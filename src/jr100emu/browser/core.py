"""Small, host-independent API used by the browser frontend."""

from __future__ import annotations

from collections import deque
from typing import Any, Mapping

from jr100emu.jr100.computer import JR100Computer
from jr100emu.jr100.memory import decode_rom_bytes


class BrowserCore:
    """Own one ROM-backed JR-100 instance and expose frame-sized operations."""

    FRAME_WIDTH = 256
    FRAME_HEIGHT = 192
    CPU_CLOCK_FREQUENCY = 894_000.0
    CYCLES_PER_FRAME = int(CPU_CLOCK_FREQUENCY / 60.0)
    FONT_DATA_LENGTH = 1024
    NORMAL_KEY_TABLE_OFFSET = 0x1A6C
    SHIFT_KEY_TABLE_OFFSET = 0x1A99
    KEY_TABLE_LENGTH = 43
    AUTOSTART_SETTLE_FRAMES = 100
    AUTOTYPE_MODIFIER_FRAMES = 4
    AUTOTYPE_KEY_FRAMES = 8
    AUTOTYPE_GAP_FRAMES = 6

    def __init__(
        self,
        rom_bytes: bytes | bytearray | memoryview,
        *,
        cycles_per_frame: int = CYCLES_PER_FRAME,
        enable_audio: bool = False,
        extended_ram: bool = False,
    ) -> None:
        image = decode_rom_bytes(
            rom_bytes,
            start=JR100Computer.BASIC_ROM_START,
            length=JR100Computer.BASIC_ROM_LENGTH,
        )
        if cycles_per_frame <= 0:
            raise ValueError("cycles_per_frame must be positive")

        self.rom_info = {
            "format": image.format,
            "name": image.name,
            "startAddress": image.start_address,
            "size": len(image.data),
        }
        self.cycles_per_frame = int(cycles_per_frame)
        self._rom_data = image.data
        self.computer = JR100Computer(
            rom_bytes=image.data,
            enable_audio=enable_audio,
            capture_audio=True,
            extended_ram=extended_ram,
            allow_implicit_rom=False,
        )
        self._autotype_queue: deque[tuple[tuple[tuple[int, int], ...], int]] = deque()
        self._autotype_cells: tuple[tuple[int, int], ...] = ()
        self._autotype_frames_remaining = 0
        self._breakpoints: set[int] = set()
        self._breakpoint_hit: int | None = None
        self._skip_breakpoint_once: int | None = None
        self.computer.reset()

    def reset(self) -> None:
        self._release_autotype_cells()
        self._autotype_queue.clear()
        self._autotype_frames_remaining = 0
        self._breakpoint_hit = None
        self.computer.reset()

    def run_frame(self, cycles: int | None = None) -> bytes:
        self._advance_autotype()
        frame_cycles = self.cycles_per_frame if cycles is None else int(cycles)
        if self._breakpoints:
            self._run_with_breakpoints(frame_cycles)
        else:
            self.computer.tick(frame_cycles)
        return self.frame_buffer()

    def frame_buffer(self) -> bytes:
        return self.computer.hardware.display.render_indexed_frame()

    def set_key(self, row: int, bit: int, pressed: bool) -> None:
        if pressed:
            self.computer.hardware.keyboard.press(int(row), int(bit))
        else:
            self.computer.hardware.keyboard.release(int(row), int(bit))

    def clear_keys(self) -> None:
        self.computer.hardware.keyboard.clear()

    def set_joystick_mask(self, mask: int) -> None:
        self.computer.ext_port.set_gamepad_mask(int(mask))

    def audio_buffer(self) -> list[int]:
        return self.computer.hardware.sound_processor.drain_samples()

    def font_data(self) -> bytes:
        return bytes(self._rom_data[: self.FONT_DATA_LENGTH])

    def normal_key_codes(self) -> bytes:
        start = self.NORMAL_KEY_TABLE_OFFSET
        return bytes(self._rom_data[start : start + self.KEY_TABLE_LENGTH])

    def shift_key_codes(self) -> bytes:
        start = self.SHIFT_KEY_TABLE_OFFSET
        return bytes(self._rom_data[start : start + self.KEY_TABLE_LENGTH])

    def read_memory(self, start: int, length: int) -> list[int]:
        if length < 0 or length > 0x10000:
            raise ValueError("memory length out of range")
        address = int(start) & 0xFFFF
        return [
            self.computer.memory.load8((address + offset) & 0xFFFF)
            for offset in range(length)
        ]

    def set_breakpoints(self, addresses: list[int]) -> None:
        self._breakpoints = {int(address) & 0xFFFF for address in addresses}
        if self._breakpoint_hit not in self._breakpoints:
            self._breakpoint_hit = None

    def continue_execution(self) -> None:
        self._skip_breakpoint_once = self._breakpoint_hit
        self._breakpoint_hit = None

    def step_instruction(self) -> dict[str, Any]:
        self._breakpoint_hit = None
        before = self.computer.clock_count
        for _ in range(2):
            self.computer.tick(1)
            if self.computer.clock_count > before:
                break
        return self.debug_state()

    def _run_with_breakpoints(self, cycles: int) -> None:
        if self._breakpoint_hit is not None:
            return
        target_clock = self.computer.clock_count + max(0, cycles)
        while self.computer.clock_count < target_clock:
            program_counter = self.computer.cpu_core.registers.program_counter & 0xFFFF
            if program_counter in self._breakpoints:
                if self._skip_breakpoint_once == program_counter:
                    self._skip_breakpoint_once = None
                else:
                    self._breakpoint_hit = program_counter
                    return
            before = self.computer.clock_count
            self.computer.tick(1)
            if self.computer.clock_count == before:
                self.computer.tick(1)

    def debug_state(self) -> dict[str, Any]:
        registers = self.computer.cpu_core.registers
        flags = self.computer.cpu_core.flags
        return {
            "clockCount": self.computer.clock_count,
            "extendedRam": self.computer.has_extended_ram(),
            "graphicsMode": bool(self.computer.memory.load8(0x0014) & 0x10),
            "cpu": {
                "a": registers.acc_a & 0xFF,
                "b": registers.acc_b & 0xFF,
                "ix": registers.index & 0xFFFF,
                "sp": registers.stack_pointer & 0xFFFF,
                "pc": registers.program_counter & 0xFFFF,
                "flags": "".join(
                    name if value else "-"
                    for name, value in (
                        ("H", flags.carry_h),
                        ("I", flags.carry_i),
                        ("N", flags.carry_n),
                        ("Z", flags.carry_z),
                        ("V", flags.carry_v),
                        ("C", flags.carry_c),
                    )
                ),
            },
            "via": self.computer.via.debug_snapshot(),
        }

    def load_program(
        self,
        data: bytes | bytearray | memoryview,
        *,
        filename: str = "",
    ) -> dict[str, Any]:
        info = self.computer.load_user_program_bytes(data, filename=filename)
        command = ""
        if info.basic_area:
            command = "RUN"
        elif info.entry_point is not None:
            command = f"A=USR(${info.entry_point:04X})"
        if command:
            self._queue_autotype(command + "\r")
        return {
            "name": info.name,
            "comment": info.comment,
            "version": info.version,
            "basic": info.basic_area,
            "entryPoint": info.entry_point,
            "suggestedEntryPoint": info.suggested_entry_point,
            "entrySource": info.entry_source,
            "autostartCommand": command,
            "regions": [
                {"start": region.start, "end": region.end, "comment": region.comment}
                for region in info.address_regions
            ],
        }

    def run_entry(self, address: int) -> str:
        entry_point = int(address) & 0xFFFF
        self.reset()
        command = f"A=USR(${entry_point:04X})"
        self._queue_autotype(command + "\r")
        return command

    def _queue_autotype(self, text: str) -> None:
        self._release_autotype_cells()
        self._autotype_queue.clear()
        self._autotype_frames_remaining = 0
        self._autotype_queue.append(((), self.AUTOSTART_SETTLE_FRAMES))
        self._queue_chord(((0, 0),), ((0, 3),))
        for character in text:
            cell, shifted = self._key_for_character(character)
            if shifted:
                self._queue_chord(((0, 1),), (cell,))
            else:
                self._autotype_queue.append(((cell,), self.AUTOTYPE_KEY_FRAMES))
                self._autotype_queue.append(((), self.AUTOTYPE_GAP_FRAMES))

    def _queue_chord(
        self,
        modifiers: tuple[tuple[int, int], ...],
        keys: tuple[tuple[int, int], ...],
    ) -> None:
        self._autotype_queue.append((modifiers, self.AUTOTYPE_MODIFIER_FRAMES))
        self._autotype_queue.append((modifiers + keys, self.AUTOTYPE_KEY_FRAMES))
        self._autotype_queue.append((modifiers, self.AUTOTYPE_MODIFIER_FRAMES))
        self._autotype_queue.append(((), self.AUTOTYPE_GAP_FRAMES))

    def _key_for_character(self, character: str) -> tuple[tuple[int, int], bool]:
        code = ord(character)
        cells = [
            (row, bit)
            for row in range(9)
            for bit in range(5)
            if (row, bit) not in {(0, 0), (0, 1)}
        ]
        for shifted, table in (
            (False, self.normal_key_codes()),
            (True, self.shift_key_codes()),
        ):
            for cell, candidate in zip(cells, table):
                if candidate == code:
                    return cell, shifted
        raise ValueError(f"character cannot be typed on JR-100 keyboard: {character!r}")

    def _advance_autotype(self) -> None:
        if self._autotype_frames_remaining > 0:
            self._autotype_frames_remaining -= 1
            return
        if not self._autotype_queue:
            self._release_autotype_cells()
            return
        cells, frames = self._autotype_queue.popleft()
        self._set_autotype_cells(cells)
        self._autotype_frames_remaining = max(0, frames - 1)

    def _set_autotype_cells(self, cells: tuple[tuple[int, int], ...]) -> None:
        self._release_autotype_cells()
        for row, bit in cells:
            self.computer.hardware.keyboard.press(row, bit)
        self._autotype_cells = cells

    def _release_autotype_cells(self) -> None:
        for row, bit in self._autotype_cells:
            self.computer.hardware.keyboard.release(row, bit)
        self._autotype_cells = ()

    def state(self) -> Mapping[str, Any]:
        registers = self.computer.cpu_core.registers
        return {
            "clockCount": self.computer.clock_count,
            "programCounter": registers.program_counter,
            "runningStatus": self.computer.get_running_status(),
            "joystickMask": self.computer.ext_port.get_gamepad_status(),
            "graphicsMode": bool(self.computer.memory.load8(0x0014) & 0x10),
            "extendedRam": self.computer.has_extended_ram(),
            "autotypeActive": bool(
                self._autotype_queue
                or self._autotype_cells
                or self._autotype_frames_remaining
            ),
            "breakpointHit": self._breakpoint_hit,
        }


__all__ = ["BrowserCore"]
