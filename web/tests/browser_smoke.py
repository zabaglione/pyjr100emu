"""Run a browser smoke test against a locally served Pages artifact."""

from __future__ import annotations

import argparse

from playwright.sync_api import sync_playwright


def synthetic_rom() -> bytes:
    image = bytearray(0x2000)
    image[0] = 0x01
    image[-2:] = b"\xe0\x00"
    return bytes(image)


def run(url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        assert page.title() == "JR-100 Web Emulator"
        assert page.locator("#core-status").inner_text() == "ROM required"
        assert page.locator(".virtual-key").count() == 45

        page.locator("#rom-file").set_input_files(
            {
                "name": "invalid.rom",
                "mimeType": "application/octet-stream",
                "buffer": b"invalid",
            }
        )
        page.locator("#core-status").filter(has_text="Error").wait_for(timeout=120_000)
        page.reload(wait_until="networkidle")
        assert page.locator("#core-status").inner_text() == "ROM required"

        page.locator("#rom-file").set_input_files(
            {
                "name": "synthetic.rom",
                "mimeType": "application/octet-stream",
                "buffer": synthetic_rom(),
            }
        )
        page.locator("#core-status").filter(has_text="Running").wait_for(timeout=120_000)
        assert page.locator("#error-status").inner_text() == ""
        assert page.locator("#rom-status").inner_text().startswith("synthetic.rom")

        page.locator("#toggle-keyboard").click()
        assert page.locator("#virtual-keyboard").get_attribute("hidden") is None
        page.reload(wait_until="networkidle")
        page.locator("#core-status").filter(has_text="Running").wait_for(timeout=120_000)
        assert page.locator("#rom-status").inner_text().startswith("synthetic.rom")
        browser.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/")
    args = parser.parse_args()
    run(args.url)
    print("browser smoke passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
