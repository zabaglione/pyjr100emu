"""Integration tests for CPU, VIA, and hardware wiring."""

from __future__ import annotations

from jr100emu.jr100.computer import JR100Computer
from jr100emu.via.r6522 import R6522


def test_memory_access_reaches_via_registers() -> None:
    computer = JR100Computer()
    via = computer.via
    memory = computer.memory

    base = via.get_start_address()
    # Configure row 1 as active in the keyboard matrix
    memory.store8(base + R6522.VIA_REG_DDRB, 0x00)

    # Simulate key press on row 1 bit 0
    computer.hardware.keyboard.press(1, 0)
    memory.store8(base + R6522.VIA_REG_IORA, 0x01)
    value = memory.load8(base + R6522.VIA_REG_IORB)
    assert (value & 0x01) == 1

    # Release key and confirm matrix returns high
    computer.hardware.keyboard.release(1, 0)
    memory.store8(base + R6522.VIA_REG_IORA, 0x01)
    value = memory.load8(base + R6522.VIA_REG_IORB)
    assert (value & 0x01) == 0


def test_timer1_irq_asserts_cpu_line() -> None:
    computer = JR100Computer()
    via = computer.via
    memory = computer.memory

    base = via.get_start_address()
    # Enable timer1 interrupt and configure continuous square wave
    memory.store8(base + R6522.VIA_REG_IER, R6522.IFR_BIT_T1)
    memory.store8(base + R6522.VIA_REG_ACR, 0xC0)
    memory.store8(base + R6522.VIA_REG_T1CL, 0x02)
    memory.store8(base + R6522.VIA_REG_T1CH, 0x00)

    computer.clock_count += 10
    via.execute()

    assert computer.cpu_core.status.irq_requested is True
