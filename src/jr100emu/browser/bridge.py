"""Pyodide bridge with a small set of module-level callable functions."""

from __future__ import annotations

from array import array
import sys
from typing import Any

from jr100emu.browser.core import BrowserCore


_core: BrowserCore | None = None


def _require_core() -> BrowserCore:
    if _core is None:
        raise RuntimeError("ROM is not loaded")
    return _core


def create_core(values: Any, extended_ram: bool = False) -> dict[str, Any]:
    global _core
    _core = BrowserCore(bytes(values), extended_ram=bool(extended_ram))
    return dict(_core.rom_info)


def reset() -> None:
    _require_core().reset()


def run_frame() -> bytes:
    return _require_core().run_frame()


def set_key(row: int, bit: int, pressed: bool) -> None:
    _require_core().set_key(row, bit, pressed)


def clear_keys() -> None:
    _require_core().clear_keys()


def set_joystick_mask(mask: int) -> None:
    _require_core().set_joystick_mask(mask)


def frame_buffer() -> bytes:
    return _require_core().frame_buffer()


def audio_buffer() -> bytes:
    samples = array("h", _require_core().audio_buffer())
    if sys.byteorder != "little":
        samples.byteswap()
    return samples.tobytes()


def font_data() -> bytes:
    return _require_core().font_data()


def normal_key_codes() -> bytes:
    return _require_core().normal_key_codes()


def shift_key_codes() -> bytes:
    return _require_core().shift_key_codes()


def load_program(values: Any, filename: str = "") -> dict[str, Any]:
    return _require_core().load_program(bytes(values), filename=filename)


def run_entry(address: int) -> str:
    return _require_core().run_entry(address)


def debug_state() -> dict[str, Any]:
    return _require_core().debug_state()


def read_memory(start: int, length: int) -> list[int]:
    return _require_core().read_memory(start, length)


def set_breakpoints(addresses: Any) -> None:
    _require_core().set_breakpoints([int(address) for address in addresses])


def continue_execution() -> None:
    _require_core().continue_execution()


def step_instruction() -> dict[str, Any]:
    return _require_core().step_instruction()


def state() -> dict[str, Any]:
    return dict(_require_core().state())
