from __future__ import annotations

import struct

import pytest

from jr100emu.browser import BrowserCore
from jr100emu.jr100.computer import JR100Computer
from jr100emu.jr100.memory import RomFormatError, decode_rom_bytes


def _rom_payload() -> bytes:
    payload = bytearray(0x2000)
    payload[0] = 0x01
    payload[0x1FFE] = 0xE0
    payload[0x1FFF] = 0x00
    return bytes(payload)


def _prog_image(payload: bytes) -> bytes:
    name = b"BASICROM"
    return (
        b"PROG"
        + struct.pack("<I", 1)
        + struct.pack("<I", len(name))
        + name
        + struct.pack("<I", 0xE000)
        + struct.pack("<I", len(payload))
        + struct.pack("<I", 0)
        + payload
    )


def test_decode_rom_bytes_accepts_raw_image() -> None:
    image = decode_rom_bytes(_rom_payload(), start=0xE000, length=0x2000)

    assert image.format == "raw"
    assert image.start_address == 0xE000
    assert image.data[0x1FFF] == 0x00


def test_decode_rom_bytes_accepts_prog_container() -> None:
    image = decode_rom_bytes(_prog_image(_rom_payload()), start=0xE000, length=0x2000)

    assert image.format == "prog"
    assert image.name == "BASICROM"
    assert image.data == _rom_payload()


def test_decode_rom_bytes_rejects_invalid_rom() -> None:
    with pytest.raises(RomFormatError):
        decode_rom_bytes(b"not a jr-100 rom", start=0xE000, length=0x2000)


def test_browser_core_requires_rom_and_exposes_frame_and_inputs() -> None:
    core = BrowserCore(_rom_payload())

    assert core.rom_info["format"] == "raw"
    assert len(core.frame_buffer()) == 256 * 192

    core.set_key(1, 0, True)
    assert core.computer.hardware.keyboard.get_key_matrix()[1] == 0x01
    core.set_key(1, 0, False)
    assert core.computer.hardware.keyboard.get_key_matrix()[1] == 0x00

    core.set_joystick_mask(0x1F)
    assert core.computer.ext_port.get_gamepad_status() == 0x1F
    frame = core.run_frame()
    assert len(frame) == 256 * 192


def test_browser_machine_does_not_resolve_private_default_rom() -> None:
    computer = JR100Computer(enable_audio=False, allow_implicit_rom=False)

    assert computer.rom_path is None
    assert computer.basic_rom is not None
    assert computer.basic_rom.format is None
