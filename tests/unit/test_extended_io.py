"""Extended IO port tests."""

from jr100emu.jr100.memory import ExtendedIOPort


def test_gamepad_state_bits_are_active_low() -> None:
    port = ExtendedIOPort(0xCC00)
    port.set_gamepad_state(right=True, up=True, switch=True)

    assert port.gamepad_status == 0xEA
    assert (port.gamepad_status & 0x01) == 0  # right pressed
    assert (port.gamepad_status & 0x04) == 0  # up pressed
    assert (port.gamepad_status & 0x10) == 0  # switch pressed
    assert port.gamepad_status & 0x02  # left released
    assert port.gamepad_status & 0x08  # down released
