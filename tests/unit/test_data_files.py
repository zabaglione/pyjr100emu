from __future__ import annotations

from pathlib import Path

from jr100emu.emulator.file import (
    BasicTextFormatFile,
    BinaryTextFormatFile,
    ProgramInfo,
    AddressRegion,
)
from jr100emu.memory import MemorySystem
from jr100emu.emulator.file.program import BASIC_START_ADDRESS


def make_memory() -> MemorySystem:
    memory = MemorySystem()
    memory.allocate_space(0x10000)
    from jr100emu.memory import RAM

    memory.register_memory(RAM(0x0000, 0x10000))
    return memory


def test_basic_text_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "sample.bas"
    source.write_text("10 PRINT \"HELLO\"\n20 END\n", encoding="utf-8")

    memory = make_memory()
    loader = BasicTextFormatFile(source)
    info = loader.load_jr100(memory)
    assert loader.error_status == loader.STATUS_SUCCESS
    assert info.basic_area is True

    target = tmp_path / "roundtrip.bas"
    saver = BasicTextFormatFile(target)
    saver.save_jr100(info)
    assert saver.error_status == saver.STATUS_SUCCESS
    assert "PRINT" in target.read_text(encoding="utf-8")


def test_basic_text_save_handles_non_printable(tmp_path: Path) -> None:
    memory = make_memory()
    info = ProgramInfo(memory=memory, basic_area=True)
    addr = BASIC_START_ADDRESS
    memory.store16(addr, 100)
    addr += 2
    memory.store8(addr, 0x1B)
    addr += 1
    memory.store8(addr, 0x00)
    end_ptr = addr - 1
    # emulate finalize
    memory.store8(end_ptr + 1, 0xDF)
    memory.store8(end_ptr + 2, 0xDF)
    memory.store8(end_ptr + 3, 0xDF)
    pointer = end_ptr
    for index in range(4):
        memory.store16(0x0006 + index * 2, pointer & 0xFFFF)
        pointer += 1

    target = tmp_path / "control.bas"
    saver = BasicTextFormatFile(target)
    saver.save_jr100(info)
    content = target.read_text(encoding="utf-8")
    assert "\\1B" in content


def test_binary_text_load_and_save(tmp_path: Path) -> None:
    source = tmp_path / "sample.txt"
    source.write_text("C000 AA BB CC : 31\n", encoding="utf-8")

    memory = make_memory()
    loader = BinaryTextFormatFile(source)
    info = loader.load_jr100(memory)
    assert loader.error_status == loader.STATUS_SUCCESS
    assert memory.load8(0xC000) == 0xAA
    assert info.address_regions and info.address_regions[0].start == 0xC000

    info.address_regions = [AddressRegion(start=0xC000, end=0xC002)]
    target = tmp_path / "dump.txt"
    saver = BinaryTextFormatFile(target)
    saver.save_jr100(info)
    out = target.read_text(encoding="utf-8")
    assert "C000" in out and ":" in out


def test_binary_text_invalid_checksum(tmp_path: Path) -> None:
    source = tmp_path / "broken.txt"
    source.write_text("C000 AA : 00\n", encoding="utf-8")
    memory = make_memory()
    loader = BinaryTextFormatFile(source)
    loader.load_jr100(memory)
    assert loader.error_status == loader.STATUS_CHECK_SUM_ERROR
