"""JR-100 display model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List


@dataclass
class JR100Display:
    WIDTH_CHARS: int = 32
    HEIGHT_CHARS: int = 24
    PPC: int = 8
    FONT_NORMAL: int = 0
    FONT_USER_DEFINED: int = 1

    color_map: List[List[int]] = field(default_factory=lambda: [[0x000000] * 256, [0xFFFFFF] * 256])
    character_rom: List[int] = field(default_factory=lambda: [0x00] * (256 * 8))
    user_defined_ram: List[int] = field(default_factory=lambda: [0x00] * (128 * 8))
    video_ram: List[int] = field(default_factory=lambda: [0x00] * (32 * 24))
    _fonts: List[List[List[int]]] = field(default_factory=lambda: [[[0] * (8 * 8) for _ in range(256)] for _ in range(2)])
    _current_font: int = FONT_NORMAL

    def __post_init__(self) -> None:
        self.rebuild_fonts()

    @property
    def current_font(self) -> int:
        return self._current_font

    def set_current_font(self, plane: int) -> None:
        if plane not in (self.FONT_NORMAL, self.FONT_USER_DEFINED):
            raise ValueError("invalid font plane")
        self._current_font = plane

    # ------------------------------------------------------------------
    # Memory loaders
    # ------------------------------------------------------------------
    def load_character_rom(self, data: Iterable[int]) -> None:
        values = list(data)
        if len(values) != 256 * self.PPC:
            raise ValueError("character ROM must be 2048 bytes")
        self.character_rom = [value & 0xFF for value in values]
        self.rebuild_fonts()

    def load_user_defined_ram(self, data: Iterable[int]) -> None:
        values = list(data)
        if len(values) != 128 * self.PPC:
            raise ValueError("user defined RAM must be 1024 bytes")
        self.user_defined_ram = [value & 0xFF for value in values]
        self._rebuild_user_defined_fonts()

    def set_video_ram(self, data: Iterable[int]) -> None:
        values = list(data)
        if len(values) != self.WIDTH_CHARS * self.HEIGHT_CHARS:
            raise ValueError("video RAM must be 768 bytes")
        self.video_ram = [value & 0xFF for value in values]

    def write_video_ram(self, index: int, value: int) -> None:
        if not (0 <= index < len(self.video_ram)):
            raise ValueError("video RAM index out of range")
        self.video_ram[index] = value & 0xFF

    # ------------------------------------------------------------------
    # Font generation
    # ------------------------------------------------------------------
    def rebuild_fonts(self) -> None:
        for code in range(256):
            self._rebuild_font_entry(self.FONT_NORMAL, code)
            self._rebuild_font_entry(self.FONT_USER_DEFINED, code)

    def _rebuild_user_defined_fonts(self) -> None:
        for code in range(128, 256):
            self._rebuild_font_entry(self.FONT_USER_DEFINED, code)

    def _rebuild_font_entry(self, plane: int, code: int) -> None:
        for line in range(self.PPC):
            value = self._glyph_byte(plane, code, line)
            for bit in range(self.PPC):
                pixel = (value >> (7 - bit)) & 0x01
                color = self.color_map[pixel][code]
                index = line * self.PPC + bit
                self._fonts[plane][code][index] = color

    def _glyph_byte(self, plane: int, code: int, line: int) -> int:
        if plane == self.FONT_NORMAL:
            if code < 128:
                return self.character_rom[code * self.PPC + line]
            base = self.character_rom[(code - 128) * self.PPC + line]
            return base ^ 0xFF
        if plane == self.FONT_USER_DEFINED:
            if code < 128:
                return self.character_rom[code * self.PPC + line]
            return self.user_defined_ram[(code - 128) * self.PPC + line]
        raise ValueError("invalid plane")

    def update_font(self, code: int, line: int, value: int) -> None:
        if not (0 <= code < 128 and 0 <= line < self.PPC):
            raise ValueError("code/line out of range")
        self.user_defined_ram[code * self.PPC + line] = value & 0xFF
        self._rebuild_font_entry(self.FONT_USER_DEFINED, code + 128)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def render_pixels(self) -> List[List[int]]:
        width = self.WIDTH_CHARS * self.PPC
        height = self.HEIGHT_CHARS * self.PPC
        pixels = [[0x000000 for _ in range(width)] for _ in range(height)]
        for y_char in range(self.HEIGHT_CHARS):
            for x_char in range(self.WIDTH_CHARS):
                code = self.video_ram[y_char * self.WIDTH_CHARS + x_char] & 0xFF
                glyph = self._fonts[self._current_font][code]
                for line in range(self.PPC):
                    row_index = y_char * self.PPC + line
                    start = x_char * self.PPC
                    pixels[row_index][start:start + self.PPC] = glyph[line * self.PPC:(line + 1) * self.PPC]
        return pixels

    def render_pygame_surface(self, scaling: int = 1):
        """Render the display into a pygame Surface.

        Parameters
        ----------
        scaling:
            Integer scale factor applied to both axes.

        Returns
        -------
        pygame.Surface
            RGB surface representing the current screen.

        Raises
        ------
        RuntimeError
            If pygame is not available.
        """

        if scaling <= 0:
            raise ValueError("scaling factor must be positive")

        try:
            import pygame  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("pygame is required for render_pygame_surface") from exc

        base_width = self.WIDTH_CHARS * self.PPC
        base_height = self.HEIGHT_CHARS * self.PPC
        surface = pygame.Surface((base_width * scaling, base_height * scaling))
        pixels = self.render_pixels()
        surface.lock()
        try:
            if scaling == 1:
                pxarray = pygame.PixelArray(surface)
                for y, row in enumerate(pixels):
                    pxarray[y][:] = row
                del pxarray
            else:
                for y, row in enumerate(pixels):
                    for x, color in enumerate(row):
                        surface.fill(color, (x * scaling, y * scaling, scaling, scaling))
        finally:
            surface.unlock()
        return surface

    # ------------------------------------------------------------------
    # Color map utilities
    # ------------------------------------------------------------------
    def set_color_map_entry(self, plane: int, index: int, color: int) -> None:
        self.color_map[plane][index] = color & 0xFFFFFF
        self._rebuild_font_entry(plane, index)
