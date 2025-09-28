"""Program loaders for JR-100 user programs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, List, Optional, Sequence

from jr100emu.memory import MemorySystem

BASIC_START_ADDRESS = 0x0246
BASIC_POINTER_BASE = 0x0006
BASIC_POINTER_COUNT = 4
BASIC_TERMINATOR = 0xDF
MAX_BASIC_LINE_LENGTH = 72

PROG_MAGIC = b"PROG"
PROG_VERSION_MIN = 1
PROG_VERSION_MAX = 2
PROG_MAX_PROGRAM_NAME_LENGTH = 256
PROG_MAX_PROGRAM_LENGTH = 65536
PROG_MAX_COMMENT_LENGTH = 1024
PROG_MAX_BINARY_SECTIONS = 256

SECTION_PNAM = 0x4D414E50  # "PNAM"
SECTION_PBAS = 0x53414250  # "PBAS"
SECTION_PBIN = 0x4E494250  # "PBIN"
SECTION_CMNT = 0x544E4D43  # "CMNT"


class ProgramLoadError(RuntimeError):
    """Raised when a user program cannot be read."""


@dataclass
class AddressRegion:
    start: int
    end: int
    comment: str = ""


@dataclass
class ProgramInfo:
    memory: MemorySystem
    name: str = ""
    comment: str = ""
    basic_area: bool = False
    address_regions: List[AddressRegion] = field(default_factory=list)
    path: Optional[Path] = None

    def add_region(self, start: int, end: int, comment: str = "") -> None:
        self.address_regions.append(AddressRegion(start, end, comment))


def load_prog(memory: MemorySystem, path: str | Path) -> ProgramInfo:
    """Load a JR-100 PROG container into memory."""

    file_path = Path(path)
    with file_path.open("rb") as stream:
        magic = stream.read(4)
        if magic != PROG_MAGIC:
            raise ProgramLoadError("invalid PROG magic")
        version = _read_u32(stream)
        if version < PROG_VERSION_MIN or version > PROG_VERSION_MAX:
            raise ProgramLoadError(f"unsupported PROG version: {version}")
        info = ProgramInfo(memory=memory, path=file_path)
        if version == 1:
            _load_prog_v1(stream, info)
        else:
            _load_prog_v2(stream, info)
        if not info.name:
            info.name = file_path.stem.upper()
        return info


def load_basic_text(memory: MemorySystem, path: str | Path, *, encoding: str = "utf-8") -> ProgramInfo:
    """Load JR-100 BASIC text (with escape sequences) into memory."""

    file_path = Path(path)
    info = ProgramInfo(memory=memory, basic_area=True, path=file_path, name=file_path.stem.upper())

    addr = BASIC_START_ADDRESS
    end_addr_limit = 0x7FFF  # Matches Java implementation

    with file_path.open("r", encoding=encoding) as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\r\n")
            canonical = _canonicalize_basic_line(line)
            if not canonical:
                continue
            line_number, rest = _extract_basic_line_number(canonical, raw_line)
            digits_length = 2
            if addr + digits_length > end_addr_limit:
                raise ProgramLoadError("basic program does not fit in memory")
            memory.store16(addr, line_number)
            addr += digits_length
            line_length = digits_length

            for byte in _encode_basic_content(rest, raw_line):
                if addr > end_addr_limit:
                    raise ProgramLoadError("basic program does not fit in memory")
                memory.store8(addr, byte)
                addr += 1
                line_length += 1

            if line_length > MAX_BASIC_LINE_LENGTH:
                raise ProgramLoadError(f"line too long: {raw_line.rstrip()}\n")
            if addr > end_addr_limit:
                raise ProgramLoadError("basic program does not fit in memory")
            memory.store8(addr, 0x00)
            addr += 1

    last_data_address = addr - 1
    _finalize_basic(memory, last_data_address)
    info.add_region(BASIC_START_ADDRESS, last_data_address)
    return info


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _read_u32(stream: BinaryIO) -> int:
    data = stream.read(4)
    if len(data) != 4:
        raise ProgramLoadError("unexpected end of file")
    return int.from_bytes(data, "little", signed=False)


def _read_bytes(stream: BinaryIO, length: int) -> bytes:
    data = stream.read(length)
    if len(data) != length:
        raise ProgramLoadError("unexpected end of file")
    return data


def _read_utf8(stream: BinaryIO, *, max_length: int) -> str:
    length = _read_u32(stream)
    if length < 0 or length > max_length:
        raise ProgramLoadError("string length out of range")
    data = _read_bytes(stream, length)
    return data.decode("utf-8") if length else ""


def _load_prog_v1(stream: BinaryIO, info: ProgramInfo) -> None:
    memory = info.memory
    name = _read_utf8(stream, max_length=PROG_MAX_PROGRAM_NAME_LENGTH)
    start = _read_u32(stream)
    length = _read_u32(stream)
    if start + length > PROG_MAX_PROGRAM_LENGTH:
        raise ProgramLoadError("program exceeds PROG limits")
    flag = _read_u32(stream)
    payload = _read_bytes(stream, length)
    _write_prog_block(memory, start, payload)
    if flag == 0:
        final_addr = start + length - 1 if length else start - 1
        _finalize_basic(memory, final_addr)
        info.basic_area = True
        info.add_region(BASIC_START_ADDRESS, final_addr)
    else:
        info.add_region(start, start + length - 1)
    info.name = name or info.name


def _load_prog_v2(stream: BinaryIO, info: ProgramInfo) -> None:
    memory = info.memory
    seen_sections: set[int] = set()
    pbin_count = 0
    while True:
        header = stream.read(8)
        if not header:
            break
        if len(header) != 8:
            if all(byte == 0 for byte in header):
                break
            raise ProgramLoadError("unexpected end of file")
        section_id = int.from_bytes(header[:4], "little", signed=False)
        section_length = int.from_bytes(header[4:], "little", signed=False)
        if section_length < 0:
            raise ProgramLoadError("negative section length")
        payload = _read_bytes(stream, section_length)
        if section_id == SECTION_PNAM:
            if SECTION_PNAM in seen_sections:
                continue
            seen_sections.add(SECTION_PNAM)
            name_len = int.from_bytes(payload[:4], "little", signed=False)
            if name_len > PROG_MAX_PROGRAM_NAME_LENGTH or 4 + name_len > section_length:
                raise ProgramLoadError("invalid PNAM section length")
            info.name = payload[4:4 + name_len].decode("utf-8") if name_len else ""
        elif section_id == SECTION_PBAS:
            if SECTION_PBAS in seen_sections:
                continue
            seen_sections.add(SECTION_PBAS)
            program_length = int.from_bytes(payload[:4], "little", signed=False)
            if program_length + 4 != section_length:
                raise ProgramLoadError("invalid PBAS section length")
            if program_length > PROG_MAX_PROGRAM_LENGTH:
                raise ProgramLoadError("BASIC program too large")
            data = payload[4:4 + program_length]
            _write_prog_block(memory, BASIC_START_ADDRESS, data)
            final_addr = BASIC_START_ADDRESS + program_length - 1 if program_length else BASIC_START_ADDRESS - 1
            _finalize_basic(memory, final_addr)
            info.basic_area = True
            info.add_region(BASIC_START_ADDRESS, final_addr)
        elif section_id == SECTION_PBIN:
            if pbin_count >= PROG_MAX_BINARY_SECTIONS:
                continue
            pbin_count += 1
            if section_length < 8:
                raise ProgramLoadError("invalid PBIN section length")
            start = int.from_bytes(payload[0:4], "little", signed=False)
            data_length = int.from_bytes(payload[4:8], "little", signed=False)
            if start + data_length > PROG_MAX_PROGRAM_LENGTH:
                raise ProgramLoadError("PBIN section exceeds limits")
            data_end = 8 + data_length
            if data_end > section_length:
                raise ProgramLoadError("invalid PBIN data length")
            data = payload[8:data_end]
            comment_offset = data_end
            remaining = section_length - comment_offset
            if remaining == 0:
                comment = ""
            elif remaining >= 4:
                comment_length = int.from_bytes(
                    payload[comment_offset:comment_offset + 4], "little", signed=False
                )
                if comment_length > PROG_MAX_COMMENT_LENGTH:
                    raise ProgramLoadError("invalid PBIN comment")
                comment_start = comment_offset + 4
                comment_end = comment_start + comment_length
                if comment_end > section_length:
                    raise ProgramLoadError("invalid PBIN comment")
                comment = (
                    payload[comment_start:comment_end].decode("utf-8") if comment_length else ""
                )
            else:
                raise ProgramLoadError("invalid PBIN comment length")
            _write_prog_block(memory, start, data)
            info.add_region(start, start + data_length - 1, comment)
        elif section_id == SECTION_CMNT:
            if SECTION_CMNT in seen_sections:
                continue
            seen_sections.add(SECTION_CMNT)
            if section_length < 4:
                raise ProgramLoadError("invalid CMNT section length")
            comment_length = int.from_bytes(payload[:4], "little", signed=False)
            if comment_length > PROG_MAX_COMMENT_LENGTH or 4 + comment_length > section_length:
                raise ProgramLoadError("invalid CMNT payload")
            info.comment = payload[4:4 + comment_length].decode("utf-8") if comment_length else ""
        else:
            continue


def _write_prog_block(memory: MemorySystem, start: int, data: Sequence[int]) -> None:
    for offset, value in enumerate(data):
        memory.store8(start + offset, value)


def _finalize_basic(memory: MemorySystem, final_data_address: int) -> None:
    if final_data_address < BASIC_START_ADDRESS - 1:
        final_data_address = BASIC_START_ADDRESS - 1
    for offset in range(1, 4):
        memory.store8(final_data_address + offset, BASIC_TERMINATOR)
    pointer = final_data_address
    for index in range(BASIC_POINTER_COUNT):
        addr = BASIC_POINTER_BASE + index * 2
        memory.store8(addr, (pointer >> 8) & 0xFF)
        memory.store8(addr + 1, pointer & 0xFF)
        pointer += 1


def _canonicalize_basic_line(line: str) -> str:
    stripped = line.strip()
    return stripped.upper()


def _extract_basic_line_number(line: str, original: str) -> tuple[int, str]:
    index = 0
    while index < len(line) and line[index].isdigit():
        index += 1
    if index == 0:
        raise ProgramLoadError(f"line number missing: {original.rstrip()}\n")
    number = int(line[:index])
    if number < 1 or number > 32767:
        raise ProgramLoadError(f"invalid line number {number}: {original.rstrip()}\n")
    remainder = line[index:].lstrip()
    return number, remainder


def _encode_basic_content(content: str, original: str) -> List[int]:
    result: List[int] = []
    i = 0
    while i < len(content):
        ch = content[i]
        if ch == "\\":
            if i + 2 >= len(content):
                raise ProgramLoadError(f"invalid escape at end of line: {original.rstrip()}\n")
            hex_digits = content[i + 1:i + 3]
            try:
                value = int(hex_digits, 16) & 0xFF
            except ValueError as exc:
                raise ProgramLoadError(f"invalid escape \\{hex_digits} in line: {original.rstrip()}\n") from exc
            result.append(value)
            i += 3
        else:
            result.append(ord(ch) & 0xFF)
            i += 1
    return result
