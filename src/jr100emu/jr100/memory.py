"""JR-100 specific memory mapped components."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from jr100emu.memory import Addressable, RAM, ROM


class MainRam(RAM):
    """Primary RAM block."""


class UserDefinedCharacterRam(RAM):
    """Memory area holding user defined glyphs and mirroring updates to the display."""

    def __init__(self, start: int, length: int) -> None:
        super().__init__(start, length)
        self.display: Optional[object] = None

    def set_display(self, display: object) -> None:
        self.display = display

    def store8(self, address: int, value: int) -> None:
        index = (address - self.start) % self.length
        self.data[index] = value & 0xFF
        if self.display is not None:
            code = index // 8
            line = index % 8
            getattr(self.display, "update_font")(code, line, value & 0xFF)

    def store16(self, address: int, value: int) -> None:
        hi = (value >> 8) & 0xFF
        lo = value & 0xFF
        self.store8(address, hi)
        self.store8(address + 1, lo)


class VideoRam(RAM):
    """Video RAM exposes per-byte updates to the display."""

    def __init__(self, start: int, length: int) -> None:
        super().__init__(start, length)
        self.display: Optional[object] = None

    def set_display(self, display: object) -> None:
        self.display = display

    def _notify_display(self, index: int, value: int) -> None:
        if self.display is None:
            return
        if hasattr(self.display, "write_video_ram"):
            self.display.write_video_ram(index, value & 0xFF)
        else:
            video = getattr(self.display, "video_ram", None)
            if isinstance(video, list) and 0 <= index < len(video):
                video[index] = value & 0xFF

    def store8(self, address: int, value: int) -> None:
        index = (address - self.start) % self.length
        self.data[index] = value & 0xFF
        self._notify_display(index, value)

    def store16(self, address: int, value: int) -> None:
        hi = (value >> 8) & 0xFF
        lo = value & 0xFF
        self.store8(address, hi)
        self.store8(address + 1, lo)


class ExtendedIOPort(Addressable):
    """Handles the JR-100 expansion port mapped at 0xCC00-0xCFFF."""

    DEFAULT_STATUS = 0x00  # bit4: switch, bit3..0: directions (active high)

    def __init__(self, start: int) -> None:
        self.start = start & 0xFFFF
        self.end = (self.start + 0x3FF) & 0xFFFF
        self.gamepad_status = self.DEFAULT_STATUS

    def get_start_address(self) -> int:
        return self.start

    def get_end_address(self) -> int:
        return self.end

    def load8(self, address: int) -> int:
        masked = address & 0xFFFF
        if masked == self.start + 0x02:
            return self.gamepad_status & 0xFF
        return 0x00

    def load16(self, address: int) -> int:
        masked = address & 0xFFFF
        if masked == (self.start + 0x01):
            return self.gamepad_status & 0x00FF
        if masked == (self.start + 0x02):
            return (self.gamepad_status << 8) & 0xFF00
        return 0x0000

    def store8(self, address: int, value: int) -> None:
        if (address & 0xFFFF) == (self.start + 0x02):
            self.gamepad_status = value & 0xFF

    def set_gamepad_state(
        self,
        *,
        left: bool = False,
        right: bool = False,
        up: bool = False,
        down: bool = False,
        switch: bool = False,
    ) -> None:
        status = self.DEFAULT_STATUS
        if right:
            status |= 0x01
        if left:
            status |= 0x02
        if up:
            status |= 0x04
        if down:
            status |= 0x08
        if switch:
            status |= 0x10
        self.set_gamepad_mask(status)

    def set_gamepad_mask(self, mask: int) -> None:
        """Set the active-high JR-100 joystick bits directly."""

        self.gamepad_status = int(mask) & 0x1F

    def store16(self, address: int, value: int) -> None:
        return

    def get_gamepad_status(self) -> int:
        return self.gamepad_status & 0xFF


class RomFormatError(ValueError):
    """Raised when a byte sequence is not a complete JR-100 BASIC ROM."""


@dataclass(frozen=True)
class RomImage:
    """Decoded JR-100 ROM payload and its source metadata."""

    format: str
    start_address: int
    data: bytes
    name: str = ""


def decode_rom_bytes(
    raw: Union[bytes, bytearray, memoryview],
    *,
    start: int,
    length: int,
) -> RomImage:
    """Decode a raw ROM image or the existing JR-100 PROG container."""

    data = bytes(raw)
    if data.startswith(BasicRom.PROG_FILE_ID):
        return _decode_prog_rom(data, start=start, length=length)
    if len(data) == length:
        return RomImage(format="raw", start_address=start, data=data)
    raise RomFormatError(
        f"ROM must be {length} bytes raw or a valid PROG container, got {len(data)} bytes"
    )


def _decode_prog_rom(data: bytes, *, start: int, length: int) -> RomImage:
    if len(data) < 32:
        raise RomFormatError("PROG ROM header is truncated")

    name_length = int.from_bytes(data[8:12], "little")
    name_start = 12
    name_end = name_start + name_length
    metadata_end = name_end + 12
    if name_end < name_start or metadata_end > len(data):
        raise RomFormatError("PROG ROM metadata is truncated")

    name = data[name_start:name_end].decode("ascii", errors="replace")
    start_address = int.from_bytes(data[name_end:name_end + 4], "little")
    data_length = int.from_bytes(data[name_end + 4:name_end + 8], "little")
    payload_start = name_end + 12
    payload_end = payload_start + data_length
    if payload_end > len(data):
        raise RomFormatError("PROG ROM payload is truncated")
    if start_address != start:
        raise RomFormatError(
            f"PROG ROM start address must be 0x{start:04X}, got 0x{start_address:04X}"
        )
    if data_length != length:
        raise RomFormatError(
            f"PROG ROM payload must be {length} bytes, got {data_length} bytes"
        )

    return RomImage(
        format="prog",
        start_address=start_address,
        data=data[payload_start:payload_end],
        name=name,
    )


class BasicRom(ROM):
    """ROM loader that understands the JR-100 PROG container format."""

    PROG_FILE_ID = b"PROG"

    def __init__(
        self,
        filename: str,
        start: int,
        length: int,
        *,
        data: Union[bytes, bytearray, memoryview, None] = None,
    ) -> None:
        super().__init__(start, length)
        self.format: Optional[str] = None
        self.name = ""
        if data is not None:
            self.load_bytes(data)
        elif filename:
            self.read_rom(filename)

    @classmethod
    def from_bytes(
        cls,
        data: Union[bytes, bytearray, memoryview],
        start: int,
        length: int,
    ) -> "BasicRom":
        return cls("", start, length, data=data)

    def get_font_address(self) -> int:
        return 0xE000

    def read_rom(self, filename: str) -> None:
        path = Path(filename)
        if not path.exists():
            return
        try:
            self.load_bytes(path.read_bytes())
        except RomFormatError:
            return

    def load_bytes(self, data: Union[bytes, bytearray, memoryview]) -> RomImage:
        """Replace the ROM contents from a raw image or PROG container."""

        image = decode_rom_bytes(data, start=self.start, length=self.length)
        self.data[:] = image.data
        self.format = image.format
        self.name = image.name
        return image


__all__ = [
    "MainRam",
    "UserDefinedCharacterRam",
    "VideoRam",
    "ExtendedIOPort",
    "RomFormatError",
    "RomImage",
    "decode_rom_bytes",
    "BasicRom",
]
