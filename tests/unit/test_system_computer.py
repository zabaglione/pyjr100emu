from __future__ import annotations

from typing import List, Tuple

from jr100emu.emulator.device import GamepadDevice
from jr100emu.memory import MemorySystem
from jr100emu.system.computer import Computer


class StubCPU:
    def __init__(self) -> None:
        self.calls: List[Tuple[str, int]] = []
        self.computer: Computer | None = None

    def execute(self, cycles: int) -> int:
        self.calls.append(("execute", cycles))
        if self.computer is not None:
            self.computer.clock_count += cycles
        return 0

    def reset(self) -> None:
        self.calls.append(("reset", 0))


class DummyDisplay:
    def __init__(self) -> None:
        self.refresh_calls = 0

    def refresh(self) -> None:
        self.refresh_calls += 1


class DummyPort:
    def __init__(self) -> None:
        self.state = {}

    def set_gamepad_state(self, **kwargs) -> None:
        self.state = dict(kwargs)


class SimpleHardware:
    def __init__(self) -> None:
        memory = MemorySystem()
        memory.allocate_space(0x10000)
        self.memory = memory
        self.display = DummyDisplay()
        self._port = DummyPort()
        self.gamepad = GamepadDevice(port=self._port)


def make_hardware() -> SimpleHardware:
    return SimpleHardware()


def test_power_on_and_tick_advances_cpu() -> None:
    computer = Computer(make_hardware())
    cpu = StubCPU()
    computer.set_cpu(cpu)

    computer.power_on()

    assert computer.get_running_status() == computer.STATUS_RUNNING
    assert computer.clock_count == 0
    assert computer.base_time != 0

    computer.tick(32)
    assert ("execute", 32) in cpu.calls
    assert computer.clock_count == 32


def test_pause_and_resume_controls_execution() -> None:
    computer = Computer(make_hardware())
    cpu = StubCPU()
    computer.set_cpu(cpu)
    computer.power_on()

    computer.tick(8)
    computer.pause()
    calls_before = len(cpu.calls)
    computer.tick(16)
    assert len(cpu.calls) == calls_before
    assert computer.get_running_status() == computer.STATUS_PAUSED

    base_before = computer.base_time
    computer.resume()
    assert computer.get_running_status() == computer.STATUS_RUNNING
    assert computer.base_time != base_before
    computer.tick(4)
    assert ("execute", 4) in cpu.calls


def test_power_off_stops_execution() -> None:
    computer = Computer(make_hardware())
    cpu = StubCPU()
    computer.set_cpu(cpu)
    computer.power_on()
    computer.power_off()
    assert computer.get_running_status() == computer.STATUS_STOPPED
    computer.tick(10)
    assert ("execute", 10) not in cpu.calls


def test_reset_invokes_cpu_and_clears_clock() -> None:
    computer = Computer(make_hardware())
    cpu = StubCPU()
    computer.set_cpu(cpu)
    computer.power_on()
    computer.tick(5)
    computer.reset()
    assert ("reset", 0) in cpu.calls
    assert computer.clock_count == 0


def test_save_and_load_state_roundtrip() -> None:
    computer = Computer(make_hardware())
    computer.power_on()
    computer.tick(12)
    computer.pause()

    state: dict[str, object] = {}
    computer.save_state(state)

    computer.clock_count = 99
    computer.set_running_status(computer.STATUS_RUNNING)
    computer.base_time = 123

    computer.load_state(state)
    assert computer.clock_count == 12
    assert computer.get_running_status() == computer.STATUS_PAUSED
    assert computer.base_time == state["computer.baseTime"]


def test_periodic_tasks_follow_running_status() -> None:
    hardware = make_hardware()
    computer = Computer(hardware)
    cpu = StubCPU()
    computer.set_cpu(cpu)
    computer.power_on()

    refresh_interval = max(1, computer._refresh_interval_clocks)
    poll_interval = max(1, computer._gamepad_poll_interval)

    computer.tick(refresh_interval + poll_interval + 5)
    assert hardware.display.refresh_calls > 0
    assert hardware.gamepad.poll_count > 0

    computer.pause()
    paused_refresh = hardware.display.refresh_calls
    paused_poll = hardware.gamepad.poll_count
    computer.tick(refresh_interval + poll_interval + 5)
    assert hardware.display.refresh_calls == paused_refresh
    assert hardware.gamepad.poll_count == paused_poll

    computer.resume()
    computer.tick(refresh_interval + poll_interval + 5)
    assert hardware.display.refresh_calls > paused_refresh
    assert hardware.gamepad.poll_count > paused_poll
