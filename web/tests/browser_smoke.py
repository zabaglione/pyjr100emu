"""Run a browser smoke test against a locally served Pages artifact."""

from __future__ import annotations

import argparse
import struct

from playwright.sync_api import sync_playwright


def synthetic_rom() -> bytes:
    image = bytearray(0x2000)
    for code in range(128):
        image[code * 8 : (code + 1) * 8] = bytes(
            [0x7E, 0x42, 0x42, 0x42, 0x42, 0x42, 0x7E, 0x00]
        )
    image[0x400:0x411] = bytes(
        [
            0x86,
            0xC0,
            0xB7,
            0xC8,
            0x0B,
            0x86,
            0xFF,
            0xB7,
            0xC8,
            0x04,
            0x86,
            0x01,
            0xB7,
            0xC8,
            0x05,
            0x20,
            0xFE,
        ]
    )
    image[0x1A6C : 0x1A6C + 43] = bytes.fromhex(
        "5a584341534446475157455254313233343536373839305955494f50"
        "484a4b4c3b56424e4d2c2e203a0d2d"
    )
    image[0x1A99 : 0x1A99 + 43] = bytes.fromhex(
        "000000000000000000000000002122232425262728295e00405c5b5d"
        "00003f2f2b0000005f3c3e202a0d3d"
    )
    image[-2:] = b"\xe4\x00"
    return bytes(image)


def synthetic_program() -> bytes:
    comment = b"entry=$3010"
    payload = (
        struct.pack("<I", 0x3000)
        + struct.pack("<I", 2)
        + b"\x20\xfe"
        + struct.pack("<I", len(comment))
        + comment
    )
    return (
        b"PROG"
        + struct.pack("<I", 2)
        + b"PBIN"
        + struct.pack("<I", len(payload))
        + payload
    )


def run(url: str) -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        assert page.title() == "JR-100 Web Emulator"
        assert page.locator("#core-status").inner_text() == "ROM required"
        assert page.locator(".virtual-key").count() == 45
        assert page.locator(".keyboard-row").count() == 4
        assert page.locator("#virtual-keyboard").get_attribute("hidden") is None

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
        page.locator("#extended-ram").check()

        page.locator("#rom-file").set_input_files(
            {
                "name": "synthetic.rom",
                "mimeType": "application/octet-stream",
                "buffer": synthetic_rom(),
            }
        )
        page.locator("#core-status").filter(has_text="Running").wait_for(
            timeout=120_000
        )
        assert page.locator("#error-status").inner_text() == ""
        assert page.locator("#rom-status").inner_text().startswith("synthetic.rom")
        assert "32K RAM" in page.locator("#rom-status").inner_text()
        assert page.locator(".main-legend:not([hidden])").count() > 20
        assert page.locator(".key-v .ctrl-legend").inner_text() == "GRAPH"
        page.wait_for_function(
            "Number(document.querySelector('#mute').dataset.pcmSamples || 0) > 0"
        )

        page.locator("#program-file").set_input_files(
            {
                "name": "demo.prg",
                "mimeType": "application/octet-stream",
                "buffer": synthetic_program(),
            }
        )
        page.locator("#program-status").filter(has_text="V2").wait_for()
        assert "entry $3010" in page.locator("#program-status").inner_text()
        page.locator("#program-entry").fill("3456")
        page.locator("#run-entry").click()
        page.locator("#program-status").filter(
            has_text="queued A=USR($3456)"
        ).wait_for()

        page.locator("#toggle-debugger").click()
        page.locator("#debug-memory").filter(has_text="0000").wait_for()
        assert "PC" in page.locator("#debug-cpu").inner_text()
        page.locator("#breakpoints").fill("E40F")
        page.locator("#apply-breakpoints").click()
        page.locator("#core-status").filter(has_text="Break $E40F").wait_for()
        page.locator("#debug-step").click()
        page.locator("#core-status").filter(has_text="Paused").wait_for()
        page.keyboard.press("Escape")
        assert page.locator("#debugger").get_attribute("hidden") == ""
        page.keyboard.press("Escape")
        assert page.locator("#debugger").get_attribute("hidden") is None

        page.locator("#toggle-keyboard").click()
        assert page.locator("#virtual-keyboard").get_attribute("hidden") == ""
        page.reload(wait_until="networkidle")
        page.locator("#core-status").filter(has_text="Running").wait_for(
            timeout=120_000
        )
        assert page.locator("#rom-status").inner_text().startswith("synthetic.rom")
        assert page.locator("#virtual-keyboard").get_attribute("hidden") == ""
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
