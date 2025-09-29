"""Headless regression checks for the STARFIRE demo program."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

_HELPER_PATH = Path(__file__).resolve().parents[1] / "helpers" / "headless.py"
_SPEC = importlib.util.spec_from_file_location("headless_helper", _HELPER_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None and _SPEC.loader is not None
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)  # type: ignore[arg-type]

KeyEvent = _MODULE.KeyEvent
run_program = _MODULE.run_program


STARFIRE_PATH = "datas/STARFIRE.prg"


def test_starfire_runs_without_entering_vram() -> None:
    computer, pc_history = run_program(
        STARFIRE_PATH,
        total_cycles=5_000_000,
        events=[],
        step_cycles=512,
    )

    assert all(not (0xC000 <= pc < 0xC400) for pc in pc_history)
    assert not computer.cpu_core.status.fetch_wai
    via_state = computer.via._state  # type: ignore[attr-defined]
    assert via_state.IFR == 0
    assert via_state.IER == 0
