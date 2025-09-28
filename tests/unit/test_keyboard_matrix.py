from __future__ import annotations

from jr100emu.jr100.keyboard import JR100Keyboard


def test_keyboard_press_and_release_updates_matrix() -> None:
    keyboard = JR100Keyboard()

    matrix = keyboard.get_key_matrix()
    assert len(matrix) == 9
    assert all(value == 0 for value in matrix)

    keyboard.press(1, 0)
    assert keyboard.get_key_matrix()[1] & 0x01 == 0x01

    keyboard.release(1, 0)
    assert keyboard.get_key_matrix()[1] & 0x01 == 0x00

    keyboard.press(0, 4)
    keyboard.clear()
    assert all(value == 0 for value in keyboard.get_key_matrix())
