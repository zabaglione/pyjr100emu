"""Simplified computer scaffold matching the Java API used by devices."""

from __future__ import annotations

from typing import Iterable, Optional

from jr100emu.jr100.hardware import JR100Hardware


class Computer:
    """Host machine tying together hardware, CPU, and mapped devices."""

    def __init__(self, hardware: JR100Hardware, *, cpu_clock_frequency: float = 894_000.0) -> None:
        self.hardware = hardware
        self.cpu_clock_frequency = cpu_clock_frequency
        self.clock_count: int = 0
        self.base_time: int = 0
        self._devices: list[object] = []
        self._cpu: Optional[object] = None

    # ------------------------------------------------------------------
    # CPU integration
    # ------------------------------------------------------------------
    @property
    def cpu(self) -> Optional[object]:
        return self._cpu

    def set_cpu(self, cpu: object) -> None:
        self._cpu = cpu

    def get_cpu(self) -> Optional[object]:
        return self._cpu

    def tick(self, cycles: int) -> None:
        if cycles <= 0:
            return
        if self._cpu is not None:
            self._cpu.execute(cycles)
        else:
            self.clock_count += cycles
        self._execute_devices()

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------
    def add_device(self, device: object) -> None:
        self._devices.append(device)

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
