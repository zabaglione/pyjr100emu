"""Tests for the R6522 VIA implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from jr100emu.via.r6522 import R6522
from jr100emu.jr100.r6522 import JR100R6522
from jr100emu.jr100.display import JR100Display
from jr100emu.jr100.keyboard import JR100Keyboard
from jr100emu.jr100.sound import JR100SoundProcessor
from jr100emu.jr100.hardware import JR100Hardware
from jr100emu.memory import MemorySystem


@dataclass
class DummyComputer:
    clock_count: int = 0
    base_time: int = 0
    hardware: object | None = None


def make_via(start_address: int = 0xC800) -> Tuple[R6522, DummyComputer]:
    computer = DummyComputer()
    via = R6522(computer, start_address)
    return via, computer


def make_jr100_via() -> Tuple[JR100R6522, DummyComputer, JR100Display, JR100Keyboard, JR100SoundProcessor]:
    display = JR100Display()
    keyboard = JR100Keyboard()
    keyboard.set_key_matrix([0x00, 0x12] + [0xFF] * 14)
    sound = JR100SoundProcessor()
    memory = MemorySystem()
    memory.allocate_space(0x10000)
    hardware = JR100Hardware(memory=memory, display=display, keyboard=keyboard, sound_processor=sound)
    computer = DummyComputer(hardware=hardware)
    via = JR100R6522(computer, 0xC800)
    return via, computer, display, keyboard, sound


def test_timer1_square_wave_sets_irq_and_toggles_pb7() -> None:
    via, computer = make_via()

    base = via.get_start_address()
    via.store8(base + R6522.VIA_REG_ACR, 0xC0)
    via.store8(base + R6522.VIA_REG_T1CL, 0x01)
    via.store8(base + R6522.VIA_REG_T1CH, 0x00)

    initial_pb7 = via.input_port_b_bit(7)

    computer.clock_count += 6
    via.execute()

    assert via._state.IFR & R6522.IFR_BIT_T1
    assert via.input_port_b_bit(7) != initial_pb7


def test_timer2_timed_mode_raises_interrupt() -> None:
    via, computer = make_via()

    base = via.get_start_address()
    via.store8(base + R6522.VIA_REG_T2CL, 0x01)
    via.store8(base + R6522.VIA_REG_T2CH, 0x00)

    computer.clock_count += 4
    via.execute()

    assert via._state.IFR & R6522.IFR_BIT_T2


def test_timer2_pulse_count_requires_pb6_edges() -> None:
    via, computer = make_via()

    base = via.get_start_address()
    via.store8(base + R6522.VIA_REG_ACR, 0x20)
    via.store8(base + R6522.VIA_REG_T2CL, 0x01)
    via.store8(base + R6522.VIA_REG_T2CH, 0x00)

    via.set_port_b(6, 1)
    computer.clock_count += 1
    via.execute()

    for _ in range(2):
        via.set_port_b(6, 0)
        computer.clock_count += 1
        via.execute()
        via.set_port_b(6, 1)
        computer.clock_count += 1
        via.execute()

    assert via._state.IFR & R6522.IFR_BIT_T2


def test_jr100_font_switch_tracks_portb5() -> None:
    via, computer, display, _, _ = make_jr100_via()
    base = via.get_start_address()

    via.store8(base + R6522.VIA_REG_DDRB, 0xFF)
    via.store8(base + R6522.VIA_REG_IORB, 0x20)
    assert display.current_font == JR100Display.FONT_USER_DEFINED

    via.store8(base + R6522.VIA_REG_IORB, 0x00)
    assert display.current_font == JR100Display.FONT_NORMAL


def test_jr100_keyboard_matrix_updates_portb() -> None:
    via, computer, _, keyboard, _ = make_jr100_via()
    base = via.get_start_address()

    via.store8(base + R6522.VIA_REG_DDRB, 0x00)
    via.store8(base + R6522.VIA_REG_IORA, 0x01)

    expected_low = (~keyboard.get_key_matrix()[1]) & 0x1F
    assert (via.input_port_b() & 0x1F) == expected_low


def _sound_events(sound: JR100SoundProcessor, name: str) -> List[Tuple[str, Tuple[float, ...]]]:
    return [entry for entry in sound.history if entry[0] == name]


def test_jr100_sound_frequency_cached() -> None:
    via, computer, _, _, sound = make_jr100_via()
    base = via.get_start_address()

    via.store8(base + R6522.VIA_REG_ACR, 0xC0)
    via.store8(base + R6522.VIA_REG_T1CL, 0x02)
    via.store8(base + R6522.VIA_REG_T1CH, 0x00)

    assert len(_sound_events(sound, "set_frequency")) == 1
    assert len(_sound_events(sound, "set_line_on")) == 1

    via.store8(base + R6522.VIA_REG_T1CL, 0x02)
    via.store8(base + R6522.VIA_REG_T1CH, 0x00)

    assert len(_sound_events(sound, "set_frequency")) == 1
    assert len(_sound_events(sound, "set_line_on")) == 2
