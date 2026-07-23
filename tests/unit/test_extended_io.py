"""Extended IO port tests."""

from jr100emu.jr100.memory import ExtendedIOPort


def test_gamepad_state_bits_are_active_high() -> None:
    port = ExtendedIOPort(0xCC00)
    port.set_gamepad_state(right=True, up=True, switch=True)

    assert port.gamepad_status == 0x15
    assert port.gamepad_status & 0x01  # right pressed
    assert port.gamepad_status & 0x04  # up pressed
    assert port.gamepad_status & 0x10  # switch pressed
    assert (port.gamepad_status & 0x02) == 0  # left released
    assert (port.gamepad_status & 0x08) == 0  # down released


def test_gamepad_status_is_only_read_from_cc02() -> None:
    port = ExtendedIOPort(0xCC00)
    port.set_gamepad_state(left=True)

    assert port.load8(0xCC01) == 0x00
    assert port.load8(0xCC02) == 0x02
