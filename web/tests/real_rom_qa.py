"""Exercise browser-only paths that require a private real-machine ROM."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def run(
    url: str,
    rom_path: Path,
    screenshot: Path | None,
    mobile_screenshot: Path | None,
) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1180, "height": 1100})
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url, wait_until="networkidle")
        page.locator("#rom-file").set_input_files(str(rom_path))
        page.locator("#core-status").filter(has_text="Running").wait_for(
            timeout=120_000
        )
        page.wait_for_timeout(2_000)
        alpha_legend = page.locator(".key-1 .alternate-legend").get_attribute(
            "data-code"
        )

        page.keyboard.down("Control")
        page.wait_for_timeout(100)
        page.keyboard.down("v")
        page.wait_for_timeout(120)
        page.keyboard.up("v")
        page.keyboard.up("Control")
        page.locator("#keyboard-mode").filter(has_text="GRAPH").wait_for(timeout=10_000)
        graph_legend = page.locator(".key-1 .alternate-legend").get_attribute(
            "data-code"
        )
        assert alpha_legend != graph_legend
        page.wait_for_function(
            "Number(document.querySelector('#mute').dataset.pcmSamples || 0) > 0"
        )

        page.keyboard.down("Control")
        page.wait_for_timeout(100)
        page.keyboard.press("v")
        page.keyboard.up("Control")
        page.locator("#keyboard-mode").filter(has_text="ALPHA").wait_for(timeout=10_000)
        assert (
            page.locator(".key-1 .alternate-legend").get_attribute("data-code")
            == alpha_legend
        )

        page.locator("#toggle-debugger").click()
        page.locator("#debug-memory").filter(has_text="0000").wait_for()
        clock_before = page.locator("#debug-cpu").inner_text()
        page.locator("#debug-step").click()
        page.wait_for_function(
            "(before) => document.querySelector('#debug-cpu').textContent !== before",
            arg=clock_before,
        )
        page.locator("#debug-vram").click()
        page.locator("#debug-memory").filter(has_text="C100").wait_for()
        page.locator("#debug-stack").click()
        page.wait_for_function(
            "document.querySelector('#memory-start').value !== 'C100'"
        )
        assert page.locator("#error-status").inner_text() == ""
        assert not errors, errors

        if screenshot is not None:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(screenshot), full_page=True)
        if mobile_screenshot is not None:
            mobile_screenshot.parent.mkdir(parents=True, exist_ok=True)
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(mobile_screenshot), full_page=True)
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument("--mobile-screenshot", type=Path)
    args = parser.parse_args()
    run(args.url, args.rom, args.screenshot, args.mobile_screenshot)
    print("real ROM browser QA passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
