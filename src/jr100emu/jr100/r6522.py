"""JR-100 specific R6522 customisations."""

from __future__ import annotations

from typing import Optional

from jr100emu.via.r6522 import R6522, _mask8


class JR100R6522(R6522):
    """JR-100 oriented VIA implementation mirroring the Java subclass."""

    DEFAULT_CPU_CLOCK = 894_000.0

    def __init__(self, computer: object, start_address: int) -> None:
        super().__init__(computer, start_address)
        self._previous_frequency: float = 0.0

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def _hardware_component(self, attr: str) -> Optional[object]:
        hardware = self._hardware()
        if hardware is None:
            return None
        if hasattr(hardware, attr):
            return getattr(hardware, attr)
        getter = f"get_{attr}"
        if hasattr(hardware, getter):
            return getattr(hardware, getter)()
        getter = f"get{attr.capitalize()}"
        if hasattr(hardware, getter):
            return getattr(hardware, getter)()
        return None

    def _call(self, obj: object | None, snake: str, *args) -> None:
        if obj is None:
            return
        if hasattr(obj, snake):
            getattr(obj, snake)(*args)
            return
        camel = snake[0].upper() + snake[1:]
        if hasattr(obj, camel):
            getattr(obj, camel)(*args)

    def _cpu_clock_frequency(self) -> float:
        if hasattr(self.computer, "cpu_clock_frequency"):
            return float(getattr(self.computer, "cpu_clock_frequency"))
        if hasattr(self.computer, "get_cpu_clock_frequency"):
            return float(self.computer.get_cpu_clock_frequency())
        if hasattr(self.computer, "clock_frequency"):
            return float(getattr(self.computer, "clock_frequency"))
        if hasattr(self.computer, "getClockFrequency"):
            return float(self.computer.getClockFrequency())
        return self.DEFAULT_CPU_CLOCK

    def _jumper_pb7_pb6(self) -> None:
        self.set_port_b(6, self.input_port_b_bit(7))

    # ------------------------------------------------------------------
    # Overridden hooks
    # ------------------------------------------------------------------
    def store_orb_option(self) -> None:
        display = self._hardware_component("display")
        if display is None:
            return
        font_user = getattr(display, "FONT_USER_DEFINED", None)
        font_normal = getattr(display, "FONT_NORMAL", None)
        if font_user is None or font_normal is None:
            return
        if (self.input_port_b() & 0x20) == 0x20:
            self._call(display, "set_current_font", font_user)
        else:
            self._call(display, "set_current_font", font_normal)
        self._jumper_pb7_pb6()

    def store_iora_option(self) -> None:
        keyboard = self._hardware_component("keyboard")
        if keyboard is None:
            return
        get_matrix = None
        if hasattr(keyboard, "get_key_matrix"):
            get_matrix = keyboard.get_key_matrix
        elif hasattr(keyboard, "getKeyMatrix"):
            get_matrix = keyboard.getKeyMatrix
        if get_matrix is None:
            return
        matrix = get_matrix()
        value = self.input_port_b() & 0xE0
        row = self._state.ORA & 0x0F
        if 0 <= row < len(matrix):
            value |= (~matrix[row]) & 0x1F
        self.set_port_b_value(value)

    def store_t1ch_option(self) -> None:
        sound = self._hardware_component("sound_processor")
        if sound is None:
            return
        if (self._state.ACR & 0xC0) == 0xC0:
            divisor = self._state.timer1 + 2
            if divisor <= 0:
                return
            frequency = 894_886.25 / divisor / 2.0
            if abs(frequency - self._previous_frequency) < 1e-6:
                self._call(sound, "set_line_on")
                return
            self._previous_frequency = frequency
            timestamp = (self._state.current_clock * 1_000_000_000) / self._cpu_clock_frequency() + self._get_base_time()
            self._call(sound, "set_frequency", timestamp, frequency)
            self._call(sound, "set_line_on")
        else:
            self._call(sound, "set_line_off")

    def timer1_timeout_mode0_option(self) -> None:
        sound = self._hardware_component("sound_processor")
        self._call(sound, "set_line_off")

    def timer1_timeout_mode2_option(self) -> None:
        self._jumper_pb7_pb6()

    def timer1_timeout_mode3_option(self) -> None:
        self._jumper_pb7_pb6()

    # ------------------------------------------------------------------
    # IRQ wiring
    # ------------------------------------------------------------------
    def handler_irq(self, state: int) -> None:
        if state != 1:
            return
        cpu = getattr(self.computer, "cpu", None)
        if cpu is None and hasattr(self.computer, "cpu_core"):
            cpu = getattr(self.computer, "cpu_core")
        if cpu is None and hasattr(self.computer, "get_cpu"):
            cpu = self.computer.get_cpu()  # type: ignore[attr-defined]
        if cpu is None:
            return
        if hasattr(cpu, "irq"):
            cpu.irq()
