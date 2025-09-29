"""Headless regression checks for the STARFIRE demo program."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

from jr100emu.jr100.computer import JR100Computer

_HELPER_PATH = Path(__file__).resolve().parents[1] / "helpers" / "headless.py"
_SPEC = importlib.util.spec_from_file_location("headless_helper", _HELPER_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)  # type: ignore[arg-type]

KeyEvent = _MODULE.KeyEvent
run_program = _MODULE.run_program


STARFIRE_PATH = "datas/STARFIRE.prg"


SHIFT_ROW_BIT = (0, 1)
RETURN_ROW_BIT = (8, 3)


KEY_MAP = {
    "A": (1, 0),
    "U": (5, 1),
    "S": (1, 1),
    "R": (2, 3),
    "D": (1, 2),
    "0": (4, 4),
    "1": (3, 0),
    "2": (3, 1),
    "3": (3, 2),
    "4": (3, 3),
    "5": (3, 4),
    "6": (4, 0),
    "7": (4, 1),
    "8": (4, 2),
    "9": (4, 3),
    "K": (6, 2),
    "L": (6, 3),
    "M": (7, 3),
    ",": (7, 4),
    ".": (8, 0),
    ";": (6, 4),
    ":": (8, 2),
}


SHIFT_COMBOS = {
    "=": (8, 4),
    "(": (4, 2),
    "$": (3, 3),
    ")": (4, 3),
    "!": (3, 0),
    '"': (3, 1),
    "#": (3, 2),
    "%": (3, 4),
    "&": (4, 0),
    "'": (4, 1),
    "^": (4, 4),
    "?": (6, 2),
    "/": (6, 3),
    "+": (6, 4),
    "*": (8, 2),
    "_": (7, 3),
    "<": (7, 4),
    ">": (8, 0),
}


def _schedule_key(events, clock, row, bit, hold=1200):
    events.append(KeyEvent(clock=clock, row=row, bit=bit, pressed=True))
    events.append(KeyEvent(clock=clock + hold, row=row, bit=bit, pressed=False))
    return clock + hold + 200


def generate_command_events(command: str, *, start_clock: int = 20_000, interval: int = 2_000) -> list[KeyEvent]:
    events: list[KeyEvent] = []
    clock = start_clock
    for char in command:
        if char == "\n":
            clock = _schedule_key(events, clock, *RETURN_ROW_BIT)
            clock += interval
            continue
        key = char.upper()
        if key in SHIFT_COMBOS:
            clock_shift = clock
            events.append(KeyEvent(clock=clock_shift, row=SHIFT_ROW_BIT[0], bit=SHIFT_ROW_BIT[1], pressed=True))
            clock_shift += 300
            clock_shift = _schedule_key(events, clock_shift, *SHIFT_COMBOS[key])
            events.append(KeyEvent(clock=clock_shift, row=SHIFT_ROW_BIT[0], bit=SHIFT_ROW_BIT[1], pressed=False))
            clock = clock_shift + interval
            continue
        if key not in KEY_MAP:
            raise ValueError(f"Unsupported character: {char}")
        clock = _schedule_key(events, clock, *KEY_MAP[key])
        clock += interval
    return events


def test_starfire_runs_without_entering_vram() -> None:
    computer, pc_history = run_program(
        STARFIRE_PATH,
        total_cycles=5_000_000,
        events=[],
        step_cycles=512,
        warmup_cycles=20_000,
    )

    assert all(not (0xC000 <= pc < 0xC400) for pc in pc_history)
    assert not computer.cpu_core.status.fetch_wai
    via_state = computer.via._state  # type: ignore[attr-defined]
    assert via_state.IFR == 0
    assert via_state.IER == 0


@pytest.mark.xfail(reason="Keyboard matrix sequence for BASIC command injection under investigation")
def test_starfire_usr_command_executes() -> None:
    command = "A=USR($D00)\n"
    events = generate_command_events(command)
    total_cycles = 8_000_000

    computer, pc_history = run_program(
        STARFIRE_PATH,
        total_cycles=total_cycles,
        events=events,
        step_cycles=512,
        warmup_cycles=20_000,
    )

    assert any(0x0D00 <= pc < 0x0F00 for pc in pc_history), "USR routine was not entered"
    via_state = computer.via._state  # type: ignore[attr-defined]
    assert via_state.IER == 0


def test_starfire_usr_manual_jump_executes() -> None:
    computer = JR100Computer(rom_path="datas/jr100rom.prg", enable_audio=False)
    computer.load_user_program(STARFIRE_PATH)

    cpu = computer.cpu_core
    cpu.registers.program_counter = 0x0D00
    initial_pc = cpu.registers.program_counter

    cpu.execute(200)

    assert cpu.registers.program_counter != initial_pc
    assert 0x0D00 <= initial_pc < 0x1000
    assert not cpu.status.fetch_wai
