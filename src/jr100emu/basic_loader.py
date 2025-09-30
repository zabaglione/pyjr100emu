"""Helpers to load BASIC text into ROM BASIC after initialization."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from jr100emu.emulator.file.program import load_basic_text, ProgramInfo
from jr100emu.jr100.computer import JR100Computer


class BasicLoader:
    """Utility to coordinate BASIC loading after ROM sign-on."""

    def __init__(self, computer: JR100Computer) -> None:
        self.computer = computer
        self._pending_path: Optional[Path] = None
        self._last_info: Optional[ProgramInfo] = None

    def queue(self, path: str | Path) -> None:
        self._pending_path = Path(path)
        # keep last_info for inspection until new program is processed

    @property
    def pending(self) -> bool:
        return self._pending_path is not None

    @property
    def loaded_info(self) -> Optional[ProgramInfo]:
        return self._last_info

    def process(self) -> Optional[ProgramInfo]:
        if self._pending_path is None:
            return None
        info = self.computer.load_user_program(self._pending_path)
        self._pending_path = None
        self._last_info = info
        return info
