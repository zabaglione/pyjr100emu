"""Private-ROM acceptance checks for browser-core automation."""

from pathlib import Path

import pytest

from jr100emu.browser import BrowserCore


ROM_PATH = Path("datas/jr100rom.prg")
PROGRAM_PATH = Path("datas/sample.prg")


@pytest.mark.skipif(
    not ROM_PATH.exists() or not PROGRAM_PATH.exists(),
    reason="private real-machine ROM acceptance assets are unavailable",
)
def test_real_rom_accepts_v2_autostart_return_and_reaches_entry() -> None:
    core = BrowserCore(ROM_PATH.read_bytes())
    for _ in range(180):
        core.run_frame()

    info = core.load_program(PROGRAM_PATH.read_bytes(), filename=PROGRAM_PATH.name)
    for _ in range(280):
        core.run_frame()
    core.set_breakpoints([0x0300])
    for _ in range(100):
        core.run_frame()
        if core.state()["breakpointHit"] is not None:
            break

    assert info["entrySource"] == "comment"
    assert core.state()["breakpointHit"] == 0x0300
