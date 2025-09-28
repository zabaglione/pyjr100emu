"""Extended IO port tests."""

from jr100emu.jr100.memory import ExtendedIOPort


def test_gamepad_state_bits() -> None:
    port = ExtendedIOPort(0xCC00)
    port.set_gamepad_state(right=True, up=True, switch=True)
    assert port.gamepad_status & 0x01  # right
    assert port.gamepad_status & 0x04  # up
    assert port.gamepad_status & 0x10  # switch
    # left/down should be cleared
    assert (port.gamepad_status & 0x02) == 0
    assert (port.gamepad_status & 0x08) == 0
