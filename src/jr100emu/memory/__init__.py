"""Memory system primitives mirroring the Java implementation."""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol


class Addressable(Protocol):
    """Protocol describing memory mapped components."""

    def get_start_address(self) -> int:
        ...

    def get_end_address(self) -> int:
        ...

    def load8(self, address: int) -> int:
        ...

    def store8(self, address: int, value: int) -> None:
        ...

    def load16(self, address: int) -> int:
        ...

    def store16(self, address: int, value: int) -> None:
        ...


class Memory(Addressable):
    """Generic memory block supporting 8/16-bit accesses."""

    start: int
    length: int
    data: List[int]

    def __init__(self, start: int, length: int) -> None:
        self.start = start & 0xFFFF
        self.length = length
        if length <= 0 or self.start + length > 0x10000:
            raise ValueError("invalid memory range")
        self.data = [0x00] * length

    def get_start_address(self) -> int:
        return self.start

    def get_end_address(self) -> int:
        return self.start + self.length - 1

    def _index(self, address: int) -> int:
        return (address - self.start) % self.length

    def load8(self, address: int) -> int:
        return self.data[self._index(address)] & 0xFF

    def store8(self, address: int, value: int) -> None:
        self.data[self._index(address)] = value & 0xFF

    def load16(self, address: int) -> int:
        index = self._index(address)
        hi = self.data[index] & 0xFF
        lo = self.data[(index + 1) % self.length] & 0xFF
        return ((hi << 8) | lo) & 0xFFFF

    def store16(self, address: int, value: int) -> None:
        index = self._index(address)
        self.data[index] = (value >> 8) & 0xFF
        self.data[(index + 1) % self.length] = value & 0xFF


class RAM(Memory):
    """Readable and writable memory block."""


class ROM(Memory):
    """Read-only memory block."""

    def store8(self, address: int, value: int) -> None:  # pragma: no cover - ROM ignores writes
        return

    def store16(self, address: int, value: int) -> None:  # pragma: no cover - ROM ignores writes
        return


class UnmappedMemory(Addressable):
    """Memory hole returning zeroed data (with JR-100 specific quirk at 0xD000)."""

    def __init__(self, start: int, length: int) -> None:
        self.start = start & 0xFFFF
        self.length = length

    def get_start_address(self) -> int:
        return self.start

    def get_end_address(self) -> int:
        return (self.start + self.length - 1) & 0xFFFF

    def load8(self, address: int) -> int:
        if (address & 0xFFFF) == 0xD000:
            return 0xAA
        return 0x00

    def load16(self, address: int) -> int:
        if (address & 0xFFFF) == 0xD000:
            return 0xAA00
        return 0x0000

    def store8(self, address: int, value: int) -> None:
        return

    def store16(self, address: int, value: int) -> None:
        return


class MemorySystem:
    """Memory mapper dispatching reads/writes to registered devices."""

    def __init__(self) -> None:
        self._space: List[Addressable] = []
        self._map: Dict[type, Addressable] = {}
        self._debug: bool = False

    def allocate_space(self, capacity: int) -> None:
        if capacity <= 0 or capacity > 0x10000:
            raise ValueError("invalid capacity for memory system")
        filler = UnmappedMemory(0, capacity)
        self._space = [filler for _ in range(capacity)]
        self._map = {UnmappedMemory: filler}

    def register_memory(self, memory: Addressable) -> None:
        start = memory.get_start_address() & 0xFFFF
        end = memory.get_end_address() & 0xFFFF
        if start > end:
            raise ValueError("memory range wrapping not supported")
        for address in range(start, end + 1):
            self._space[address] = memory
        self._map[type(memory)] = memory

    def regist_memory(self, memory: Addressable) -> None:
        """Compatibility alias mirroring Java naming."""

        self.register_memory(memory)

    def get_memory(self, cls: type) -> Optional[Addressable]:
        return self._map.get(cls)

    def get_memories(self) -> List[Addressable]:
        return list(self._map.values())

    def load8(self, address: int) -> int:
        addr = address & 0xFFFF
        value = self._space[addr].load8(addr) & 0xFF
        if self._debug:
            print(f"load8: addr={addr:04X} val={value:02X}")
        return value

    def store8(self, address: int, value: int) -> None:
        addr = address & 0xFFFF
        if self._debug:
            print(f"store8: addr={addr:04X} val={value:02X}")
        self._space[addr].store8(addr, value & 0xFF)

    def load16(self, address: int) -> int:
        addr = address & 0xFFFF
        hi = self._space[addr].load8(addr)
        lo_addr = (addr + 1) & 0xFFFF
        lo = self._space[lo_addr].load8(lo_addr)
        value = ((hi << 8) | lo) & 0xFFFF
        if self._debug:
            print(f"load16: addr={addr:04X} val={value:04X}")
        return value

    def store16(self, address: int, value: int) -> None:
        addr = address & 0xFFFF
        if self._debug:
            print(f"store16: addr={addr:04X} val={value:04X}")
        self._space[addr].store8(addr, (value >> 8) & 0xFF)
        lo_addr = (addr + 1) & 0xFFFF
        self._space[lo_addr].store8(lo_addr, value & 0xFF)

    def enable_debug(self, enabled: bool) -> None:
        self._debug = enabled


__all__ = [
    "Addressable",
    "Memory",
    "RAM",
    "ROM",
    "UnmappedMemory",
    "MemorySystem",
]
