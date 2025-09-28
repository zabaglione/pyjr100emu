"""Tests for JR100 keyboard matrix handling."""

from jr100emu.jr100.keyboard import JR100Keyboard


def test_press_and_release_updates_matrix() -> None:
    kb = JR100Keyboard()
    kb.press(1, 3)
    assert (kb.get_key_matrix()[1] & (1 << 3)) == 0
    kb.release(1, 3)
    assert (kb.get_key_matrix()[1] & (1 << 3)) != 0


def test_set_key_matrix_validation() -> None:
    kb = JR100Keyboard()
    kb.set_key_matrix([0xFF] * 16)
    try:
        kb.set_key_matrix([0xFF] * 15)
    except ValueError:
        pass
    else:
        assert False, "should have raised"
