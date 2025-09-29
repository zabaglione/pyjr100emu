"""Headless execution helpers for JR-100 programs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from jr100emu.jr100.computer import JR100Computer


@dataclass(frozen=True)
class KeyEvent:
    """Represents a keyboard event scheduled by clock count."""

    clock: int
    row: int
    bit: int
    pressed: bool


def run_program(
    program_path: str,
    *,
    total_cycles: int,
    events: Sequence[KeyEvent] | None = None,
    step_cycles: int = 512,
    rom_path: str = "datas/jr100rom.prg",
    warmup_cycles: int = 0,
) -> tuple[JR100Computer, List[int]]:
    """Execute a JR-100 program headlessly and capture PC history."""

    computer = JR100Computer(rom_path=rom_path, enable_audio=False)
    computer.load_user_program(program_path)

    pc_history: List[int] = []
    keyboard = computer.hardware.keyboard
    scheduled = sorted(events or [], key=lambda evt: evt.clock)
    index = 0

    if warmup_cycles:
        while computer.clock_count < warmup_cycles:
            computer.tick(step_cycles)

    target_clock = computer.clock_count + total_cycles
    while computer.clock_count < target_clock:
        while index < len(scheduled) and scheduled[index].clock <= computer.clock_count:
            evt = scheduled[index]
            if evt.pressed:
                keyboard.press(evt.row, evt.bit)
            else:
                keyboard.release(evt.row, evt.bit)
            index += 1

        computer.tick(step_cycles)
        pc_history.append(computer.cpu_core.registers.program_counter)

    return computer, pc_history
