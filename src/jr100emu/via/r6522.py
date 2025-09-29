"""Python port of `jp.asamomiji.emulator.device.R6522`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


def _mask8(value: int) -> int:
    return value & 0xFF


def _mask16(value: int) -> int:
    return value & 0xFFFF


def _to_signed8(value: int) -> int:
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


def _to_signed16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


@dataclass
class VIAState:
    start_address: int
    end_address: int
    IFR: int = 0
    IER: int = 0
    PCR: int = 0
    ACR: int = 0
    IRA: int = 0
    ORA: int = 0
    DDRA: int = 0
    IRB: int = 0
    ORB: int = 0
    DDRB: int = 0
    SR: int = 0
    port_a: int = 0
    port_b: int = 0
    CA1_in: int = 0
    CA2_in: int = 0
    CA2_out: int = 0
    CA2_timer: int = -1
    CB1_in: int = 0
    CB1_out: int = 0
    CB2_in: int = 0
    CB2_out: int = 0
    previous_pb6: int = 0
    latch1: int = 0
    latch2: int = 0
    timer1: int = 0
    timer2: int = 0
    shift_tick: bool = False
    shift_counter: int = 0
    shift_started: bool = False
    timer1_initialized: bool = False
    timer1_enable: bool = False
    timer2_initialized: bool = False
    timer2_enable: bool = False
    timer2_low_byte_timeout: bool = False
    current_clock: int = 0


class R6522:
    """VIA (Versatile Interface Adapter) base implementation."""

    VIA_REG_IORB = 0x00
    VIA_REG_IORA = 0x01
    VIA_REG_DDRB = 0x02
    VIA_REG_DDRA = 0x03
    VIA_REG_T1CL = 0x04
    VIA_REG_T1CH = 0x05
    VIA_REG_T1LL = 0x06
    VIA_REG_T1LH = 0x07
    VIA_REG_T2CL = 0x08
    VIA_REG_T2CH = 0x09
    VIA_REG_SR = 0x0A
    VIA_REG_ACR = 0x0B
    VIA_REG_PCR = 0x0C
    VIA_REG_IFR = 0x0D
    VIA_REG_IER = 0x0E
    VIA_REG_IORANH = 0x0F

    IFR_BIT_CA2 = 0x01
    IFR_BIT_CA1 = 0x02
    IFR_BIT_SR = 0x04
    IFR_BIT_CB2 = 0x08
    IFR_BIT_CB1 = 0x10
    IFR_BIT_T2 = 0x20
    IFR_BIT_T1 = 0x40
    IFR_BIT_IRQ = 0x80

    def __init__(self, computer: object, start_address: int) -> None:
        self.computer = computer
        start = start_address & 0xFFFF
        self._state = VIAState(start_address=start, end_address=start + 0x0F)
        self.reset()

    def get_start_address(self) -> int:
        return self._state.start_address

    def get_end_address(self) -> int:
        return self._state.end_address

    # -------------------------------------------------------------------------
    # Helpers to work with the host computer object
    # -------------------------------------------------------------------------
    def _get_clock_count(self) -> int:
        if hasattr(self.computer, "clock_count"):
            return int(getattr(self.computer, "clock_count"))
        if hasattr(self.computer, "get_clock_count"):
            return int(self.computer.get_clock_count())
        raise AttributeError("Computer must expose clock_count")

    def _get_base_time(self) -> int:
        if hasattr(self.computer, "base_time"):
            return int(getattr(self.computer, "base_time"))
        if hasattr(self.computer, "get_base_time"):
            return int(self.computer.get_base_time())
        return 0

    def _hardware(self) -> Optional[object]:
        if hasattr(self.computer, "hardware"):
            return getattr(self.computer, "hardware")
        if hasattr(self.computer, "get_hardware"):
            return self.computer.get_hardware()
        return None

    # -------------------------------------------------------------------------
    # IRQ handling
    # -------------------------------------------------------------------------
    def process_irq(self) -> None:
        if (self._state.IER & self._state.IFR & 0x7F) != 0:
            if (self._state.IFR & self.IFR_BIT_IRQ) == 0:
                self._state.IFR |= self.IFR_BIT_IRQ
                self.handler_irq(1)
        else:
            if (self._state.IFR & self.IFR_BIT_IRQ) != 0:
                self._state.IFR &= ~self.IFR_BIT_IRQ
                self.handler_irq(0)

    def set_interrupt(self, value: int) -> None:
        if (self._state.IFR & value) == 0:
            self._state.IFR |= value
            self.process_irq()

    def clear_interrupt(self, value: int) -> None:
        if (self._state.IFR & value) != 0:
            self._state.IFR &= ~value
            self.process_irq()

    def is_set_in_interrupts(self, value: int) -> bool:
        return (self._state.IFR & value) != 0

    def handler_irq(self, state: int) -> None:  # pragma: no cover - hook
        """Override to handle IRQ line transitions."""

    # -------------------------------------------------------------------------
    # Port A handling (mirrors Java implementation)
    # -------------------------------------------------------------------------
    def set_port_a(self, bit: int, state: int) -> None:
        mask = 1 << bit
        if (self._state.DDRA & mask) != 0:
            return
        if state:
            self._state.port_a |= mask
        else:
            self._state.port_a &= ~mask
        if (self._state.ACR & 0x01) == 0:
            self._state.IRA = _mask8(self._state.port_a)

    def set_port_a_value(self, value: int) -> None:
        self._state.port_a = _mask8((self._state.port_a & self._state.DDRA) | (value & ~self._state.DDRA))
        if (self._state.ACR & 0x01) == 0:
            self._state.IRA = _mask8(self._state.port_a)

    def input_port_a(self) -> int:
        return _mask8((self._state.IRA & ~self._state.DDRA) | (self._state.port_a & self._state.DDRA))

    def input_port_a_bit(self, bit: int) -> int:
        return (self.input_port_a() >> bit) & 0x01

    def output_port_a(self) -> None:
        self.handler_port_a(_mask8(self._state.ORA))

    def handler_port_a(self, state: int) -> None:  # pragma: no cover - hook
        """Override to react to Port A output changes."""

    def set_ca1(self, state: int) -> None:
        if self._state.CA1_in == state:
            return
        self._state.CA1_in = state
        rising = state == 1 and (self._state.PCR & 0x01) == 0x01
        falling = state == 0 and (self._state.PCR & 0x01) == 0x00
        if rising or falling:
            if (self._state.ACR & 0x01) == 0x01:
                self._state.IRA = self.input_port_a()
            self.set_interrupt(self.IFR_BIT_CA1)
            if self._state.CA2_out == 0 and (self._state.PCR & 0x0E) == 0x08:
                self._state.CA2_out = 1
                self.handler_ca2(self._state.CA2_out)

    def set_ca2(self, state: int) -> None:
        if self._state.CA2_in == state:
            return
        self._state.CA2_in = state
        if (self._state.PCR & 0x08) == 0x00:
            rising = state == 1 and (self._state.PCR & 0x0C) == 0x04
            falling = state == 0 and (self._state.PCR & 0x0C) == 0x00
            if rising or falling:
                self.set_interrupt(self.IFR_BIT_CA2)

    def handler_ca2(self, status: int) -> None:  # pragma: no cover - hook
        """Override for CA2 output changes."""

    # -------------------------------------------------------------------------
    # Port B handling
    # -------------------------------------------------------------------------
    def set_port_b(self, bit: int, state: int) -> None:
        mask = 1 << bit
        if (self._state.DDRB & mask) != 0:
            return
        if state:
            self._state.port_b |= mask
        else:
            self._state.port_b &= ~mask
        if (self._state.ACR & 0x02) == 0:
            self._state.IRB = _mask8(self._state.port_b)

    def set_port_b_value(self, value: int) -> None:
        self._state.port_b = _mask8((self._state.port_b & self._state.DDRB) | (value & ~self._state.DDRB))
        if (self._state.ACR & 0x02) == 0:
            self._state.IRB = _mask8(self._state.port_b)

    def invert_port_b(self, bit: int) -> None:
        mask = 1 << bit
        if (self._state.DDRB & mask) != 0:
            return
        if self._state.port_b & mask:
            self._state.port_b &= ~mask
        else:
            self._state.port_b |= mask
        if (self._state.ACR & 0x02) == 0:
            self._state.IRB = _mask8(self._state.port_b)

    def input_port_b(self) -> int:
        return _mask8((self._state.IRB & ~self._state.DDRB) | (self._state.ORB & self._state.DDRB))

    def input_port_b_bit(self, bit: int) -> int:
        return (self.input_port_b() >> bit) & 0x01

    def output_port_b(self) -> None:
        self.handler_port_b(self._state.ORB)

    def handler_port_b(self, state: int) -> None:  # pragma: no cover - hook
        """Override to react to Port B output changes."""

    def set_cb1(self, state: int) -> None:
        if self._state.CB1_in == state:
            return
        self._state.CB1_in = state
        rising = state == 1 and (self._state.PCR & 0x10) == 0x10
        falling = state == 0 and (self._state.PCR & 0x10) == 0x00
        if rising or falling:
            if (self._state.ACR & 0x02) == 0x02:
                self._state.IRB = self.input_port_b()
            if self._state.shift_started and (self._state.ACR & 0x1C) == 0x0C:
                self._process_shift_in()
            if self._state.shift_started and (self._state.ACR & 0x1C) == 0x1C:
                self._process_shift_out()
            self.set_interrupt(self.IFR_BIT_CB1)
            if self._state.CB2_out == 0 and (self._state.PCR & 0xA0) == 0x20:
                self._state.CB2_out = 1
                self.handler_cb2(self._state.CB2_out)

    def set_cb2(self, state: int) -> None:
        if self._state.CB2_in == state:
            return
        self._state.CB2_in = state
        if (self._state.PCR & 0x80) == 0x00:
            rising = state == 1 and (self._state.PCR & 0xC0) == 0x40
            falling = state == 0 and (self._state.PCR & 0xC0) == 0x00
            if rising or falling:
                self.set_interrupt(self.IFR_BIT_CB2)

    def handler_cb1(self, status: int) -> None:  # pragma: no cover - hook
        """Override to react to CB1 changes."""

    def handler_cb2(self, status: int) -> None:  # pragma: no cover - hook
        """Override to react to CB2 changes."""

    # -------------------------------------------------------------------------
    # Shift register operations
    # -------------------------------------------------------------------------
    def _initialize_shift_in(self) -> None:
        self._state.shift_tick = False
        self._state.shift_counter = 0
        if self.is_set_in_interrupts(self.IFR_BIT_SR):
            self.clear_interrupt(self.IFR_BIT_SR)
            self._process_shift_in()
        self._state.shift_started = True

    def _initialize_shift_out(self) -> None:
        self._state.shift_tick = False
        self._state.shift_counter = 0
        if self.is_set_in_interrupts(self.IFR_BIT_SR):
            self.clear_interrupt(self.IFR_BIT_SR)
            self._process_shift_out()
        self._state.shift_started = True

    def _process_shift_in(self) -> None:
        if not self._state.shift_started:
            return
        if self._state.shift_tick:
            self._state.CB1_out = 1
            self.handler_cb1(self._state.CB1_out)
            self._state.SR = _mask8((self._state.SR << 1) | (self._state.CB2_in & 0x01))
            self._state.shift_counter = (self._state.shift_counter + 1) % 8
            if self._state.shift_counter == 0:
                self.set_interrupt(self.IFR_BIT_SR)
                self._state.shift_started = False
        else:
            self._state.CB1_out = 0
            self.handler_cb1(self._state.CB1_out)
        self._state.shift_tick = not self._state.shift_tick

    def _process_shift_out(self) -> None:
        if not self._state.shift_started:
            return
        if self._state.shift_tick:
            self._state.CB1_out = 1
            self.handler_cb1(self._state.CB1_out)
            self._state.CB2_out = (self._state.SR >> 7) & 0x01
            self.handler_cb2(self._state.CB2_out)
            self._state.SR = _mask8((self._state.SR << 1) | (self._state.CB2_out & 0x01))
            if (self._state.ACR & 0x1C) != 0x10:
                self._state.shift_counter = (self._state.shift_counter + 1) % 8
                if self._state.shift_counter == 0:
                    self.set_interrupt(self.IFR_BIT_SR)
                    self._state.shift_started = False
        else:
            self._state.CB1_out = 0
            self.handler_cb1(self._state.CB1_out)
        self._state.shift_tick = not self._state.shift_tick

    # -------------------------------------------------------------------------
    # Memory mapped access
    # -------------------------------------------------------------------------
    def load8(self, address: int) -> int:
        delay = 0
        self._execute(self._get_clock_count() - 1 + delay)
        offset = (address - self._state.start_address) & 0xFFFF
        if offset == self.VIA_REG_IORB:
            if (self._state.ACR & 0x02) == 0:
                result = self.input_port_b()
            else:
                result = self._state.IRB
            self.clear_interrupt(self.IFR_BIT_CB1 | (0 if (self._state.PCR & 0xA0) == 0x20 else self.IFR_BIT_CB2))
        elif offset == self.VIA_REG_IORA:
            result = self.input_port_a() if (self._state.ACR & 0x01) == 0 else self._state.IRA
            self.clear_interrupt(self.IFR_BIT_CA1 | (0 if (self._state.PCR & 0x0A) == 0x02 else self.IFR_BIT_CA2))
            if (self._state.CA2_out == 1) and (((self._state.PCR & 0x0E) == 0x0A) or ((self._state.PCR & 0x0E) == 0x08)):
                self._state.CA2_out = 0
                self.handler_ca2(self._state.CA2_out)
                if (self._state.PCR & 0x0E) == 0x08:
                    self._state.CA2_timer = 1
        elif offset == self.VIA_REG_DDRB:
            result = self._state.DDRB
        elif offset == self.VIA_REG_DDRA:
            result = self._state.DDRA
        elif offset == self.VIA_REG_T1CL:
            self.clear_interrupt(self.IFR_BIT_T1)
            result = self._state.timer1 & 0xFF
        elif offset == self.VIA_REG_T1CH:
            result = (self._state.timer1 >> 8) & 0xFF
        elif offset == self.VIA_REG_T1LL:
            result = self._state.latch1 & 0xFF
        elif offset == self.VIA_REG_T1LH:
            result = (self._state.latch1 >> 8) & 0xFF
        elif offset == self.VIA_REG_T2CL:
            self.clear_interrupt(self.IFR_BIT_T2)
            result = self._state.timer2 & 0xFF
        elif offset == self.VIA_REG_T2CH:
            result = (self._state.timer2 >> 8) & 0xFF
        elif offset == self.VIA_REG_SR:
            mode = self._state.ACR & 0x1C
            if mode in {0x00}:
                pass
            elif mode in {0x04, 0x08, 0x0C}:
                self._initialize_shift_in()
            elif mode in {0x10, 0x14, 0x18, 0x1C}:
                self._initialize_shift_out()
            else:
                raise AssertionError(f"invalid sr mode {mode:02x}")
            result = self._state.SR
        elif offset == self.VIA_REG_ACR:
            result = self._state.ACR
        elif offset == self.VIA_REG_PCR:
            result = self._state.PCR
        elif offset == self.VIA_REG_IFR:
            result = self._state.IFR
        elif offset == self.VIA_REG_IER:
            result = self._state.IER | 0x80
        elif offset == self.VIA_REG_IORANH:
            result = self.input_port_a() if (self._state.ACR & 0x01) == 0 else self._state.IRA
        else:
            raise AssertionError(f"invalid register {address:#04x}")
        self._execute(self._get_clock_count() + delay)
        return result & 0xFF

    def store8(self, address: int, value: int) -> None:
        delay = 0
        self._execute(self._get_clock_count() - 1 + delay)
        offset = (address - self._state.start_address) & 0xFFFF
        value &= 0xFF
        if offset == self.VIA_REG_IORB:
            self._state.ORB = value
            self.output_port_b()
            self.clear_interrupt(self.IFR_BIT_CB1 | (0 if (self._state.PCR & 0xA0) == 0x20 else self.IFR_BIT_CB2))
            if (self._state.CB2_out == 1) and ((self._state.PCR & 0xC0) == 0x80):
                self._state.CB2_out = 0
                self.handler_cb2(self._state.CB2_out)
            self.store_orb_option()
        elif offset == self.VIA_REG_IORA:
            self._state.ORA = value
            if self._state.DDRA != 0x00:
                self.output_port_a()
            self.clear_interrupt(self.IFR_BIT_CA1 | (0 if (self._state.PCR & 0x0A) == 0x02 else self.IFR_BIT_CA2))
            if (self._state.CA2_out == 1) and (((self._state.PCR & 0x0E) == 0x0A) or (self._state.PCR & 0x0C) == 0x08):
                self._state.CA2_out = 0
                self.handler_ca2(self._state.CA2_out)
            if (self._state.PCR & 0x0E) == 0x0A:
                self._state.CA2_timer = 1
            self.store_iora_option()
        elif offset == self.VIA_REG_DDRB:
            self._state.DDRB = value
            self.store_ddrb_option()
        elif offset == self.VIA_REG_DDRA:
            self._state.DDRA = value
            self.store_ddra_option()
        elif offset == self.VIA_REG_T1CL:
            self._state.latch1 = _mask16((self._state.latch1 & 0xFF00) | value)
            self.store_t1cl_option()
        elif offset == self.VIA_REG_T1CH:
            self._state.latch1 = _mask16((self._state.latch1 & 0x00FF) | (value << 8))
            self._state.timer1 = self._state.latch1
            self._state.timer1_initialized = True
            self._state.timer1_enable = True
            self.set_port_b(7, 0)
            self.store_t1ch_option()
        elif offset == self.VIA_REG_T1LL:
            self._state.latch1 = _mask16((self._state.latch1 & 0xFF00) | value)
            self.store_t1ll_option()
        elif offset == self.VIA_REG_T1LH:
            self._state.latch1 = _mask16((self._state.latch1 & 0x00FF) | (value << 8))
            self.store_t1lh_option()
        elif offset == self.VIA_REG_T2CL:
            self._state.latch2 = _mask16((self._state.latch2 & 0xFF00) | value)
            self.store_t2cl_option()
        elif offset == self.VIA_REG_T2CH:
            self._state.latch2 = _mask16((self._state.latch2 & 0x00FF) | (value << 8))
            self._state.timer2 = self._state.latch2
            self.clear_interrupt(self.IFR_BIT_T2)
            self._state.timer2_initialized = True
            self._state.timer2_enable = True
            self.store_t2ch_option()
        elif offset == self.VIA_REG_SR:
            mode = self._state.ACR & 0x1C
            if mode in {0x04, 0x08, 0x0C}:
                self._initialize_shift_in()
            elif mode in {0x10, 0x14, 0x18, 0x1C}:
                self._initialize_shift_out()
            elif mode not in {0x00}:
                raise AssertionError(f"invalid sr mode {mode:02x}")
            self._state.SR = value
            self.store_sr_option()
        elif offset == self.VIA_REG_ACR:
            self._state.ACR = value
            self.store_acr_option()
        elif offset == self.VIA_REG_PCR:
            self._state.PCR = value
            self.store_pcr_option()
        elif offset == self.VIA_REG_IFR:
            if (value & 0x80) == 0x80:
                value = 0x7F
            self.clear_interrupt(value)
            self.store_ifr_option()
        elif offset == self.VIA_REG_IER:
            if value & 0x80:
                self._state.IER |= value & 0x7F
            else:
                self._state.IER &= ~(value & 0x7F)
            self.process_irq()
            self.store_ier_option()
        elif offset == self.VIA_REG_IORANH:
            self._state.ORA = value
            if self._state.DDRA != 0x00:
                self.output_port_a()
            self.store_iora_nohs_option()
        else:
            raise AssertionError(f"invalid register {address:#04x}")
        self._execute(self._get_clock_count() + delay)

    # -------------------------------------------------------------------------
    # Hooks for subclasses (no-ops by default)
    # -------------------------------------------------------------------------
    def store_orb_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_iora_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_ddrb_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_ddra_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_t1cl_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_t1ch_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_t1ll_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_t1lh_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_t2cl_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_t2ch_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_sr_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_acr_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_pcr_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_ifr_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_ier_option(self) -> None:  # pragma: no cover - hook
        pass

    def store_iora_nohs_option(self) -> None:  # pragma: no cover - hook
        pass

    def timer1_timeout_mode0_option(self) -> None:  # pragma: no cover - hook
        pass

    def timer1_timeout_mode1_option(self) -> None:  # pragma: no cover - hook
        pass

    def timer1_timeout_mode2_option(self) -> None:  # pragma: no cover - hook
        pass

    def timer1_timeout_mode3_option(self) -> None:  # pragma: no cover - hook
        pass

    # -------------------------------------------------------------------------
    # Core execution loop
    # -------------------------------------------------------------------------
    def _execute(self, target_clock: int) -> None:
        while self._state.current_clock <= target_clock:
            if self._state.CA2_timer >= 0:
                self._state.CA2_timer -= 1
                if self._state.CA2_timer < 0:
                    self._state.CA2_out = 1
                    self.handler_ca2(self._state.CA2_out)

            # Timer 1
            if self._state.timer1_initialized:
                self._state.timer1_initialized = False
            elif self._state.timer1 >= 0:
                self._state.timer1 -= 1
            else:
                if self._state.timer1_enable:
                    self.set_interrupt(self.IFR_BIT_T1)
                    mode = self._state.ACR & 0xC0
                    if mode == 0x00:
                        self._state.timer1_enable = False
                        self.timer1_timeout_mode0_option()
                    elif mode == 0x40:
                        self.invert_port_b(7)
                        self.timer1_timeout_mode1_option()
                    elif mode == 0x80:
                        self._state.timer1_enable = False
                        self.set_port_b(7, 1)
                        self.timer1_timeout_mode2_option()
                    elif mode == 0xC0:
                        self.invert_port_b(7)
                        self.timer1_timeout_mode3_option()
                    else:
                        raise AssertionError(f"invalid t1 mode {mode:02x}")
                self._state.timer1 = self._state.latch1
                self.store_t1ch_option()

            # Timer 2
            current_pb6 = self.input_port_b() & 0x40
            pb6_negative = self._state.previous_pb6 != 0 and current_pb6 == 0
            self._state.previous_pb6 = current_pb6

            if self._state.timer2 >= 0:
                mode = self._state.ACR & 0x20
                if mode == 0x00:
                    if self._state.timer2_initialized:
                        self._state.timer2_initialized = False
                    else:
                        self._state.timer2 -= 1
                elif mode == 0x20:
                    if self._state.timer2_initialized:
                        self._state.timer2_initialized = False
                    elif pb6_negative:
                        self._state.timer2 -= 1
                else:
                    raise AssertionError(f"invalid t2 mode {(self._state.ACR & 0x20):02x}")
            else:
                if self._state.timer2_enable:
                    self.set_interrupt(self.IFR_BIT_T2)
                    self._state.timer2_enable = False
                if self._state.shift_started and (self._state.timer2 & 0xFF) == 0xFF:
                    mode = self._state.ACR & 0x1C
                    if mode == 0x04:
                        self._process_shift_in()
                    elif mode in {0x10, 0x14}:
                        self._process_shift_out()
                self._state.timer2 = self._state.latch2

            # Shift register
            mode = self._state.ACR & 0x1C
            if mode == 0x08:
                self._process_shift_in()
            elif mode == 0x18:
                self._process_shift_out()

            self._state.current_clock += 1

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------
    def reset(self) -> None:
        state = self._state
        state.IFR = 0
        state.IER = 0
        state.PCR = 0
        state.ACR = 0
        state.IRA = 0
        state.ORA = 0
        state.DDRA = 0
        state.IRB = 0
        state.ORB = 0
        state.DDRB = 0
        state.SR = 0
        state.port_a = 0
        state.port_b = 0
        state.CA1_in = 0
        state.CA2_in = 0
        state.CA2_out = 0
        state.CA2_timer = -1
        state.CB1_in = 0
        state.CB1_out = 0
        state.CB2_in = 0
        state.CB2_out = 0
        state.previous_pb6 = 0
        state.latch1 = 0
        state.latch2 = 0
        state.timer1 = 0
        state.timer2 = 0
        state.shift_tick = False
        state.shift_counter = 0
        state.shift_started = False
        state.timer1_initialized = False
        state.timer1_enable = False
        state.timer2_initialized = False
        state.timer2_enable = False
        state.timer2_low_byte_timeout = False
        state.current_clock = 0

    def execute(self) -> None:
        self._execute(self._get_clock_count())

    # -------------------------------------------------------------------------
    # State serialization hooks (to be wired once StateSet exists)
    # -------------------------------------------------------------------------
    def save_state(self, save: dict[str, object]) -> None:
        for field, value in self._state.__dict__.items():
            save[f"R6522.{field}"] = value

    def load_state(self, load: dict[str, object]) -> None:
        for field in self._state.__dict__.keys():
            key = f"R6522.{field}"
            if key in load:
                setattr(self._state, field, load[key])
