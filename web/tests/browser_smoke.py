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


def check_audio_activation(playwright, url: str) -> None:
    for autoplay in (False, True):
        policy = (
            "no-user-gesture-required"
            if autoplay
            else "document-user-activation-required"
        )
        browser = playwright.chromium.launch(
            headless=True, args=["--no-sandbox", f"--autoplay-policy={policy}"]
        )
        methods = (
            ("automatic",) if autoplay else ("screen", "notice", "mute", "keyboard")
        )
        for method in methods:
            context = browser.new_context()
            page = context.new_page()
            page.goto(url, wait_until="networkidle")
            assert not page.locator("#audio-enable").is_visible()
            # Save a ROM without any click or key, then open the saved-ROM path.
            page.evaluate(
                """async bytes => {
                  const {saveRom} = await import('./storage.js');
                  await saveRom(Uint8Array.from(bytes), {filename:'synthetic.rom'});
                }""",
                list(synthetic_rom()),
            )
            page.reload(wait_until="networkidle")
            page.wait_for_function(
                "document.querySelector('#core-status').textContent === 'Running'"
            )
            notice = page.locator("#audio-enable")
            if not autoplay:
                notice.wait_for(state="visible")
                assert page.locator("#mute").inner_text() == "Enable sound"
                assert (
                    page.locator("#mute").get_attribute("data-audio-state")
                    == "suspended"
                )
                rect, screen = (
                    notice.bounding_box(),
                    page.locator("#screen").bounding_box(),
                )
                assert rect["y"] + rect["height"] <= screen["y"]
                assert "画面をマウスでクリックして" in notice.inner_text()
                if method == "keyboard":
                    notice.focus()
                    page.keyboard.press("Enter")
                else:
                    selector = {
                        "screen": "#screen",
                        "notice": "#audio-enable",
                        "mute": "#mute",
                    }[method]
                    page.locator(selector).click()
            page.wait_for_function(
                "document.querySelector('#mute').dataset.audioReady === 'true'"
            )
            notice.wait_for(state="hidden")
            assert page.locator("#mute").inner_text() == "Sound on"
            page.wait_for_function(
                "document.querySelector('#mute').dataset.audioWorkletStarted === 'true'"
            )
            assert page.locator("#error-status").inner_text() == ""
            if method in ("notice", "keyboard"):
                assert page.evaluate("document.activeElement.id") == "screen"
            # Muting hides the activation request and survives a reload.
            page.locator("#mute").click()
            assert page.locator("#mute").inner_text() == "Sound off"
            page.reload(wait_until="networkidle")
            page.wait_for_function(
                "document.querySelector('#core-status').textContent === 'Running'"
            )
            assert not notice.is_visible()
            assert page.locator("#mute").inner_text() == "Sound off"
            assert (
                page.locator("#mute").get_attribute("data-audio-state") == "not-created"
            )
            page.locator("#mute").click()
            page.wait_for_function(
                "document.querySelector('#mute').dataset.audioReady === 'true'"
            )
            assert not notice.is_visible()
            context.close()
            print(
                f"PASS: audio activation {method}, real browser policy, PCM output and saved mute"
            )
        browser.close()


def run(url: str) -> None:
    with sync_playwright() as playwright:
        check_audio_activation(playwright, url)
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page()
        page.add_init_script(
            """
            globalThis.__testGamepad = {
              id: "Synthetic Gamepad",
              axes: [0, 0],
              buttons: Array.from(
                { length: 16 },
                () => ({ pressed: false, value: 0 }),
              ),
            };
            globalThis.__joystickMessages = [];
            globalThis.__resetMessages = 0;
            Object.defineProperty(navigator, "getGamepads", {
              configurable: true,
              value: () => [globalThis.__testGamepad],
            });
            const originalPostMessage = Worker.prototype.postMessage;
            Worker.prototype.postMessage = function(message, transfer) {
              if (message?.type === "reset") globalThis.__resetMessages++;
              if (message?.type === "joystick") {
                globalThis.__joystickMessages.push(message.mask);
              }
              if (transfer === undefined) return originalPostMessage.call(this, message);
              return originalPostMessage.call(this, message, transfer);
            };
            """
        )
        page.goto(url, wait_until="networkidle")
        assert page.title() == "JR-100 Web Emulator"
        assert page.locator("#core-status").inner_text() == "ROM required"
        assert page.locator(".virtual-key").count() == 45
        assert page.locator(".keyboard-row").count() == 4
        assert page.locator("#virtual-keyboard").get_attribute("hidden") is None
        assert page.locator(".virtual-key.cursor").count() == 0

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

        def dismiss_reset(dialog):
            assert dialog.type == "confirm" and "Really reset?" in dialog.message
            dialog.dismiss()

        page.once("dialog", dismiss_reset)
        page.locator("#reset").click()
        assert page.evaluate("globalThis.__resetMessages") == 0
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator("#reset").click()
        page.wait_for_function("globalThis.__resetMessages === 1")
        assert page.locator(".main-legend:not([hidden])").count() > 20
        assert page.locator(".key-v .ctrl-legend").inner_text() == "GRAPH"
        page.evaluate(
            """
            () => {
              globalThis.__testGamepad.axes = [1, -1];
              for (const index of [0, 8]) {
                globalThis.__testGamepad.buttons[index] = { pressed: true, value: 1 };
              }
            }
            """
        )
        page.wait_for_function("globalThis.__joystickMessages.includes(0x15)")
        assert page.locator("#virtual-keyboard").get_attribute("hidden") is None
        assert page.locator(".virtual-key.cursor").count() == 0
        page.evaluate(
            """
            () => {
              globalThis.__testGamepad.axes = [0, 0];
              for (const button of globalThis.__testGamepad.buttons) {
                button.pressed = false;
                button.value = 0;
              }
            }
            """
        )
        page.wait_for_function("globalThis.__joystickMessages.at(-1) === 0")
        page.keyboard.press("a")
        page.wait_for_function(
            "document.querySelector('#mute').dataset.audioBackend !== 'none'"
        )
        assert page.locator("#mute").get_attribute("data-audio-backend") in {
            "worklet",
            "buffer-source",
        }
        page.wait_for_function(
            "(() => { const button = document.querySelector('#mute'); "
            "return button.dataset.audioBackend === 'buffer-source' "
            "|| button.dataset.audioWorkletStarted === 'true'; })()",
        )
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

        page.locator("#program-file").set_input_files(
            {
                "name": "demo.bas",
                "mimeType": "text/plain",
                "buffer": b"10 END\n",
            }
        )
        page.locator("#program-status").filter(has_text="BASIC").wait_for()
        assert page.locator("#program-entry").is_disabled()
        assert page.locator("#run-entry").is_disabled()

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
