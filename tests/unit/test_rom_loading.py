"""Tests for JR-100 ROM loading and CPU reset handling."""

from __future__ import annotations

import os
import struct

from jr100emu.jr100.computer import JR100Computer


def _write_prog(path, *, start: int, data: bytes) -> None:
    name = b"TEST"
    payload = (
        b"PROG"
        + struct.pack("<I", 1)
        + struct.pack("<I", len(name))
        + name
        + struct.pack("<I", start)
        + struct.pack("<I", len(data))
        + struct.pack("<I", 0)
        + data
    )
    path.write_bytes(payload)


def test_reset_vector_loaded_from_prog(tmp_path) -> None:
    payload = bytearray(0x2000)
    payload[0] = 0x01  # NOP
    payload[0x1FFE] = 0xE0
    payload[0x1FFF] = 0x00
    rom_path = tmp_path / "dummy.prg"
    _write_prog(rom_path, start=0xE000, data=bytes(payload))

    computer = JR100Computer(rom_path=str(rom_path))
    computer.cpu_core.reset()
    computer.cpu_core.execute(1)
    assert computer.cpu_core.registers.program_counter == 0xE000

    computer.tick(1)
    assert computer.cpu_core.registers.program_counter == 0xE001
    assert computer.memory.load8(0xE000) == 0x01


def test_environment_variable_overrides_default(tmp_path, monkeypatch) -> None:
    payload = bytearray(0x2000)
    payload[0] = 0x01
    payload[0x1FFE] = 0xE0
    payload[0x1FFF] = 0x00
    rom_path = tmp_path / "env.prg"
    _write_prog(rom_path, start=0xE000, data=bytes(payload))

    monkeypatch.setenv(JR100Computer.ENV_ROM_PATH, str(rom_path))

    computer = JR100Computer()
    assert computer.rom_path is not None
    assert str(computer.rom_path) == os.fspath(rom_path)
