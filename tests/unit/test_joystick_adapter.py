from __future__ import annotations

from pathlib import Path

from jr100emu.io.joystick import (
    DEFAULT_JOYSTICK_MAPPING,
    GamepadState,
    JoystickAdapter,
    load_mapping_file,
)


def test_axis_mapping_updates_state() -> None:
    adapter = JoystickAdapter()
    assert adapter.current_state() == GamepadState()

    adapter.update_axis(0, -0.8)
    state = adapter.current_state()
    assert state.left is True
    assert state.right is False

    adapter.update_axis(0, 0.0)
    assert adapter.current_state().left is False


def test_button_mapping_and_reset() -> None:
    adapter = JoystickAdapter()

    adapter.update_button(0, True)
    assert adapter.current_state().switch is True

    adapter.reset()
    assert adapter.current_state() == GamepadState()


def test_hat_mapping_support() -> None:
    mapping = {
        "left": ("hat", (0, "x"), -1),
        "right": ("hat", (0, "x"), 1),
        "up": ("hat", (0, "y"), 1),
        "down": ("hat", (0, "y"), -1),
        "switch": ("button", 0, 0.5),
    }
    adapter = JoystickAdapter(mapping)

    adapter.update_hat(0, (-1, 0))
    assert adapter.current_state().left is True

    adapter.update_hat(0, (0, 1))
    state = adapter.current_state()
    assert state.up is True
    assert state.down is False


def test_load_mapping_file_overrides(tmp_path: Path) -> None:
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text("{\"left\": [\"axis\", 0, -0.75]}", encoding="utf-8")

    mapping = load_mapping_file(mapping_file, fallback=DEFAULT_JOYSTICK_MAPPING)
    adapter = JoystickAdapter(mapping)

    adapter.update_axis(0, -0.8)
    assert adapter.current_state().left is True

    adapter.update_axis(0, -0.6)
    assert adapter.current_state().left is False
