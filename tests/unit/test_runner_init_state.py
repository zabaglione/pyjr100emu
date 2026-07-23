"""Tests for lockstep initial-state control in the debug runner.

Lockstep comparison requires identical initial registers and RAM on both
sides (JR100_MiSTer requirements §5.2), so the runner must be able to
normalise registers and export the pre-execution memory image.
"""

from __future__ import annotations

from pathlib import Path

from jr100emu import debug_runner
from jr100emu.jr100.computer import JR100Computer


def test_parser_accepts_clear_regs_and_save_initial_memory(tmp_path) -> None:
    parser = debug_runner._build_argument_parser()
    args = parser.parse_args(
        [
            "--program",
            "dummy.prg",
            "--start",
            "0x0300",
            "--clear-regs",
            "--save-initial-memory",
            str(tmp_path / "image.bin"),
        ]
    )
    assert args.clear_regs is True
    assert args.save_initial_memory == str(tmp_path / "image.bin")


def test_clear_registers_resets_accumulators_index_and_flags() -> None:
    computer = JR100Computer()
    computer.tick(16)
    cpu = computer.cpu_core
    cpu.registers.acc_a = 0xAA
    cpu.registers.acc_b = 0xBB
    cpu.registers.index = 0x1234
    cpu.flags.carry_h = True
    cpu.flags.carry_i = True
    cpu.flags.carry_n = True
    cpu.flags.carry_z = True
    cpu.flags.carry_v = True
    cpu.flags.carry_c = True

    debug_runner._clear_registers(computer)

    assert cpu.registers.acc_a == 0x00
    assert cpu.registers.acc_b == 0x00
    assert cpu.registers.index == 0x0000
    assert debug_runner._ccr_byte(cpu.flags) == 0xC0


def test_save_memory_image_writes_full_64k(tmp_path) -> None:
    computer = JR100Computer()
    computer.tick(16)
    memory = computer.memory
    memory.store8(0x0300, 0x4C)
    memory.store8(0x3FFF, 0x99)  # top of standard main RAM

    target = Path(tmp_path) / "image.bin"
    debug_runner._save_memory_image(memory, target)

    data = target.read_bytes()
    assert len(data) == 0x10000
    assert data[0x0300] == 0x4C
    assert data[0x3FFF] == 0x99
    # ROM region reads through the same bus view the CPU sees
    assert data[0xFFFF] == memory.load8(0xFFFF)
