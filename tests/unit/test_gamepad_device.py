from __future__ import annotations

from typing import Dict

from jr100emu.emulator.device import GamepadDevice


class RecordingPort:
    def __init__(self) -> None:
        self.state: Dict[str, bool] | None = None

    def set_gamepad_state(self, **kwargs: bool) -> None:
        self.state = dict(kwargs)


class FakeBackend:
    def __init__(self) -> None:
        self.initialize_calls = 0
        self.poll_calls = 0
        self.reset_calls = 0
        self.closed = False

    def initialize(self) -> bool:
        self.initialize_calls += 1
        return True

    def poll(self, adapter) -> bool:
        self.poll_calls += 1
        return adapter.update_button(0, True)

    def reset(self) -> None:
        self.reset_calls += 1

    def close(self) -> None:
        self.closed = True


def test_gamepad_device_applies_backend_state() -> None:
    port = RecordingPort()
    backend = FakeBackend()
    device = GamepadDevice(port=port, backend=backend)

    assert port.state == {
        "left": False,
        "right": False,
        "up": False,
        "down": False,
        "switch": False,
    }

    changed = device.poll()
    assert changed is True
    assert backend.initialize_calls == 1
    assert backend.poll_calls == 1
    assert port.state is not None
    assert port.state["switch"] is True


def test_gamepad_device_reset_resets_backend_and_port() -> None:
    port = RecordingPort()
    backend = FakeBackend()
    device = GamepadDevice(port=port, backend=backend)

    device.poll()
    device.reset()

    assert backend.reset_calls == 1
    assert backend.initialize_calls == 1
    assert port.state == {
        "left": False,
        "right": False,
        "up": False,
        "down": False,
        "switch": False,
    }

    device.poll()
    assert backend.initialize_calls == 2


def test_gamepad_device_disable_stops_backend_usage() -> None:
    port = RecordingPort()
    backend = FakeBackend()
    device = GamepadDevice(port=port, backend=backend)

    device.poll()
    device.disable()
    assert backend.closed is True

    backend.poll_calls = 0
    changed = device.poll()
    assert changed is False
    assert backend.poll_calls == 0
