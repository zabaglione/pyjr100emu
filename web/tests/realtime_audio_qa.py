"""Measure browser clock and AudioWorklet continuity with a private JR-100 ROM."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


TARGET_CLOCK_HZ = 894_000


def snapshot(page: Page) -> dict[str, int | float | str | bool]:
    return page.evaluate(
        """() => {
          const status = document.querySelector('#core-status');
          const mute = document.querySelector('#mute');
          return {
            wallMs: performance.now(),
            clock: Number(status.dataset.clockCount || 0),
            backend: mute.dataset.audioBackend || 'none',
            workletStarted: mute.dataset.audioWorkletStarted === 'true',
            bufferedSamples: Number(mute.dataset.audioBufferedSamples || 0),
            droppedSamples: Number(mute.dataset.audioDroppedSamples || 0),
            underflowSamples: Number(mute.dataset.audioUnderflowSamples || 0),
            rebufferCount: Number(mute.dataset.audioRebufferCount || 0),
            activeSamples: Number(mute.dataset.pcmActiveSamples || 0),
          };
        }"""
    )


def warm_audio_after_three_keys(page: Page) -> int:
    for _ in range(3):
        page.keyboard.press("a", delay=40)
        page.wait_for_timeout(120)
    page.wait_for_function(
        "document.querySelector('#mute').dataset.audioBackend !== 'none'"
    )
    page.wait_for_timeout(250)
    before = snapshot(page)
    page.keyboard.press("a", delay=40)
    page.wait_for_function(
        "before => Number(document.querySelector('#mute').dataset.pcmActiveSamples || 0) "
        "> before",
        arg=before["activeSamples"],
    )
    after = snapshot(page)
    active_delta = int(after["activeSamples"]) - int(before["activeSamples"])
    assert active_delta > 0, "the fourth key did not produce active PCM"
    return active_delta


def exercise_program(
    page: Page,
    url: str,
    rom_path: Path,
    program_path: Path,
    duration_seconds: float,
    sample_interval_ms: int,
    clock_tolerance: float,
) -> dict[str, object]:
    page.goto(url, wait_until="networkidle")
    page.locator("#rom-file").set_input_files(str(rom_path))
    page.locator("#core-status").filter(has_text="Running").wait_for(timeout=120_000)
    fourth_key_active_samples = warm_audio_after_three_keys(page)

    page.locator("#program-file").set_input_files(str(program_path))
    expected_status = (
        "BASIC" if program_path.suffix.lower() in {".bas", ".txt"} else "V"
    )
    page.locator("#program-status").filter(has_text=expected_status).wait_for(
        timeout=20_000
    )
    page.wait_for_function(
        "(() => { const mute = document.querySelector('#mute'); "
        "return mute.dataset.audioBackend === 'buffer-source' "
        "|| mute.dataset.audioWorkletStarted === 'true'; })()"
    )
    page.wait_for_timeout(250)

    baseline = snapshot(page)
    telemetry = [baseline]
    sample_count = math.ceil(duration_seconds * 1000 / sample_interval_ms)
    for _ in range(sample_count):
        page.wait_for_timeout(sample_interval_ms)
        telemetry.append(snapshot(page))

    first = telemetry[0]
    last = telemetry[-1]
    elapsed_seconds = (float(last["wallMs"]) - float(first["wallMs"])) / 1000
    clock_delta = int(last["clock"]) - int(first["clock"])
    clock_rate = clock_delta / elapsed_seconds
    clock_error = abs(clock_rate - TARGET_CLOCK_HZ) / TARGET_CLOCK_HZ
    dropped = max(int(item["droppedSamples"]) for item in telemetry) - int(
        baseline["droppedSamples"]
    )
    underflow = max(int(item["underflowSamples"]) for item in telemetry) - int(
        baseline["underflowSamples"]
    )
    rebuffer = max(int(item["rebufferCount"]) for item in telemetry) - int(
        baseline["rebufferCount"]
    )
    active_delta = int(last["activeSamples"]) - int(first["activeSamples"])

    assert clock_error <= clock_tolerance, (
        f"{program_path}: {clock_rate:.1f} cycles/s is outside {clock_tolerance:.2%}"
    )
    assert dropped == 0, f"{program_path}: dropped {dropped} PCM samples"
    assert underflow == 0, f"{program_path}: underflowed {underflow} PCM samples"
    assert rebuffer == 0, f"{program_path}: rebuffered {rebuffer} times"
    assert active_delta > 0, f"{program_path}: no active PCM during measurement"

    return {
        "program": str(program_path),
        "durationSeconds": round(elapsed_seconds, 3),
        "clockRate": round(clock_rate, 1),
        "clockErrorPercent": round(clock_error * 100, 4),
        "telemetrySamples": len(telemetry),
        "bufferedSamplesMin": min(int(item["bufferedSamples"]) for item in telemetry),
        "bufferedSamplesMax": max(int(item["bufferedSamples"]) for item in telemetry),
        "baselineDroppedSamples": baseline["droppedSamples"],
        "baselineUnderflowSamples": baseline["underflowSamples"],
        "baselineRebufferCount": baseline["rebufferCount"],
        "droppedSamples": dropped,
        "underflowSamples": underflow,
        "rebufferCount": rebuffer,
        "activeSamples": active_delta,
        "fourthKeyActiveSamples": fourth_key_active_samples,
        "backend": last["backend"],
    }


def run(
    url: str,
    rom_path: Path,
    programs: list[Path],
    duration_seconds: float,
    sample_interval_ms: int,
    clock_tolerance: float,
) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        for program in programs:
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            result = exercise_program(
                page,
                url,
                rom_path,
                program,
                duration_seconds,
                sample_interval_ms,
                clock_tolerance,
            )
            assert not errors, errors
            print(json.dumps(result, sort_keys=True))
            page.close()
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--duration", type=float, default=10.0)
    parser.add_argument("--sample-interval-ms", type=int, default=100)
    parser.add_argument("--clock-tolerance", type=float, default=0.005)
    parser.add_argument("program", type=Path, nargs="+")
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error("--duration must be positive")
    if args.sample_interval_ms <= 0:
        parser.error("--sample-interval-ms must be positive")
    if not 0 < args.clock_tolerance < 1:
        parser.error("--clock-tolerance must be between zero and one")
    run(
        args.url,
        args.rom,
        args.program,
        args.duration,
        args.sample_interval_ms,
        args.clock_tolerance,
    )
    print("real-time browser audio QA passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
