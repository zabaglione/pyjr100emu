"""Generic data file helpers mirroring the Java implementation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from jr100emu.emulator.file.program import (
    AddressRegion,
    ProgramInfo,
    ProgramLoadError,
    BASIC_START_ADDRESS,
    BASIC_POINTER_BASE,
    BASIC_POINTER_COUNT,
    BASIC_TERMINATOR,
    load_basic_text,
)
from jr100emu.memory import MemorySystem


class DataFile:
    """Base class for JR-100 compatible data files."""

    FORMAT_UNKNOWN = 0
    FORMAT_PROG = 1
    FORMAT_BASIC_TEXT = 2
    FORMAT_BINARY_TEXT = 3

    STATUS_SUCCESS = 0
    STATUS_NO_ADDRESS = 1
    STATUS_CHECK_SUM_ERROR = 2
    STATUS_INVALID_FORMAT = 3
    STATUS_FILE_NOT_FOUND = 4
    STATUS_IO_ERROR = 5
    STATUS_UNEXPECTED_ERROR = 6
    STATUS_MEMORY_FULL = 7

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self.error_status: int = self.STATUS_SUCCESS
        self.error_message: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_jr100(self, memory: MemorySystem) -> ProgramInfo:
        raise NotImplementedError

    def save_jr100(self, program: ProgramInfo, version: int = 1) -> None:
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Error handling helpers
    # ------------------------------------------------------------------
    def set_error(self, status: int, message: Optional[str] = None) -> None:
        self.error_status = status
        self.error_message = message

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    @property
    def path(self) -> Path:
        return self._path

    @staticmethod
    def _read_magic(path: Path) -> Optional[bytes]:
        try:
            with path.open("rb") as handle:
                return handle.read(4)
        except OSError:
            return None

    @staticmethod
    def get_extension(filename: str | Path | None) -> Optional[str]:
        if filename is None:
            return None
        name = str(filename)
        index = name.rfind(".")
        if index == -1:
            return None
        return name[index + 1 :].lower()

    @classmethod
    def is_prog_file(cls, path: str | Path) -> bool:
        ext = cls.get_extension(path)
        if ext in {"prg", "prog"}:
            return True
        magic = cls._read_magic(Path(path))
        return magic == b"PROG"

    @classmethod
    def is_basic_text_file(cls, path: str | Path) -> bool:
        ext = cls.get_extension(path)
        return ext in {"txt", "bas"}


class TextFormatFile(DataFile):
    """Base class for text based formats."""

    pass


class BasicTextFormatFile(TextFormatFile):
    """BASIC text loader/saver built on top of ProgramInfo helpers."""

    def load_jr100(self, memory: MemorySystem) -> ProgramInfo:
        try:
            info = load_basic_text(memory, self.path)
        except FileNotFoundError as exc:
            self.set_error(self.STATUS_FILE_NOT_FOUND, str(exc))
            return ProgramInfo(memory=memory)
        except (OSError, ProgramLoadError) as exc:
            self.set_error(self.STATUS_INVALID_FORMAT, str(exc))
            return ProgramInfo(memory=memory)
        self.set_error(self.STATUS_SUCCESS, None)
        return info

    def save_jr100(self, program: ProgramInfo, version: int = 1) -> None:
        memory = program.memory
        try:
            with self.path.open("w", encoding="utf-8") as handle:
                for line_number, content in self._iterate_basic_lines(memory):
                    handle.write(f"{line_number} {content}\n")
        except OSError as exc:
            self.set_error(self.STATUS_IO_ERROR, str(exc))
            return
        self.set_error(self.STATUS_SUCCESS, None)

    def _iterate_basic_lines(self, memory: MemorySystem) -> Iterable[tuple[int, str]]:
        addr = BASIC_START_ADDRESS
        end_marker = BASIC_TERMINATOR << 8 | BASIC_TERMINATOR
        seen = set()
        while True:
            if addr in seen:
                # Broken BASIC area – avoid infinite loop
                break
            seen.add(addr)
            line_number = memory.load16(addr) & 0xFFFF
            if line_number in (end_marker, 0x0000):
                break
            addr = (addr + 2) & 0xFFFF
            bytes_values: List[int] = []
            value = memory.load8(addr) & 0xFF
            while value != 0x00:
                bytes_values.append(value)
                addr = (addr + 1) & 0xFFFF
                value = memory.load8(addr) & 0xFF
            addr = (addr + 1) & 0xFFFF
            text = self._encode_text(bytes_values)
            yield line_number, text

    @staticmethod
    def _encode_text(values: Sequence[int]) -> str:
        parts: List[str] = []
        for value in values:
            value &= 0xFF
            if 0x20 <= value <= 0x7E:
                parts.append(chr(value))
            else:
                parts.append(f"\\{value:02X}")
        return "".join(parts)


class BinaryTextFormatFile(TextFormatFile):
    """Binary text dump handler compatible with the Java implementation."""

    def load_jr100(self, memory: MemorySystem) -> ProgramInfo:
        info = ProgramInfo(memory=memory)
        info.basic_area = False
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            self.set_error(self.STATUS_FILE_NOT_FOUND, str(exc))
            return info
        except OSError as exc:
            self.set_error(self.STATUS_IO_ERROR, str(exc))
            return info

        lines = text.splitlines()
        file_head = True
        current_addr: Optional[int] = None
        start_addr: Optional[int] = None
        last_addr: Optional[int] = None

        for raw_line in lines:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            tokens = line.split()
            if not tokens:
                continue
            try:
                addr_token = tokens[0]
                addr = int(addr_token, 16) & 0xFFFF
            except ValueError:
                self.set_error(self.STATUS_INVALID_FORMAT, f"invalid address: {addr_token}")
                return info

            if file_head:
                start_addr = addr
                file_head = False
            elif last_addr is not None and addr != ((last_addr + 1) & 0xFFFF):
                if start_addr is not None:
                    info.add_region(start_addr, last_addr)
                start_addr = addr
            current_addr = addr
            checksum = 0
            idx = 1
            while idx < len(tokens):
                token = tokens[idx]
                if token == ":":
                    idx += 1
                    if idx >= len(tokens):
                        self.set_error(self.STATUS_INVALID_FORMAT, "checksum missing")
                        return info
                    try:
                        expected = int(tokens[idx], 16) & 0xFF
                    except ValueError:
                        self.set_error(self.STATUS_INVALID_FORMAT, f"invalid checksum: {tokens[idx]}")
                        return info
                    if checksum & 0xFF != expected:
                        self.set_error(self.STATUS_CHECK_SUM_ERROR, raw_line)
                        return info
                    break
                try:
                    value = int(token, 16) & 0xFF
                except ValueError:
                    self.set_error(self.STATUS_INVALID_FORMAT, f"invalid value: {token}")
                    return info
                if current_addr is None:
                    self.set_error(self.STATUS_NO_ADDRESS, "address missing before data")
                    return info
                memory.store8(current_addr, value)
                checksum = (checksum + value) & 0xFF
                last_addr = current_addr
                current_addr = (current_addr + 1) & 0xFFFF
                idx += 1

            if idx == len(tokens):
                # No checksum delimiter found
                self.set_error(self.STATUS_INVALID_FORMAT, "line missing checksum delimiter")
                return info

        if start_addr is not None and last_addr is not None and last_addr >= start_addr:
            info.add_region(start_addr, last_addr)

        self.set_error(self.STATUS_SUCCESS, None)
        return info

    def save_jr100(self, program: ProgramInfo, version: int = 1) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as handle:
                memory = program.memory
                regions = list(program.address_regions)
                if program.basic_area and not regions:
                    pointer_index = BASIC_POINTER_BASE + (BASIC_POINTER_COUNT - 1) * 2
                    end_pointer = memory.load16(pointer_index) & 0xFFFF
                    if end_pointer > BASIC_START_ADDRESS:
                        end = max(BASIC_START_ADDRESS, end_pointer - 1)
                        regions.append(AddressRegion(BASIC_START_ADDRESS, end))

                for region in regions:
                    for line in self._dump_region(memory, region.start, region.end):
                        handle.write(line)
        except OSError as exc:
            self.set_error(self.STATUS_IO_ERROR, str(exc))
            return
        self.set_error(self.STATUS_SUCCESS, None)

    def _dump_region(self, memory: MemorySystem, start: int, end: int) -> Iterable[str]:
        line_addr = start & 0xFFFF
        checksum = 0
        bytes_in_line: List[int] = []
        current_addr = start
        while current_addr <= end:
            if len(bytes_in_line) == 0:
                line_addr = current_addr & 0xFFFF
            value = memory.load8(current_addr) & 0xFF
            checksum = (checksum + value) & 0xFF
            bytes_in_line.append(value)
            if len(bytes_in_line) == 16:
                yield self._format_line(line_addr, bytes_in_line, checksum)
                bytes_in_line = []
                checksum = 0
            current_addr += 1
        if bytes_in_line:
            yield self._format_line(line_addr, bytes_in_line, checksum)

    @staticmethod
    def _format_line(address: int, values: Sequence[int], checksum: int) -> str:
        parts = [f"{address:04X}"]
        for value in values:
            parts.append(f"{value:02X}")
        parts.append(":")
        parts.append(f"{checksum:02X}")
        return " ".join(parts) + "\n"
__all__ = [
    "DataFile",
    "TextFormatFile",
    "BasicTextFormatFile",
    "BinaryTextFormatFile",
]
