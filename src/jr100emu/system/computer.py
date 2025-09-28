"""Computer scaffold providing scheduling and control utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
import heapq
import time
from typing import Callable, Iterable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from jr100emu.jr100.hardware import JR100Hardware
else:  # pragma: no cover - used for runtime only
    JR100Hardware = object


class TimeManager:
    """Tracks wall-clock alignment against the emulated clock."""

    def __init__(self) -> None:
        self._base_time_ns = time.perf_counter_ns()

    def reset(self, clock_count: int, frequency_hz: float) -> int:
        now = time.perf_counter_ns()
        if frequency_hz <= 0:
            self._base_time_ns = now
        else:
            simulated_offset = int((clock_count / frequency_hz) * 1_000_000_000)
            self._base_time_ns = now - simulated_offset
        return self._base_time_ns

    def base_time(self) -> int:
        return self._base_time_ns

    def set_base_time(self, base_time: int) -> None:
        self._base_time_ns = base_time


@dataclass(order=True)
class _ComputerEvent:
    clock: int
    order: int
    handler: Callable[["Computer"], None] = field(compare=False)
    name: str = field(default="", compare=False)

    def apply(self, computer: "Computer") -> None:
        self.handler(computer)


class EventQueue:
    """Minimal priority queue mirroring Java EventQueue semantics."""

    def __init__(self) -> None:
        self._heap: List[_ComputerEvent] = []

    def add(self, event: _ComputerEvent) -> None:
        heapq.heappush(self._heap, event)

    def pop_ready(self, clock: int) -> List[_ComputerEvent]:
        ready: List[_ComputerEvent] = []
        while self._heap and self._heap[0].clock <= clock:
            ready.append(heapq.heappop(self._heap))
        return ready

    def clear(self) -> None:
        self._heap.clear()


class Computer:
    """Host machine tying together hardware, CPU, and mapped devices."""

    STATUS_RUNNING = 0
    STATUS_PAUSED = 1
    STATUS_STOPPED = 2

    def __init__(self, hardware: JR100Hardware, *, cpu_clock_frequency: float = 894_000.0) -> None:
        self.hardware = hardware
        self.cpu_clock_frequency = cpu_clock_frequency
        self.clock_count: int = 0
        self.base_time: int = 0
        self._devices: list[object] = []
        self._cpu: Optional[object] = None
        self._running_status: int = self.STATUS_STOPPED
        self._event_queue = EventQueue()
        self._event_counter = 0
        self._time_manager = TimeManager()
        self.refresh_rate: float = 1.0 / 60.0
        self._refresh_interval_clocks: int = max(1, int(self.refresh_rate * self.cpu_clock_frequency))
        self._gamepad_poll_interval: int = max(1, int(self.cpu_clock_frequency / 120.0))
        self._display_refresh_active: bool = False
        self._gamepad_poll_active: bool = False
        self.base_time = self._time_manager.reset(self.clock_count, self.cpu_clock_frequency)

    # ------------------------------------------------------------------
    # CPU integration
    # ------------------------------------------------------------------
    @property
    def cpu(self) -> Optional[object]:
        return self._cpu

    def set_cpu(self, cpu: object) -> None:
        self._cpu = cpu
        if hasattr(cpu, "computer"):
            setattr(cpu, "computer", self)

    def get_cpu(self) -> Optional[object]:
        return self._cpu

    def tick(self, cycles: int) -> None:
        if cycles <= 0:
            return
        self._process_events()
        if self._running_status != self.STATUS_RUNNING:
            return
        if self._cpu is not None:
            self._cpu.execute(cycles)
        else:
            self.clock_count += cycles
        self._execute_devices()
        self._process_events()

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------
    def add_device(self, device: object) -> None:
        self._devices.append(device)
        if hasattr(device, "computer"):
            setattr(device, "computer", self)

    def add_devices(self, devices: Iterable[object]) -> None:
        for device in devices:
            self.add_device(device)

    @property
    def devices(self) -> list[object]:
        return self._devices

    def _execute_devices(self) -> None:
        for device in self._devices:
            if hasattr(device, "execute"):
                device.execute()

    # ------------------------------------------------------------------
    # Control lifecycle
    # ------------------------------------------------------------------
    def power_on(self) -> None:
        self._run_reset()
        self._running_status = self.STATUS_RUNNING
        self._start_periodic_tasks()

    def power_off(self) -> None:
        if self._running_status == self.STATUS_STOPPED:
            return
        self._schedule_event(lambda comp: comp._apply_power_off(), name="powerOff")

    def reset(self) -> None:
        self._schedule_event(lambda comp: comp._run_reset(), name="reset")

    def pause(self) -> None:
        if self._running_status != self.STATUS_RUNNING:
            return
        self._schedule_event(lambda comp: comp._apply_pause(), name="pause")

    def resume(self) -> None:
        if self._running_status != self.STATUS_PAUSED:
            return
        self._schedule_event(lambda comp: comp._apply_resume(), name="resume")

    def start(self) -> None:
        self.resume()

    def get_running_status(self) -> int:
        return self._running_status

    def set_running_status(self, status: int) -> None:
        if status not in (self.STATUS_RUNNING, self.STATUS_PAUSED, self.STATUS_STOPPED):
            raise ValueError("invalid status")
        if status == self.STATUS_RUNNING:
            self._schedule_event(lambda comp: comp._apply_resume(), name="resume")
        elif status == self.STATUS_PAUSED:
            self._schedule_event(lambda comp: comp._apply_pause(), name="pause")
        else:
            self._schedule_event(lambda comp: comp._apply_power_off(), name="powerOff")

    # ------------------------------------------------------------------
    # Event dispatch helpers
    # ------------------------------------------------------------------
    def _process_events(self) -> None:
        for event in self._event_queue.pop_ready(self.clock_count):
            event.apply(self)

    def _schedule_event(self, handler: Callable[["Computer"], None], delay_cycles: int = 0, *, name: str = "") -> None:
        event_clock = max(self.clock_count + max(delay_cycles, 0), 0)
        event = _ComputerEvent(event_clock, self._event_counter, handler, name)
        self._event_counter += 1
        self._event_queue.add(event)
        if event_clock <= self.clock_count:
            self._process_events()

    def _run_reset(self) -> None:
        active = self._running_status == self.STATUS_RUNNING
        self._stop_periodic_tasks()
        self.clock_count = 0
        self.base_time = self._time_manager.reset(self.clock_count, self.cpu_clock_frequency)
        if self._cpu is not None and hasattr(self._cpu, "reset"):
            self._cpu.reset()
        for device in self._devices:
            if hasattr(device, "reset"):
                device.reset()
        if active:
            self._start_periodic_tasks()

    def _apply_pause(self) -> None:
        if self._running_status != self.STATUS_RUNNING:
            return
        self._running_status = self.STATUS_PAUSED
        self._stop_periodic_tasks()

    def _apply_resume(self) -> None:
        if self._running_status == self.STATUS_RUNNING:
            return
        self._running_status = self.STATUS_RUNNING
        self.base_time = self._time_manager.reset(self.clock_count, self.cpu_clock_frequency)
        self._start_periodic_tasks()

    def _apply_power_off(self) -> None:
        self._running_status = self.STATUS_STOPPED
        self._stop_periodic_tasks()
        self._event_queue.clear()

    def _start_periodic_tasks(self) -> None:
        if self._running_status != self.STATUS_RUNNING:
            return
        display = getattr(self.hardware, "display", None)
        if not self._display_refresh_active and display is not None and hasattr(display, "refresh"):
            self._display_refresh_active = True
            self._schedule_event(self._display_refresh_event, self._refresh_interval_clocks, name="display.refresh")

        gamepad = getattr(self.hardware, "gamepad", None)
        if not self._gamepad_poll_active and gamepad is not None and hasattr(gamepad, "poll"):
            self._gamepad_poll_active = True
            self._schedule_event(self._gamepad_poll_event, self._gamepad_poll_interval, name="gamepad.poll")

    def _stop_periodic_tasks(self) -> None:
        self._display_refresh_active = False
        self._gamepad_poll_active = False

    def _display_refresh_event(self, comp: "Computer") -> None:
        if not comp._display_refresh_active or comp._running_status != comp.STATUS_RUNNING:
            return
        display = getattr(comp.hardware, "display", None)
        if display is not None and hasattr(display, "refresh"):
            try:
                display.refresh()
            except Exception:
                pass
        if comp._display_refresh_active and comp._running_status == comp.STATUS_RUNNING:
            comp._schedule_event(comp._display_refresh_event, comp._refresh_interval_clocks, name="display.refresh")

    def _gamepad_poll_event(self, comp: "Computer") -> None:
        if not comp._gamepad_poll_active or comp._running_status != comp.STATUS_RUNNING:
            return
        gamepad = getattr(comp.hardware, "gamepad", None)
        if gamepad is not None and hasattr(gamepad, "poll"):
            try:
                gamepad.poll()
            except Exception:
                pass
        if comp._gamepad_poll_active and comp._running_status == comp.STATUS_RUNNING:
            comp._schedule_event(comp._gamepad_poll_event, comp._gamepad_poll_interval, name="gamepad.poll")

    # ------------------------------------------------------------------
    # Compatibility helpers (mirroring Java Computer API)
    # ------------------------------------------------------------------
    def get_hardware(self) -> JR100Hardware:
        return self.hardware

    def get_clock_count(self) -> int:
        return self.clock_count

    def get_base_time(self) -> int:
        return self.base_time

    def get_clock_frequency(self) -> float:
        return self.cpu_clock_frequency

    def set_clock_frequency(self, frequency: float) -> None:
        if frequency <= 0:
            raise ValueError("frequency must be positive")
        self.cpu_clock_frequency = frequency
        self.base_time = self._time_manager.reset(self.clock_count, self.cpu_clock_frequency)
        self._refresh_interval_clocks = max(1, int(self.refresh_rate * self.cpu_clock_frequency))
        self._gamepad_poll_interval = max(1, int(self.cpu_clock_frequency / 120.0))
        if self._running_status == self.STATUS_RUNNING:
            self._stop_periodic_tasks()
            self._start_periodic_tasks()

    # ------------------------------------------------------------------
    # State persistence helpers
    # ------------------------------------------------------------------
    def save_state(self, out: dict[str, object]) -> None:
        out["computer.clockCount"] = int(self.clock_count)
        out["computer.baseTime"] = int(self.base_time)
        out["computer.runningStatus"] = int(self._running_status)

    def load_state(self, data: dict[str, object]) -> None:
        self.clock_count = int(data.get("computer.clockCount", 0))
        self.base_time = int(data.get("computer.baseTime", self.base_time))
        status = int(data.get("computer.runningStatus", self.STATUS_STOPPED))
        self._time_manager.set_base_time(self.base_time)
        self._running_status = status
        self._stop_periodic_tasks()
        if status == self.STATUS_RUNNING:
            self._start_periodic_tasks()
