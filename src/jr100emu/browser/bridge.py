"""Pyodide bridge with a small set of module-level callable functions."""

from __future__ import annotations

from typing import Any

from jr100emu.browser.core import BrowserCore


_core: BrowserCore | None = None


def _require_core() -> BrowserCore:
    if _core is None:
        raise RuntimeError("ROM is not loaded")
    return _core


def create_core(values: Any) -> dict[str, Any]:
    global _core
    _core = BrowserCore(bytes(values))
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


def state() -> dict[str, Any]:
    return dict(_require_core().state())
