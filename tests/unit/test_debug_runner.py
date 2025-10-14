from __future__ import annotations

import io
from pathlib import Path

import pytest

from jr100emu import debug_runner


class DummyMemory:
    def __init__(self) -> None:
        self.values = {0x0000: 0x12, 0x0001: 0x34, 0x000F: 0xAB, 0x0010: 0xCD}

    def load8(self, address: int) -> int:
        return self.values.get(address & 0xFFFF, 0x00)


def test_parse_hex_accepts_prefixed_and_plain() -> None:
    assert debug_runner._parse_hex("0x0300") == 0x0300
    assert debug_runner._parse_hex("0300") == 0x0300


@pytest.mark.parametrize("value", ["", "0x10000", "xyz", "-1"])
def test_parse_hex_rejects_invalid(value: str) -> None:
    with pytest.raises(ValueError):
        debug_runner._parse_hex(value)


def test_parse_range_and_merge() -> None:
    rng = debug_runner._parse_range("0010:001F")
    assert rng.start == 0x0010
    assert rng.end == 0x001F
    merged = debug_runner._merge_ranges(
        [debug_runner.DumpRange(0x0000, 0x000F), debug_runner.DumpRange(0x0010, 0x0015)]
    )
    assert merged == [debug_runner.DumpRange(0x0000, 0x0015)]


def test_merge_ranges_defaults_to_full_memory() -> None:
    merged = debug_runner._merge_ranges([])
    assert merged == [debug_runner.DumpRange(0x0000, 0xFFFF)]


def test_format_hex_dump_renders_expected_table() -> None:
    memory = DummyMemory()
    dump = debug_runner._format_hex_dump(memory, [debug_runner.DumpRange(0x0000, 0x0010)])
    lines = dump.splitlines()
    assert lines[0].startswith("ADDR")
    assert lines[1].startswith("0000 12 34")
    assert lines[2].startswith("0010 CD 00")


def test_initialise_cpu_state_sets_pc_and_sp() -> None:
    class DummyCPU:
        def __init__(self) -> None:
            self.registers = type("Regs", (), {"program_counter": 0, "stack_pointer": 0})()

    class DummyComputer:
        def __init__(self) -> None:
            self.cpu_core = DummyCPU()

    comp = DummyComputer()
    debug_runner._initialise_cpu_state(comp, start_address=0x1234, stack_pointer=0x0244)
    assert comp.cpu_core.registers.program_counter == 0x1234
    assert comp.cpu_core.registers.stack_pointer == 0x0244
