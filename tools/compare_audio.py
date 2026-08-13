#!/usr/bin/env python3
"""Compare PCM from the native C++ core with the pygame/Python core."""

from __future__ import annotations

import argparse
from array import array
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from jr100emu.browser import BrowserCore


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUNNER_BUILD = ROOT / "build" / "native-compare"


def _active_segments(samples: array, window: int = 32) -> list[array]:
    active_windows = [
        any(samples[index : index + window]) for index in range(0, len(samples), window)
    ]
    segments: list[array] = []
    start: int | None = None
    for index, active in enumerate(active_windows + [False]):
        if active and start is None:
            start = index * window
        elif not active and start is not None:
            segments.append(samples[start : min(index * window, len(samples))])
            start = None
    return segments


def _estimated_frequency(samples: array, sample_rate: int = 44_100) -> float:
    signs = [sample > 0 for sample in samples if sample != 0]
    crossings = sum(left != right for left, right in zip(signs, signs[1:]))
    return crossings * sample_rate / (2.0 * len(samples)) if samples else 0.0


def _ensure_runner(path: Path | None) -> Path:
    if path is not None:
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
    build = DEFAULT_RUNNER_BUILD
    runner = build / "jr100_core_runner"
    subprocess.run(
        [
            "cmake",
            "-S",
            str(ROOT / "cpp"),
            "-B",
            str(build),
            "-DCMAKE_BUILD_TYPE=Release",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["cmake", "--build", str(build), "--target", "jr100_core_runner", "-j", "4"],
        cwd=ROOT,
        check=True,
    )
    return runner


def _run_cpp(
    runner: Path,
    rom_path: Path,
    program_path: Path,
    frames: int,
    boot_frames: int,
) -> tuple[array, dict[str, object]]:
    with tempfile.TemporaryDirectory(prefix="jr100-cpp-audio-") as directory:
        pcm_path = Path(directory) / "audio.pcm"
        process = subprocess.run(
            [
                str(runner),
                "--rom",
                str(rom_path),
                "--boot-frames",
                str(boot_frames),
                "--program",
                str(program_path),
                "--frames",
                str(frames),
                "--audio",
                str(pcm_path),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        samples = array("h")
        samples.frombytes(pcm_path.read_bytes())
        if sys.byteorder != "little":
            samples.byteswap()
        summary = json.loads(process.stdout.strip().splitlines()[-1])
        return samples, summary


def _run_python(
    rom_path: Path,
    program_path: Path,
    frames: int,
    boot_frames: int,
) -> tuple[array, dict[str, object]]:
    core = BrowserCore(rom_path.read_bytes())
    for _ in range(boot_frames):
        core.run_frame()
    core.audio_buffer()
    core.load_program(program_path.read_bytes(), filename=program_path.name)
    samples = array("h")
    for _ in range(frames):
        core.run_frame()
        samples.extend(core.audio_buffer())
    return samples, core.debug_state()


def compare(
    runner: Path,
    rom_path: Path,
    program_path: Path,
    frames: int,
    boot_frames: int,
) -> dict[str, object]:
    cpp_samples, cpp_state = _run_cpp(
        runner, rom_path, program_path, frames, boot_frames
    )
    python_samples, python_state = _run_python(
        rom_path, program_path, frames, boot_frames
    )
    cpp_segments = _active_segments(cpp_samples)
    python_segments = _active_segments(python_samples)
    cpp_frequencies = [_estimated_frequency(segment) for segment in cpp_segments]
    python_frequencies = [_estimated_frequency(segment) for segment in python_segments]
    frequency_deltas = [
        abs(cpp - reference)
        for cpp, reference in zip(cpp_frequencies, python_frequencies)
    ]
    common_length = min(len(cpp_samples), len(python_samples))
    differences = [
        abs(cpp_samples[index] - python_samples[index])
        for index in range(common_length)
    ]
    sample_delta = abs(len(cpp_samples) - len(python_samples))
    sample_ratio = sample_delta / max(len(cpp_samples), len(python_samples), 1)
    passed = (
        len(cpp_segments) == len(python_segments)
        and sample_ratio <= 0.01
        and max(frequency_deltas, default=0.0) <= 25.0
    )
    return {
        "program": str(program_path),
        "frames": frames,
        "bootFrames": boot_frames,
        "cppSamples": len(cpp_samples),
        "pygameSamples": len(python_samples),
        "sampleCountDelta": sample_delta,
        "sampleCountRatio": round(sample_ratio, 8),
        "cppSegments": len(cpp_segments),
        "pygameSegments": len(python_segments),
        "cppFrequencies": [round(value, 1) for value in cpp_frequencies],
        "pygameFrequencies": [round(value, 1) for value in python_frequencies],
        "maxFrequencyDelta": round(max(frequency_deltas, default=0.0), 3),
        "exactCommonSamples": sum(value == 0 for value in differences),
        "maxAbsDifference": max(differences, default=0),
        "cppState": cpp_state,
        "pygameState": python_state,
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("datas/jr100rom.prg"))
    parser.add_argument("--runner", type=Path)
    parser.add_argument("--frames", type=int, help="override the scenario frame count")
    parser.add_argument("--boot-frames", type=int, default=140)
    parser.add_argument(
        "program",
        type=Path,
        nargs="*",
        default=[Path("datas/sound_scale.prg"), Path("datas/twinkle_star.bas")],
    )
    args = parser.parse_args()
    if args.frames is not None and args.frames <= 0:
        parser.error("--frames must be positive")
    if args.boot_frames < 0:
        parser.error("--boot-frames must not be negative")
    runner = _ensure_runner(args.runner)
    passed = True
    for program in args.program:
        frames = args.frames or (
            4_000 if program.suffix.lower() in {".bas", ".txt"} else 1_200
        )
        result = compare(runner, args.rom, program, frames, args.boot_frames)
        print(json.dumps(result, sort_keys=True))
        passed = passed and bool(result["passed"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
