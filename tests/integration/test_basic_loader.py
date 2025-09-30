"""Integration tests for loading JR-100 BASIC text programs."""

from __future__ import annotations

from pathlib import Path

from jr100emu.jr100.computer import JR100Computer


def test_load_basic_text_sample(tmp_path: Path) -> None:
    computer = JR100Computer(rom_path="datas/jr100rom.prg", enable_audio=False)

    info = computer.load_user_program("datas/prog_sample.bas")

    assert info.basic_area
    assert info.name == "PROG_SAMPLE"

    memory = computer.memory

    # プログラム先頭の REM 行が正しく格納されているか確認する
    header_bytes = [memory.load8(0x0246 + i) & 0xFF for i in range(16)]
    assert header_bytes[0:2] == [0x00, 0x64]  # line number 100
    rem_text = bytes(header_bytes[2:2 + 16]).decode("ascii", errors="ignore")
    assert rem_text.startswith("REM")

    # TXTTOP (0x0004/0x0005) が BASIC 開始番地を指すこと
    txttop = (memory.load8(0x0004) << 8) | (memory.load8(0x0005) & 0xFF)
    assert txttop == 0x0246

    # BASIC ワークエリア関連ポインタが更新されていること
    txttop = (memory.load8(0x0004) << 8) | (memory.load8(0x0005) & 0xFF)
    assert txttop == 0x0246
    prog_ptr = (memory.load8(0x0022) << 8) | (memory.load8(0x0023) & 0xFF)
    assert prog_ptr == 0x0246

    # BASIC ポインタテーブル (0x0006〜0x000D) が終端を示す値で更新されていること
    pointers = [memory.load8(0x0006 + i) & 0xFF for i in range(8)]
    assert any(value != 0x00 for value in pointers)
