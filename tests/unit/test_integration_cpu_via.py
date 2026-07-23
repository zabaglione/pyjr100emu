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
    assert (value & 0x01) == 0

    # Release key and confirm matrix returns high
    computer.hardware.keyboard.release(1, 0)
    memory.store8(base + R6522.VIA_REG_IORA, 0x01)
    value = memory.load8(base + R6522.VIA_REG_IORB)
    assert (value & 0x01) == 1


def test_timer1_irq_asserts_cpu_line() -> None:
    computer = JR100Computer()
    via = computer.via
    memory = computer.memory

    base = via.get_start_address()
    # Enable timer1 interrupt and configure continuous square wave
    memory.store8(base + R6522.VIA_REG_IER, 0x80 | R6522.IFR_BIT_T1)
    memory.store8(base + R6522.VIA_REG_ACR, 0xC0)
    memory.store8(base + R6522.VIA_REG_T1CL, 0x02)
    memory.store8(base + R6522.VIA_REG_T1CH, 0x00)

    computer.clock_count += 10
    via.execute()

    assert computer.cpu_core.status.irq_requested is True


def test_cleared_timer1_irq_is_not_serviced_after_interrupts_are_unmasked() -> None:
    computer = JR100Computer(enable_audio=False)
    cpu = computer.cpu_core
    via = computer.via
    memory = computer.memory
    base = via.get_start_address()

    cpu.registers.program_counter = 0x1000
    cpu.registers.stack_pointer = 0x01FF
    cpu.flags.carry_i = True
    memory.store8(0x1000, 0x01)

    memory.store8(base + R6522.VIA_REG_IER, 0x80 | R6522.IFR_BIT_T1)
    memory.store8(base + R6522.VIA_REG_T1CL, 0x00)
    memory.store8(base + R6522.VIA_REG_T1CH, 0x00)
    computer.clock_count += 3
    via.execute()
    assert cpu.status.irq_requested is True

    memory.load8(base + R6522.VIA_REG_T1CL)
    cpu.flags.carry_i = False
    cpu.execute(1)

    assert cpu.registers.program_counter == 0x1001
    assert cpu.registers.stack_pointer == 0x01FF


def test_ier_changes_immediately_update_the_cpu_irq_line() -> None:
    computer = JR100Computer(enable_audio=False)
    cpu = computer.cpu_core
    via = computer.via
    memory = computer.memory
    base = via.get_start_address()

    via.set_interrupt(R6522.IFR_BIT_T1)
    assert cpu.status.irq_requested is False

    memory.store8(base + R6522.VIA_REG_IER, 0x80 | R6522.IFR_BIT_T1)
    assert cpu.status.irq_requested is True

    memory.store8(base + R6522.VIA_REG_IER, R6522.IFR_BIT_T1)
    assert cpu.status.irq_requested is False


def test_via_reset_deasserts_the_cpu_irq_line() -> None:
    computer = JR100Computer(enable_audio=False)
    cpu = computer.cpu_core
    via = computer.via
    memory = computer.memory
    base = via.get_start_address()

    memory.store8(base + R6522.VIA_REG_IER, 0x80 | R6522.IFR_BIT_T1)
    via.set_interrupt(R6522.IFR_BIT_T1)
    assert cpu.status.irq_requested is True

    via.reset()

    assert cpu.status.irq_requested is False


def test_loading_via_state_synchronizes_the_cpu_irq_line() -> None:
    computer = JR100Computer(enable_audio=False)
    cpu = computer.cpu_core
    via = computer.via
    memory = computer.memory
    base = via.get_start_address()

    memory.store8(base + R6522.VIA_REG_IER, 0x80 | R6522.IFR_BIT_T1)
    via.set_interrupt(R6522.IFR_BIT_T1)
    asserted_state: dict[str, object] = {}
    via.save_state(asserted_state)

    via.reset()
    assert cpu.status.irq_requested is False

    via.load_state(asserted_state)
    assert cpu.status.irq_requested is True

    cleared_state: dict[str, object] = {}
    via.reset()
    via.save_state(cleared_state)
    via.load_state(asserted_state)
    assert cpu.status.irq_requested is True

    via.load_state(cleared_state)
    assert cpu.status.irq_requested is False
