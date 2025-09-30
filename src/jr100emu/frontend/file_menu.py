"""Simple pygame-based file selection menu."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional, Tuple


class FileMenu:
    """Lightweight file picker drawn with pygame."""

    VISIBLE_ITEMS = 12
    SUPPORTED_SUFFIXES = (".bas", ".BAS", ".txt", ".TXT", ".prg", ".PRG", ".prog", ".PROG")
    AXIS_REPEAT_DELAY_MS = 220
    AXIS_THRESHOLD = 0.55

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.active: bool = False
        self.entries: List[Path] = []
        self.selected_index: int = 0
        self._scroll: int = 0
        self._font = None
        self._line_height = 18
        self._message: str = ""
        self._last_axis_move_ms: int = 0

    # ------------------------------------------------------------------
    def open(self) -> None:
        self.refresh()
        self.active = True

    def close(self) -> None:
        self.active = False
        self._message = ""

    def toggle(self) -> bool:
        if self.active:
            self.close()
            return False
        self.open()
        return True

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        previous = None
        if self.entries and 0 <= self.selected_index < len(self.entries):
            previous = self.entries[self.selected_index]

        suffixes = {s.lower() for s in self.SUPPORTED_SUFFIXES}
        entries: List[Path] = []
        if self.root.exists() and self.root.is_dir():
            try:
                children = list(self.root.iterdir())
            except OSError:
                children = []
            if self.root.parent != self.root:
                entries.append(self.root.parent)
            directories = sorted((c for c in children if c.is_dir()), key=lambda p: p.name.lower())
            files = sorted(
                (
                    c
                    for c in children
                    if c.is_file() and c.suffix.lower() in suffixes
                ),
                key=lambda p: p.name.lower(),
            )
            entries.extend(directories)
            entries.extend(files)

        self.entries = entries

        if self.entries:
            if previous in self.entries:
                self.selected_index = self.entries.index(previous)
            else:
                self.selected_index = 0
        else:
            self.selected_index = 0

        if self.selected_index < self._scroll:
            self._scroll = self.selected_index
        elif self.selected_index >= self._scroll + self.VISIBLE_ITEMS:
            self._scroll = max(0, self.selected_index - self.VISIBLE_ITEMS + 1)
        else:
            self._scroll = min(self._scroll, max(0, self.selected_index - self.VISIBLE_ITEMS + 1))

    # ------------------------------------------------------------------
    def handle_event(self, event) -> Optional[Tuple[str, Optional[Path]]]:
        import pygame  # type: ignore

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_F1):
                self.close()
                return ("close", None)
            if event.key == pygame.K_r:
                self.refresh()
                self._message = "Reloaded list"
                return None
            if event.key in (pygame.K_DOWN, pygame.K_j):
                self._move_selection(1)
                return None
            if event.key in (pygame.K_UP, pygame.K_k):
                self._move_selection(-1)
                return None
            if event.key == pygame.K_PAGEUP:
                self._move_selection(-(self.VISIBLE_ITEMS))
                return None
            if event.key == pygame.K_PAGEDOWN:
                self._move_selection(self.VISIBLE_ITEMS)
                return None
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return self._activate_selected()

        if event.type == pygame.JOYBUTTONDOWN:
            if event.button == 0:
                return self._activate_selected()
            if event.button in (1, 9):
                self.close()
                return ("close", None)
            if event.button == 3:
                self.refresh()
                self._message = "Reloaded list"
                return None

        if event.type == pygame.JOYHATMOTION:
            x, y = event.value
            if y == 1:
                self._move_selection(-1)
            elif y == -1:
                self._move_selection(1)
            elif x == -1:
                self._move_selection(-(self.VISIBLE_ITEMS))
            elif x == 1:
                self._move_selection(self.VISIBLE_ITEMS)
            return None

        if event.type == pygame.JOYAXISMOTION:
            now = pygame.time.get_ticks()
            if now - self._last_axis_move_ms < self.AXIS_REPEAT_DELAY_MS:
                return None
            if event.axis == 1 and abs(event.value) >= self.AXIS_THRESHOLD:
                self._last_axis_move_ms = now
                self._move_selection(-1 if event.value < 0 else 1)
                return None
            if event.axis == 0 and abs(event.value) >= self.AXIS_THRESHOLD:
                self._last_axis_move_ms = now
                self._move_selection(-(self.VISIBLE_ITEMS) if event.value < 0 else self.VISIBLE_ITEMS)
                return None
        return None

    def _move_selection(self, delta: int) -> None:
        if not self.entries:
            return
        self.selected_index = max(0, min(self.selected_index + delta, len(self.entries) - 1))
        if self.selected_index < self._scroll:
            self._scroll = self.selected_index
        elif self.selected_index >= self._scroll + self.VISIBLE_ITEMS:
            self._scroll = self.selected_index - self.VISIBLE_ITEMS + 1

    def _activate_selected(self) -> Optional[Tuple[str, Optional[Path]]]:
        if not self.entries:
            self._message = "No entries"
            return None
        target = self.entries[self.selected_index]
        if target.is_dir():
            self.root = target
            self.refresh()
            self._message = f"Directory: {self.root}"
            return None
        if not target.exists():
            self._message = "Missing entry"
            return None
        suffixes = {s.lower() for s in self.SUPPORTED_SUFFIXES}
        if target.suffix.lower() not in suffixes:
            self._message = "Unsupported file"
            return None
        return ("load", target.resolve())

    # ------------------------------------------------------------------
    def render(self, screen) -> None:
        if not self.active:
            return
        import pygame  # type: ignore

        self._ensure_font()
        width, height = screen.get_size()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))

        title = f"Load BASIC/PROG from {self.root}" if self.entries else f"No BASIC files in {self.root}"
        title_surface = self._font.render(title, True, (255, 255, 180))
        overlay.blit(title_surface, (60, 60))

        info_surface = self._font.render("ENTER: load  R: refresh  ESC/F1: close", True, (200, 200, 200))
        overlay.blit(info_surface, (60, 60 + self._line_height + 8))

        start_y = 60 + (self._line_height + 8) * 2
        visible = self.entries[self._scroll:self._scroll + self.VISIBLE_ITEMS]
        for row, path in enumerate(visible):
            display_name = self._format_entry_name(path)
            color = (255, 255, 0) if (self._scroll + row) == self.selected_index else (220, 220, 220)
            text_surface = self._font.render(display_name, True, color)
            overlay.blit(text_surface, (80, start_y + row * (self._line_height + 4)))

        if self._message:
            msg_surface = self._font.render(self._message, True, (173, 216, 230))
            overlay.blit(msg_surface, (60, start_y + self.VISIBLE_ITEMS * (self._line_height + 4)))

        screen.blit(overlay, (0, 0))

    def _ensure_font(self) -> None:
        if self._font is not None:
            return
        import pygame  # type: ignore

        pygame.font.init()
        self._font = pygame.font.SysFont("Courier", 20)
        self._line_height = self._font.get_linesize()

    def _format_entry_name(self, path: Path) -> str:
        if path.is_dir():
            if path == self.root.parent and path != self.root:
                return "[..]"
            name = path.name or str(path)
            return f"[{name}]"
        return path.name


__all__ = ["FileMenu"]
