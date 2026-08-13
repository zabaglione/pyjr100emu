from __future__ import annotations

import struct

import pytest

from jr100emu.browser import BrowserCore
from jr100emu.jr100.computer import JR100Computer
from jr100emu.jr100.memory import RomFormatError, decode_rom_bytes


def _rom_payload() -> bytes:
    payload = bytearray(0x2000)
    payload[0] = 0x01
    payload[0x1A6C : 0x1A6C + 43] = bytes.fromhex(
        "5a584341534446475157455254313233343536373839305955494f50"
        "484a4b4c3b56424e4d2c2e203a0d2d"
    )
    payload[0x1A99 : 0x1A99 + 43] = bytes.fromhex(
        "000000000000000000000000002122232425262728295e00405c5b5d"
        "00003f2f2b0000005f3c3e202a0d3d"
    )
    payload[0x1FFE] = 0xE0
    payload[0x1FFF] = 0x00
    return bytes(payload)


def _beep_rom_payload() -> bytes:
    payload = bytearray(_rom_payload())
    payload[:17] = bytes(
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
    return bytes(payload)


def _machine_prog_v2(start: int = 0x3000, entry: int = 0x3010) -> bytes:
    comment = f"entry=${entry:04X}".encode()
    payload = (
        struct.pack("<I", start)
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


def _machine_prog_v2_without_entry(start: int = 0x3000) -> bytes:
    payload = struct.pack("<I", start) + struct.pack("<I", 2) + b"\x20\xfe"
    return (
        b"PROG"
        + struct.pack("<I", 2)
        + b"PBIN"
        + struct.pack("<I", len(payload))
        + payload
    )


def _machine_prog_v1(start: int = 0x3400) -> bytes:
    name = b"V1DEMO"
    payload = b"\x20\xfe"
    return (
        b"PROG"
        + struct.pack("<I", 1)
        + struct.pack("<I", len(name))
        + name
        + struct.pack("<I", start)
        + struct.pack("<I", len(payload))
        + struct.pack("<I", 1)
        + payload
    )


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


def test_browser_core_captures_beep_pcm_without_pygame() -> None:
    core = BrowserCore(_beep_rom_payload())

    core.run_frame()
    core.run_frame()
    pcm = core.audio_buffer()

    assert len(pcm) >= 700
    assert any(sample != 0 for sample in pcm)
    assert core.audio_buffer() == []


def test_browser_core_exposes_rom_keyboard_assets() -> None:
    rom = bytearray(_rom_payload())
    rom[:1024] = bytes((index & 0xFF) for index in range(1024))
    rom[0x1A6C : 0x1A6C + 43] = bytes(range(0x20, 0x20 + 43))
    rom[0x1A99 : 0x1A99 + 43] = bytes(range(43))
    core = BrowserCore(bytes(rom))

    assert core.font_data() == bytes(rom[:1024])
    assert core.normal_key_codes() == bytes(rom[0x1A6C : 0x1A6C + 43])
    assert core.shift_key_codes() == bytes(rom[0x1A99 : 0x1A99 + 43])


def test_browser_core_extended_ram_and_debug_memory() -> None:
    core = BrowserCore(_rom_payload(), extended_ram=True)

    core.computer.memory.store8(0x4000, 0xA5)
    state = core.debug_state()

    assert core.computer.memory.load8(0x4000) == 0xA5
    assert state["extendedRam"] is True
    assert set(state["cpu"]) == {"a", "b", "ix", "sp", "pc", "flags"}
    assert len(core.read_memory(0x3FF8, 16)) == 16
    assert len(core.read_memory(0xFFF8, 16)) == 16


def test_browser_core_loads_v2_program_and_queues_usr_autostart() -> None:
    core = BrowserCore(_rom_payload(), extended_ram=True)

    info = core.load_program(_machine_prog_v2(), filename="demo.prg")

    assert info["version"] == 2
    assert info["entryPoint"] == 0x3010
    assert info["entrySource"] == "comment"
    assert info["autostartCommand"] == "A=USR($3010)"
    assert core.computer.memory.load8(0x3000) == 0x20
    assert core.state()["autotypeActive"] is True


def test_browser_core_loads_basic_text_bytes_and_queues_run() -> None:
    core = BrowserCore(_rom_payload())

    info = core.load_program(b"10 END\n", filename="demo.bas")

    assert info["basic"] is True
    assert info["autostartCommand"] == "RUN"
    assert core.computer.memory.load16(0x0246) == 10
    assert core.state()["autotypeActive"] is True


def test_browser_core_can_reset_and_run_an_overridden_usr_entry() -> None:
    core = BrowserCore(_rom_payload())
    core.load_program(_machine_prog_v2(), filename="demo.prg")

    command = core.run_entry(0x3456)

    assert command == "A=USR($3456)"
    assert core.state()["autotypeActive"] is True
    assert core.computer.cpu_core.registers.program_counter == 0xE000


def test_browser_core_autostarts_v1_machine_program_at_header_start() -> None:
    core = BrowserCore(_rom_payload())

    info = core.load_program(_machine_prog_v1(), filename="v1demo.prg")

    assert info["version"] == 1
    assert info["entryPoint"] == 0x3400
    assert info["entrySource"] == "v1-start"
    assert info["autostartCommand"] == "A=USR($3400)"


def test_browser_core_does_not_autostart_an_inferred_v2_load_address() -> None:
    core = BrowserCore(_rom_payload())

    info = core.load_program(_machine_prog_v2_without_entry(), filename="legacy.prg")

    assert info["entryPoint"] is None
    assert info["suggestedEntryPoint"] == 0x3000
    assert info["entrySource"] == "pbin-start"
    assert info["autostartCommand"] == ""
    assert core.state()["autotypeActive"] is False


def test_browser_core_stops_on_breakpoint_and_steps_one_instruction() -> None:
    core = BrowserCore(_beep_rom_payload())
    core.run_frame()
    core.set_breakpoints([0xE005])

    core.run_frame()

    assert core.state()["breakpointHit"] == 0xE005
    assert core.debug_state()["cpu"]["pc"] == 0xE005

    before = core.computer.clock_count
    state = core.step_instruction()

    assert state["cpu"]["pc"] == 0xE007
    assert core.computer.clock_count > before
    assert core.state()["breakpointHit"] is None
