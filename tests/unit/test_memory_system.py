"""Tests covering the JR-100 memory system wiring."""

from __future__ import annotations

from typing import List

from jr100emu.jr100.computer import JR100Computer
from jr100emu.jr100.display import JR100Display
from jr100emu.jr100.memory import MainRam, UserDefinedCharacterRam, VideoRam


class CaptureDisplay(JR100Display):
    def __init__(self) -> None:
        super().__init__()
        self.updated: List[tuple[int, int, int]] = []

    def update_font(self, code: int, line: int, value: int) -> None:
        super().update_font(code, line, value)
        self.updated.append((code, line, value))

    def write_video_ram(self, index: int, value: int) -> None:
        super().write_video_ram(index, value)
        self.updated.append((-1, index, value))


def test_user_defined_ram_notifies_display() -> None:
    display = CaptureDisplay()
    ram = UserDefinedCharacterRam(0xC000, 0x0100)
    ram.set_display(display)

    ram.store8(0xC000, 0xAA)
    assert (0, 0, 0xAA) in display.updated


def test_video_ram_notifies_display() -> None:
    display = CaptureDisplay()
    ram = VideoRam(0xC100, 0x0300)
    ram.set_display(display)

    ram.store8(0xC100, 0x42)
    assert (-1, 0, 0x42) in display.updated


def test_jr100_computer_installs_expected_blocks() -> None:
    computer = JR100Computer()
    memory = computer.memory

    assert memory.get_memory(MainRam) is not None
    assert memory.get_memory(UserDefinedCharacterRam) is not None
    assert memory.get_memory(VideoRam) is not None
