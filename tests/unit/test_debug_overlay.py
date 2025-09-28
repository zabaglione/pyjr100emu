"""Tests for the pygame debug overlay."""

from __future__ import annotations

import os

import pytest

from jr100emu.frontend.debug_overlay import DebugOverlay
from jr100emu.jr100.computer import JR100Computer


@pytest.fixture(autouse=True)
def _set_dummy_video(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")


def _create_stub_rom(tmp_path):
    import struct

    rom_bytes = bytearray(0x2000)
    rom_bytes[-2:] = b"\x00\xE0"
    rom_path = tmp_path / "stub_rom.prg"
    payload = (
        b"PROG"
        + struct.pack("<I", 1)
        + struct.pack("<I", 0)
        + struct.pack("<I", 0)
        + struct.pack("<I", len(rom_bytes))
        + struct.pack("<I", 0)
        + rom_bytes
    )
    rom_path.write_bytes(payload)
    return rom_path


def test_debug_overlay_renders_surface(tmp_path, monkeypatch):
    pygame = pytest.importorskip("pygame")

    rom_path = _create_stub_rom(tmp_path)
    monkeypatch.setenv("JR100EMU_ROM", os.fspath(rom_path))

    pygame.init()
    computer = JR100Computer()
    overlay = DebugOverlay(computer)

    if computer.cpu_core is not None:
        overlay.record_execution(computer.cpu_core.registers.program_counter)
    overlay.capture_state()

    surface = pygame.Surface((320, 240))
    surface.fill((0, 0, 0))
    overlay.render(surface)

    raw = pygame.image.tostring(surface, "RGBA")
    assert any(raw)

    pygame.quit()


def test_debug_overlay_trace(tmp_path, monkeypatch):
    pygame = pytest.importorskip("pygame")

    rom_path = _create_stub_rom(tmp_path)
    monkeypatch.setenv("JR100EMU_ROM", os.fspath(rom_path))

    pygame.init()
    computer = JR100Computer()
    overlay = DebugOverlay(computer)

    for pc in range(0xE000, 0xE010):
        overlay.record_execution(pc)
    trace = overlay.get_trace()
    assert trace[-1] == 0xE00F
    assert trace[0] == 0xE000

    pygame.quit()
