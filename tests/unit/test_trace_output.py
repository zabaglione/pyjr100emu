"""Tests for the instruction-boundary trace output of the debug runner."""

from __future__ import annotations

import io
import re

from jr100emu import debug_runner
from jr100emu.cpu.cpu import CPUFlags
from jr100emu.jr100.computer import JR100Computer


TRACE_LINE_PATTERN = (
    r"S n=1 clk=\d+ pc=0300 a=12 b=34 ix=5678 sp=0244 cc=[0-9A-F]{2}"
    r" ora=[0-9A-F]{2} orb=[0-9A-F]{2} ddra=[0-9A-F]{2} ddrb=[0-9A-F]{2}"
    r" acr=[0-9A-F]{2} pcr=[0-9A-F]{2} ifr=[0-9A-F]{2} ier=[0-9A-F]{2} sr=[0-9A-F]{2}"
    r" t1=[0-9A-F]{4} t1l=[0-9A-F]{4} t2=[0-9A-F]{4} t2l=[0-9A-F]{4}"
)


def _flush_reset(computer: JR100Computer) -> None:
    computer.tick(16)


def test_ccr_byte_packs_flags_in_mb8861_order() -> None:
    flags = CPUFlags(
        carry_h=True,
        carry_i=False,
        carry_n=False,
        carry_z=True,
        carry_v=False,
        carry_c=True,
    )
    assert debug_runner._ccr_byte(flags) == 0xC0 | 0x20 | 0x04 | 0x01


def test_format_trace_line_has_fixed_field_order() -> None:
    computer = JR100Computer()
    _flush_reset(computer)
    cpu = computer.cpu_core
    cpu.registers.program_counter = 0x0300
    cpu.registers.acc_a = 0x12
    cpu.registers.acc_b = 0x34
    cpu.registers.index = 0x5678
    cpu.registers.stack_pointer = 0x0244

    line = debug_runner._format_trace_line(computer, sample_index=1)

    assert re.fullmatch(TRACE_LINE_PATTERN, line), line


def test_traced_execution_emits_one_sample_per_instruction() -> None:
    computer = JR100Computer()
    _flush_reset(computer)
    memory = computer.memory
    # INCA; INCA; BRA * (self-loop)
    memory.store8(0x0300, 0x4C)
    memory.store8(0x0301, 0x4C)
    memory.store8(0x0302, 0x20)
    memory.store8(0x0303, 0xFE)
    debug_runner._initialise_cpu_state(
        computer, start_address=0x0300, stack_pointer=0x0244
    )
    computer.cpu_core.registers.acc_a = 0x00

    sink = io.StringIO()
    debug_runner._execute_program(
        computer,
        max_cycles=10,
        breakpoints=[],
        max_seconds=None,
        trace_sink=sink,
    )

    lines = [line for line in sink.getvalue().splitlines() if line.startswith("S ")]
    assert len(lines) >= 3
    assert lines[0].startswith("S n=1 ")
    assert " pc=0301 " in lines[0]
    assert " a=01 " in lines[0]
    assert lines[1].startswith("S n=2 ")
    assert " pc=0302 " in lines[1]
    assert " a=02 " in lines[1]
    # clk must be strictly increasing across samples
    clks = [int(re.search(r" clk=(\d+) ", line).group(1)) for line in lines]
    assert clks == sorted(clks) and len(set(clks)) == len(clks)


def test_argument_parser_accepts_trace_option(tmp_path) -> None:
    parser = debug_runner._build_argument_parser()
    args = parser.parse_args(
        [
            "--program",
            "dummy.prg",
            "--start",
            "0x0300",
            "--trace",
            str(tmp_path / "trace.txt"),
        ]
    )
    assert args.trace == str(tmp_path / "trace.txt")
