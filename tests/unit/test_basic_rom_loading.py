from __future__ import annotations

from jr100emu.jr100.computer import JR100Computer


def test_basic_rom_loaded_into_memory() -> None:
    computer = JR100Computer()

    assert computer.basic_rom is not None

    # JR-100 BASIC ROM starts at 0xE000; check that known bytes are mapped.
    first_nonzero = computer.memory.load8(0xE008)
    assert first_nonzero == 0x08

    display = computer.hardware.display
    # Character ROM should mirror the BASIC ROM font payload (first 2048 bytes).
    assert display.character_rom[8] == 0x08
