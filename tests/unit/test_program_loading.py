"""Tests for JR-100 user program loading."""

from __future__ import annotations

import io
import struct
from pathlib import Path

from jr100emu.jr100.computer import JR100Computer
from jr100emu.emulator.file import ProgramLoadError
from jr100emu.app import (
    SNAPSHOT_SLOTS,
    SNAPSHOT_DIR,
    _load_program_for_demo,
    _read_snapshot_from_file,
    _restore_snapshot,
    _take_snapshot,
    _write_snapshot_to_file,
)
from jr100emu.frontend import snapshot_db

BASIC_START = 0x0246
BASIC_TERMINATOR = 0xDF


def _read_c_string(computer: JR100Computer, address: int) -> bytes:
    memory = computer.memory
    data = bytearray()
    while True:
        value = memory.load8(address) & 0xFF
        if value == 0x00:
            break
        data.append(value)
        address += 1
    return bytes(data)


def _build_prog_v2(name: str, basic_data: bytes, binary_sections: list[tuple[int, bytes, str]], comment: str) -> bytes:
    buffer = io.BytesIO()
    buffer.write(b"PROG")
    buffer.write(struct.pack("<I", 2))

    def write_section(identifier: bytes, payload: bytes) -> None:
        buffer.write(int.from_bytes(identifier, "little").to_bytes(4, "little"))
        buffer.write(struct.pack("<I", len(payload)))
        buffer.write(payload)

    name_bytes = name.encode("utf-8")
    write_section(b"PNAM", struct.pack("<I", len(name_bytes)) + name_bytes)

    if basic_data:
        payload = struct.pack("<I", len(basic_data)) + basic_data
        write_section(b"PBAS", payload)

    for start, data, region_comment in binary_sections:
        comment_bytes = region_comment.encode("utf-8")
        payload = (
            struct.pack("<I", start)
            + struct.pack("<I", len(data))
            + data
            + struct.pack("<I", len(comment_bytes))
            + comment_bytes
        )
        write_section(b"PBIN", payload)

    if comment:
        comment_bytes = comment.encode("utf-8")
        payload = struct.pack("<I", len(comment_bytes)) + comment_bytes
        write_section(b"CMNT", payload)

    return buffer.getvalue()


def test_load_basic_text_with_escape(tmp_path, monkeypatch) -> None:
    # Use bundled ROM via environment override to avoid touching real files in datas.
    rom_bytes = bytearray(0x2000)
    rom_bytes[-2:] = b"\x00\xE0"  # Reset vector to BASIC ROM start
    rom_path = tmp_path / "stub_rom.prg"
    rom_payload = (
        b"PROG"
        + struct.pack("<I", 1)
        + struct.pack("<I", 0)
        + struct.pack("<I", 0)
        + struct.pack("<I", len(rom_bytes))
        + struct.pack("<I", 0)
        + rom_bytes
    )
    rom_path.write_bytes(rom_payload)
    monkeypatch.setenv("JR100EMU_ROM", str(rom_path))

    src = "10 print a\n20 data \\1b\\7f\n"
    bas_path = tmp_path / "demo.bas"
    bas_path.write_text(src, encoding="utf-8")

    computer = JR100Computer()
    info = computer.load_user_program(bas_path)

    assert info.basic_area is True
    assert info.name == "DEMO"
    memory = computer.memory

    assert memory.load16(BASIC_START) == 10
    line1 = _read_c_string(computer, BASIC_START + 2)
    assert line1 == b"PRINT A"

    second_line_addr = BASIC_START + 2 + len(line1) + 1
    assert memory.load16(second_line_addr) == 20
    line2 = _read_c_string(computer, second_line_addr + 2)
    assert line2[:5] == b"DATA "
    assert line2[5:] == bytes([0x1B, 0x7F])

    last_data_addr = second_line_addr + 2 + len(line2)
    end_pointer = (memory.load8(0x0006) << 8) | memory.load8(0x0007)
    assert end_pointer == last_data_addr
    assert memory.load8(end_pointer + 1) == BASIC_TERMINATOR


def test_load_prog_with_basic_and_binary(tmp_path, monkeypatch) -> None:
    rom_bytes = bytearray(0x2000)
    rom_bytes[-2:] = b"\x00\xE0"
    rom_path = tmp_path / "stub_rom.prg"
    rom_payload = (
        b"PROG"
        + struct.pack("<I", 1)
        + struct.pack("<I", 0)
        + struct.pack("<I", 0)
        + struct.pack("<I", len(rom_bytes))
        + struct.pack("<I", 0)
        + rom_bytes
    )
    rom_path.write_bytes(rom_payload)
    monkeypatch.setenv("JR100EMU_ROM", str(rom_path))

    basic_data = bytes(
        [0x00, 0x0A]  # line 10
        + list(b"PRINT")
        + [0x00]
    )
    binary_section = (0x2000, bytes([0xC3, 0x01, 0x02]), "BIN")
    prog_data = _build_prog_v2("HELLO", basic_data, [binary_section], "sample")
    prog_path = tmp_path / "test.prg"
    prog_path.write_bytes(prog_data)

    computer = JR100Computer()
    info = computer.load_user_program(prog_path)

    assert info.name == "HELLO"
    assert info.comment == "sample"
    assert info.basic_area is True
    assert any(region.start == BASIC_START for region in info.address_regions)
    assert any(region.start == 0x2000 and region.comment == "BIN" for region in info.address_regions)

    memory = computer.memory
    assert memory.load16(BASIC_START) == 10
    assert _read_c_string(computer, BASIC_START + 2) == b"PRINT"
    assert memory.load8(0x2000) == 0xC3
    assert memory.load8(0x2001) == 0x01
    assert memory.load8(0x2002) == 0x02
    assert computer.program_info is info


def test_load_program_helper_caption(tmp_path, monkeypatch) -> None:
    rom_bytes = bytearray(0x2000)
    rom_bytes[-2:] = b"\x00\xE0"
    rom_path = tmp_path / "stub_rom.prg"
    rom_payload = (
        b"PROG"
        + struct.pack("<I", 1)
        + struct.pack("<I", 0)
        + struct.pack("<I", 0)
        + struct.pack("<I", len(rom_bytes))
        + struct.pack("<I", 0)
        + rom_bytes
    )
    rom_path.write_bytes(rom_payload)
    monkeypatch.setenv("JR100EMU_ROM", str(rom_path))

    prog_bytes = _build_prog_v2("CAPTION", b"", [], "")
    prog_path = tmp_path / "caption.prg"
    prog_path.write_bytes(prog_bytes)

    computer = JR100Computer()
    caption, info = _load_program_for_demo(computer, str(prog_path))

    assert info is computer.program_info
    assert "CAPTION" in caption


def test_load_program_helper_error(tmp_path, monkeypatch) -> None:
    rom_bytes = bytearray(0x2000)
    rom_bytes[-2:] = b"\x00\xE0"
    rom_path = tmp_path / "stub_rom.prg"
    rom_payload = (
        b"PROG"
        + struct.pack("<I", 1)
        + struct.pack("<I", 0)
        + struct.pack("<I", 0)
        + struct.pack("<I", len(rom_bytes))
        + struct.pack("<I", 0)
        + rom_bytes
    )
    rom_path.write_bytes(rom_payload)
    monkeypatch.setenv("JR100EMU_ROM", str(rom_path))

    invalid_path = tmp_path / "invalid.bin"
    invalid_path.write_bytes(b"bad")

    computer = JR100Computer()
    try:
        _load_program_for_demo(computer, str(invalid_path))
    except SystemExit as exc:
        assert "失敗" in str(exc)
    else:
        raise AssertionError("SystemExit not raised for invalid program")


def test_snapshot_roundtrip(tmp_path, monkeypatch) -> None:
    rom_bytes = bytearray(0x2000)
    rom_bytes[-2:] = b"\x00\xE0"
    rom_path = tmp_path / "stub_rom.prg"
    rom_payload = (
        b"PROG"
        + struct.pack("<I", 1)
        + struct.pack("<I", 0)
        + struct.pack("<I", 0)
        + struct.pack("<I", len(rom_bytes))
        + struct.pack("<I", 0)
        + rom_bytes
    )
    rom_path.write_bytes(rom_payload)
    monkeypatch.setenv("JR100EMU_ROM", str(rom_path))

    computer = JR100Computer()
    snapshot = _take_snapshot(computer)
    assert snapshot is not None

    memory = computer.memory
    memory.store8(0x0246, 0x99)
    computer.cpu_core.registers.program_counter = 0xFFFF

    _restore_snapshot(computer, snapshot)
    assert memory.load8(0x0246) == snapshot.memory[0x0246]
    assert computer.cpu_core.registers.program_counter == snapshot.cpu_registers["program_counter"]


def test_snapshot_file_roundtrip(tmp_path, monkeypatch) -> None:
    rom_bytes = bytearray(0x2000)
    rom_bytes[-2:] = b"\x00\xE0"
    rom_path = tmp_path / "stub_rom.prg"
    rom_payload = (
        b"PROG"
        + struct.pack("<I", 1)
        + struct.pack("<I", 0)
        + struct.pack("<I", 0)
        + struct.pack("<I", len(rom_bytes))
        + struct.pack("<I", 0)
        + rom_bytes
    )
    rom_path.write_bytes(rom_payload)
    monkeypatch.setenv("JR100EMU_ROM", str(rom_path))

    monkeypatch.setattr("jr100emu.app.SNAPSHOT_DIR", tmp_path)
    monkeypatch.setattr(snapshot_db, "SNAPSHOT_DIR", tmp_path)

    computer = JR100Computer()
    snapshot = _take_snapshot(computer)
    assert snapshot is not None

    slot = SNAPSHOT_SLOTS[1]
    db = snapshot_db.SnapshotDatabase()
    db.set_slot(slot, comment="test")
    _write_snapshot_to_file(slot, snapshot, comment="test")

    loaded = _read_snapshot_from_file(slot)
    assert loaded is not None
    assert loaded.cpu_registers == snapshot.cpu_registers
    meta = snapshot_db.SnapshotDatabase().get(slot)
    assert meta is not None and meta.comment == "test"


def test_load_program_invalid_extension(tmp_path, monkeypatch) -> None:
    rom_bytes = bytearray(0x2000)
    rom_bytes[-2:] = b"\x00\xE0"
    rom_path = tmp_path / "stub_rom.prg"
    rom_payload = (
        b"PROG"
        + struct.pack("<I", 1)
        + struct.pack("<I", 0)
        + struct.pack("<I", 0)
        + struct.pack("<I", len(rom_bytes))
        + struct.pack("<I", 0)
        + rom_bytes
    )
    rom_path.write_bytes(rom_payload)
    monkeypatch.setenv("JR100EMU_ROM", str(rom_path))

    bin_path = tmp_path / "dummy.bin"
    bin_path.write_bytes(b"dummy")

    computer = JR100Computer()
    try:
        computer.load_user_program(bin_path)
    except ProgramLoadError:
        pass
    else:
        raise AssertionError("ProgramLoadError not raised")
