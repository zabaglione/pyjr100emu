"""Lightweight hexadecimal memory dump viewer."""

from __future__ import annotations

from dataclasses import dataclass

from jr100emu.memory import MemorySystem


@dataclass
class _ViewState:
    base_address: int = 0x0000
    input_active: bool = False
    input_buffer: str = ""
    message: str = ""


class HexViewer:
    """16x16-byte memory dump overlay toggled with F2."""

    ROWS = 16
    COLS = 16
    PAGE_BYTES = ROWS * COLS
    MAX_ADDRESS = 0x10000

    def __init__(self, computer) -> None:
        self.computer = computer
        self.active: bool = False
        self._state = _ViewState()
        self._font = None
        self._line_height = 0

    # ------------------------------------------------------------------
    def open(self) -> None:
        self.active = True
        self._state = _ViewState(
            base_address=self._state.base_address & 0xFFF0,
            message="F2/ESC: close    Enter: address input",
        )

    def close(self) -> None:
        self.active = False
        self._state.input_active = False
        self._state.input_buffer = ""
        self._state.message = ""

    def toggle(self) -> bool:
        if self.active:
            self.close()
            return False
        self.open()
        return True

    # ------------------------------------------------------------------
    def handle_event(self, event) -> bool:
        import pygame  # type: ignore

        if not self.active:
            return False

        if event.type != pygame.KEYDOWN:
            return False

        key = event.key

        if self._state.input_active:
            if key == pygame.K_RETURN:
                self._apply_input()
                return True
            if key == pygame.K_ESCAPE:
                self._state.input_active = False
                self._state.input_buffer = ""
                self._state.message = "Address input cancelled"
                return True
            if key == pygame.K_BACKSPACE:
                self._state.input_buffer = self._state.input_buffer[:-1]
                self._state.message = f"Enter address: {self._state.input_buffer or '_'}"
                return True
            ch = event.unicode.upper() if event.unicode else ""
            if ch in "0123456789ABCDEF":
                if len(self._state.input_buffer) < 4:
                    self._state.input_buffer += ch
                    self._state.message = f"Enter address: {self._state.input_buffer}"
                return True
            return True

        if key in (pygame.K_F2, pygame.K_ESCAPE):
            self.close()
            return True
        if key == pygame.K_RETURN:
            self._begin_input()
            return True
        if key in (pygame.K_UP, pygame.K_k):
            self._move_base(-0x10)
            return True
        if key in (pygame.K_DOWN, pygame.K_j):
            self._move_base(0x10)
            return True
        if key == pygame.K_PAGEUP:
            self._move_base(-self.PAGE_BYTES)
            return True
        if key == pygame.K_PAGEDOWN:
            self._move_base(self.PAGE_BYTES)
            return True
        if key == pygame.K_HOME:
            self._set_base(0x0000)
            return True
        if key == pygame.K_END:
            self._set_base(self.MAX_ADDRESS - self.PAGE_BYTES)
            return True
        if key in (pygame.K_LEFT, pygame.K_h):
            self._move_base(-1)
            return True
        if key in (pygame.K_RIGHT, pygame.K_l):
            self._move_base(1)
            return True

        return True

    # ------------------------------------------------------------------
    def render(self, screen) -> None:
        if not self.active:
            return

        import pygame  # type: ignore

        self._ensure_font()

        width, height = screen.get_size()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 192))

        x = 48
        y = 48

        header = "ADDR " + " ".join(f"+{col:X}" for col in range(self.COLS))
        header_surface = self._font.render(header, True, (255, 215, 0))
        overlay.blit(header_surface, (x, y))
        y += self._line_height + 4

        memory = self._memory()
        base = self._state.base_address
        for row in range(self.ROWS):
            addr = (base + row * self.COLS) & 0xFFFF
            bytes_values = [
                memory.load8(addr + col) & 0xFF for col in range(self.COLS)
            ]
            line = f"{addr:04X} " + " ".join(f"{value:02X}" for value in bytes_values)
            line_surface = self._font.render(line, True, (220, 220, 220))
            overlay.blit(line_surface, (x, y))
            y += self._line_height

        y += self._line_height

        info_lines = [
            f"BASE: {self._state.base_address:04X}",
            "Controls:",
            "  Up/Down = ±16     Left/Right = ±1",
            "  PgUp/PgDn = ±256  Home/End = First/Last",
        ]
        if self._state.input_active:
            entered = self._state.input_buffer or "_"
            info_lines.append(f"Enter address: {entered} (4 hex digits, Enter to confirm)")
        if self._state.message:
            info_lines.append(self._state.message)

        for line in info_lines:
            surface = self._font.render(line, True, (173, 216, 230))
            overlay.blit(surface, (x, y))
            y += self._line_height

        screen.blit(overlay, (0, 0))

    # ------------------------------------------------------------------
    def _ensure_font(self) -> None:
        if self._font is not None:
            return

        import pygame  # type: ignore

        pygame.font.init()
        self._font = pygame.font.SysFont("Courier", 20)
        self._line_height = self._font.get_linesize()

    def _memory(self) -> MemorySystem:
        memory = getattr(self.computer, "memory", None)
        if isinstance(memory, MemorySystem):
            return memory
        return self.computer.hardware.memory  # type: ignore[return-value]

    def _move_base(self, delta: int) -> None:
        new_base = self._state.base_address + delta
        self._set_base(new_base)

    def _set_base(self, address: int) -> None:
        aligned = max(0, min(address, self.MAX_ADDRESS - self.PAGE_BYTES))
        aligned &= 0xFFF0
        self._state.base_address = aligned
        self._state.message = f"Base address set to {aligned:04X}"

    def _begin_input(self) -> None:
        self._state.input_active = True
        self._state.input_buffer = ""
        self._state.message = "Address input: type 4 hex digits and press Enter (ESC to cancel)"

    def _apply_input(self) -> None:
        buffer = self._state.input_buffer.strip()
        if not buffer:
            self._state.message = "No address entered"
            self._state.input_active = False
            return
        try:
            value = int(buffer, 16)
        except ValueError:
            self._state.message = "Invalid hexadecimal value"
            self._state.input_buffer = ""
            return
        self._set_base(value & 0xFFFF)
        self._state.input_active = False
        self._state.input_buffer = ""


__all__ = ["HexViewer"]
