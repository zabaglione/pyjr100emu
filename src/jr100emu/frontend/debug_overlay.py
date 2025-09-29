"""Debug overlay rendering for the pygame demo."""

from __future__ import annotations

from collections import deque
from typing import Iterable, Optional, List

from jr100emu.memory import MemorySystem
from jr100emu.frontend.snapshot_db import SnapshotDatabase, SNAPSHOT_SLOTS, DEFAULT_SLOT


class DebugOverlay:
    """Collects and renders debug information for the JR-100 demo."""

    TRACE_LENGTH = 32
    STACK_BYTES = 8
    INSTRUCTIONS = [
        "ESC: toggle debug",
        "SPACE: resume",
        "N: step",
        "S: snapshot",
        "R: restore",
        "C: edit comment",
        "D: delete snapshot",
        "1-4 / UP/DOWN: select slot",
        "[/]: history nav",
        "P: preview history",
        "L: load history",
        "Q: quit",
    ]

    def __init__(self, computer) -> None:
        self._computer = computer
        self._trace: deque[int] = deque(maxlen=self.TRACE_LENGTH)
        self._font = None
        self._line_height = 0
        self._cached_cpu_lines: list[str] = []
        self._cached_via_lines: list[str] = []
        self._cached_stack_lines: list[str] = []
        self._cached_program: list[str] = []
        self._vram_surface = None
        self._status_message: str = ""
        self._snapshot_available: bool = False
        self._slot_name: str = DEFAULT_SLOT
        self._meta_db = SnapshotDatabase()
        self._history_entries: List[HistoryEntry] = self._meta_db.list_history()
        self._selected_index = SNAPSHOT_SLOTS.index(DEFAULT_SLOT)
        self._history_index: int = 0
        self._history_offset: int = 0
        self._comment_buffer: Optional[str] = None
        self._preview_lines: List[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def record_execution(self, pc: int) -> None:
        """Record the latest program counter for trace display."""

        self._trace.append(pc & 0xFFFF)

    def capture_state(self) -> None:
        """Snapshot CPU/VIA/stack state for later rendering."""

        cpu = getattr(self._computer, "cpu_core", None)
        via = getattr(self._computer, "via", None)
        memory = getattr(self._computer, "memory", None)
        program_info = getattr(self._computer, "program_info", None)

        self._cached_cpu_lines = self._snapshot_cpu(cpu)
        self._cached_stack_lines = self._snapshot_stack(cpu, memory)
        self._cached_via_lines = self._snapshot_via(via)
        self._cached_program = self._snapshot_program(program_info)
        self._vram_surface = None  # refresh lazily

    def render(self, screen) -> None:
        """Render the overlay onto the given pygame surface."""

        import pygame  # type: ignore

        self._ensure_font()
        self.capture_state()
        self._meta_db = SnapshotDatabase()
        self._history_entries = self._meta_db.list_history()
        if self._history_entries:
            self._history_index %= len(self._history_entries)
        else:
            self._history_index = 0

        overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 196))

        x_cursor = 24
        y_cursor = 24
        column_gap = max(12, self._line_height // 2)

        left_sections = [
            ("CPU", self._cached_cpu_lines),
            ("Stack", self._cached_stack_lines),
            ("Program", self._cached_program),
        ]
        left_width = self._measure_sections(left_sections) + 32

        if self._font is not None and self._status_message:
            status_surface = self._font.render(self._status_header(), True, (173, 216, 230))
            overlay.blit(status_surface, (x_cursor, y_cursor))
            y_cursor += self._line_height + 4

        y_cursor = self._render_section(overlay, x_cursor, y_cursor, "CPU", self._cached_cpu_lines)
        y_cursor = self._render_section(overlay, x_cursor, y_cursor + column_gap, "Stack", self._cached_stack_lines)
        y_cursor = self._render_section(overlay, x_cursor, y_cursor + column_gap, "Program", self._cached_program)

        via_y = 24
        via_x = x_cursor + left_width
        via_y = self._render_section(overlay, via_x, via_y, "VIA", self._cached_via_lines)

        trace_x = via_x
        trace_y = via_y + column_gap
        trace_lines = self._format_trace_lines()
        self._render_section(overlay, trace_x, trace_y, "Trace", trace_lines)

        help_x = via_x
        help_y = trace_y + column_gap + max(len(trace_lines), 1) * self._line_height
        self._render_section(overlay, help_x, help_y, "Controls", self.INSTRUCTIONS)

        slots_lines = []
        for idx, meta in enumerate(self._meta_db.list_slots()):
            marker = ">" if idx == self._selected_index else " "
            timestamp = meta.format_timestamp() if meta.timestamp else "(empty)"
            slots_lines.append(f"{marker} {meta.slot}: {meta.comment} @ {timestamp}")
        slots_y = help_y + column_gap + len(self.INSTRUCTIONS) * self._line_height
        self._render_section(overlay, help_x, slots_y, "Slots", slots_lines)

        history_window = self._history_entries[self._history_offset:self._history_offset + 10]
        history_lines: List[str] = []
        for idx, entry in enumerate(history_window):
            marker = "*" if idx == self._history_index else " "
            history_lines.append(
                f"{marker} {entry.slot} {entry.format_timestamp()} {entry.comment}"
            )
        history_y = slots_y + column_gap + max(len(slots_lines), 1) * self._line_height
        self._render_section(
            overlay,
            help_x,
            history_y,
            "History",
            history_lines or ["(no history)"]
        )

        vram_preview = self._render_vram_preview()
        if vram_preview is not None:
            screen_rect = screen.get_rect()
            pos_x = screen_rect.width - vram_preview.get_width() - 24
            pos_y = 24
            overlay.blit(vram_preview, (pos_x, pos_y))
            label = self._font.render("VRAM", True, (200, 200, 200))
            overlay.blit(label, (pos_x, pos_y + vram_preview.get_height() + 8))

        screen.blit(overlay, (0, 0))

        if self._preview_lines:
            import pygame  # type: ignore

            width = screen.get_width() - 80
            height = self._line_height * (len(self._preview_lines) + 1)
            x = 40
            y = history_y + column_gap + max(len(history_lines), 1) * self._line_height
            panel = pygame.Surface((width, height), pygame.SRCALPHA)
            panel.fill((30, 30, 30, 200))
            screen.blit(panel, (x, y))
            for idx, line in enumerate(self._preview_lines):
                rendered = self._font.render(line, True, (200, 240, 255))
                screen.blit(rendered, (x + 12, y + 6 + idx * self._line_height))

        if self._comment_buffer is not None:
            import pygame  # type: ignore

            width = screen.get_width() - 80
            lines = self._comment_buffer.split("\n") or [""]
            max_lines = 4
            render_lines = lines[-max_lines:]
            height = self._line_height * (len(render_lines) + 2)
            x = 40
            y = screen.get_height() - height - 40
            panel = pygame.Surface((width, height), pygame.SRCALPHA)
            panel.fill((20, 20, 20, 220))
            screen.blit(panel, (x, y))
            prompt = self._font.render("Comment (Shift+Enter newline):", True, (255, 215, 0))
            screen.blit(prompt, (x + 12, y + 6))
            for idx, line in enumerate(render_lines):
                suffix = "_" if idx == len(render_lines) - 1 else ""
                text_surface = self._font.render(line + suffix, True, (230, 230, 230))
                screen.blit(text_surface, (x + 12, y + 6 + self._line_height * (idx + 1)))

    def get_trace(self) -> list[int]:
        """Expose a copy of the recent trace for tests."""

        return list(self._trace)

    def set_status(self, message: str) -> None:
        self._status_message = message

    def set_snapshot_available(self, available: bool) -> None:
        self._snapshot_available = available

    def set_slot_name(self, slot: str) -> None:
        self._slot_name = slot
        self._meta_db = SnapshotDatabase()
        if slot in SNAPSHOT_SLOTS:
            self._selected_index = SNAPSHOT_SLOTS.index(slot)

    def update_metadata(self, slot: str, comment: str) -> None:
        self._meta_db.set_slot(slot, comment=comment)
        self.set_slot_name(slot)
        self.set_snapshot_available(True)

    def set_comment_buffer(self, buffer: Optional[str]) -> None:
        self._comment_buffer = buffer

    def move_selection(self, direction: int) -> str:
        self._selected_index = (self._selected_index + direction) % len(SNAPSHOT_SLOTS)
        slot = SNAPSHOT_SLOTS[self._selected_index]
        self.set_slot_name(slot)
        return slot

    def move_history(self, direction: int) -> Optional[HistoryEntry]:
        if not self._history_entries:
            return None
        new_index = self._history_index + direction
        window_size = min(len(self._history_entries) - self._history_offset, 10)
        max_index = max(0, window_size - 1)
        if new_index < 0:
            if self._history_offset > 0:
                self._history_offset -= 1
                new_index = 0
            else:
                new_index = 0
        elif new_index > max_index:
            if self._history_offset + window_size < len(self._history_entries):
                self._history_offset += 1
                window_size = min(len(self._history_entries) - self._history_offset, 10)
                max_index = max(0, window_size - 1)
                new_index = max_index
            else:
                new_index = max_index
        self._history_index = new_index
        return self.current_history_entry()

    def current_history_entry(self) -> Optional[HistoryEntry]:
        if not self._history_entries:
            return None
        return self._history_entries[self._history_index]

    def set_preview_lines(self, lines: List[str]) -> None:
        self._preview_lines = lines

    def clear_preview(self) -> None:
        self._preview_lines = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_font(self) -> None:
        if self._font is not None:
            return
        import pygame  # type: ignore

        pygame.font.init()
        size = 12
        self._font = pygame.font.SysFont("Courier", size)
        self._line_height = self._font.get_linesize()

    def _render_section(self, surface, x: int, y: int, title: str, lines: Iterable[str]) -> int:
        import pygame  # type: ignore

        if self._font is None:
            return y
        title_surface = self._font.render(title, True, (255, 215, 0))
        surface.blit(title_surface, (x, y))
        cursor_y = y + self._line_height
        for line in lines:
            rendered = self._font.render(line, True, (230, 230, 230))
            surface.blit(rendered, (x, cursor_y))
            cursor_y += self._line_height
        return cursor_y

    def _measure_sections(self, sections: Iterable[tuple[str, Iterable[str]]]) -> int:
        if self._font is None:
            return 0
        max_width = 0
        for title, lines in sections:
            max_width = max(max_width, self._font.size(title)[0])
            for line in lines:
                max_width = max(max_width, self._font.size(line)[0])
        return max_width

    def _snapshot_cpu(self, cpu) -> list[str]:
        if cpu is None:
            return ["CPU not attached"]
        regs = cpu.registers
        flags = cpu.flags
        lines = [
            f"PC:{regs.program_counter:04X}  IX:{regs.index:04X}  SP:{regs.stack_pointer:04X}",
            f"A:{regs.acc_a:02X}  B:{regs.acc_b:02X}",
            "FLAGS:" + " ".join([
                f"H={int(flags.carry_h)}",
                f"I={int(flags.carry_i)}",
                f"N={int(flags.carry_n)}",
                f"Z={int(flags.carry_z)}",
                f"V={int(flags.carry_v)}",
                f"C={int(flags.carry_c)}",
            ]),
        ]
        status = cpu.status
        extra = []
        if status.halt_requested:
            extra.append("HALT")
        if status.fetch_wai:
            extra.append("WAI")
        if status.irq_requested:
            extra.append("IRQ")
        if status.nmi_requested:
            extra.append("NMI")
        if extra:
            lines.append("STATUS:" + ",".join(extra))
        return lines

    def _snapshot_stack(self, cpu, memory: MemorySystem | None) -> list[str]:
        if cpu is None or memory is None:
            return ["Stack unavailable"]
        sp = cpu.registers.stack_pointer & 0xFFFF
        bytes_list = []
        for offset in range(self.STACK_BYTES):
            addr = (sp + offset) & 0xFFFF
            bytes_list.append((addr, memory.load8(addr) & 0xFF))
        lines = [f"{addr:04X}:{value:02X}" for addr, value in bytes_list]
        return lines

    def _snapshot_via(self, via) -> list[str]:
        if via is None:
            return ["VIA not attached"]
        state = getattr(via, "_state", None)
        if state is None:
            return ["VIA state unavailable"]
        lines = [
            f"IFR:{state.IFR:02X}  IER:{state.IER:02X}",
            f"ORA:{state.ORA:02X}  ORB:{state.ORB:02X}",
            f"DDRA:{state.DDRA:02X}  DDRB:{state.DDRB:02X}",
            f"PCR:{state.PCR:02X}  ACR:{state.ACR:02X}",
            f"T1:{state.timer1:04X} T2:{state.timer2:04X}",
        ]
        return lines

    def _snapshot_program(self, info) -> list[str]:
        if info is None:
            return ["No program loaded"]
        lines = [f"Name: {info.name or '-'}"]
        if info.comment:
            lines.append(f"Comment: {info.comment}")
        if info.path is not None:
            lines.append(f"File: {info.path.name}")
        if info.basic_area:
            lines.append("Contains BASIC area")
        if info.address_regions:
            lines.append("Regions:")
            for region in info.address_regions[:4]:
                comment = f" ({region.comment})" if region.comment else ""
                lines.append(f"  {region.start:04X}-{region.end:04X}{comment}")
            if len(info.address_regions) > 4:
                lines.append(f"  ... (+{len(info.address_regions) - 4} more)")
        return lines

    def _format_trace_lines(self) -> list[str]:
        entries = list(self._trace)
        if not entries:
            return ["<empty>"]
        grouped: list[str] = []
        line: list[str] = []
        for pc in reversed(entries):
            line.append(f"{pc:04X}")
            if len(line) == 8:
                grouped.append(" ".join(line))
                line = []
        if line:
            grouped.append(" ".join(line))
        return grouped

    def _render_vram_preview(self):
        display = getattr(self._computer.hardware, "display", None)
        if display is None:
            return None
        if self._vram_surface is not None:
            return self._vram_surface
        try:
            import pygame  # type: ignore

            surface = display.render_pygame_surface(1)
            width, height = surface.get_size()
            scale = 2
            preview = pygame.transform.scale(surface, (width // scale, height // scale))
            self._vram_surface = preview
            return preview
        except Exception:
            return None

    def _status_header(self) -> str:
        suffix = " [snapshot]" if self._snapshot_available else ""
        base = self._status_message or "Debug menu"
        return f"{base} [slot:{self._slot_name}]" + suffix
