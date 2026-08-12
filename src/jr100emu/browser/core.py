"""Small, host-independent API used by the browser frontend."""

from __future__ import annotations

from typing import Any, Mapping

from jr100emu.jr100.computer import JR100Computer
from jr100emu.jr100.memory import decode_rom_bytes


class BrowserCore:
    """Own one ROM-backed JR-100 instance and expose frame-sized operations."""

    FRAME_WIDTH = 256
    FRAME_HEIGHT = 192
    CPU_CLOCK_FREQUENCY = 894_000.0
    CYCLES_PER_FRAME = int(CPU_CLOCK_FREQUENCY / 60.0)

    def __init__(
        self,
        rom_bytes: bytes | bytearray | memoryview,
        *,
        cycles_per_frame: int = CYCLES_PER_FRAME,
        enable_audio: bool = False,
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
        self.computer = JR100Computer(
            rom_bytes=image.data,
            enable_audio=enable_audio,
            allow_implicit_rom=False,
        )
        self.computer.reset()

    def reset(self) -> None:
        self.computer.reset()

    def run_frame(self, cycles: int | None = None) -> bytes:
        self.computer.tick(self.cycles_per_frame if cycles is None else int(cycles))
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

    def state(self) -> Mapping[str, Any]:
        registers = self.computer.cpu_core.registers
        return {
            "clockCount": self.computer.clock_count,
            "programCounter": registers.program_counter,
            "runningStatus": self.computer.get_running_status(),
            "joystickMask": self.computer.ext_port.get_gamepad_status(),
        }


__all__ = ["BrowserCore"]
