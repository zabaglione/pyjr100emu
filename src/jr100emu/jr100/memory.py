"""JR-100 specific memory mapped components."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

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

    def __init__(self, start: int) -> None:
        self.start = start & 0xFFFF
        self.end = (self.start + 0x3FF) & 0xFFFF
        self.gamepad_status = 0x00

    def get_start_address(self) -> int:
        return self.start

    def get_end_address(self) -> int:
        return self.end

    def load8(self, address: int) -> int:
        if (address & 0xFFFF) == (self.start + 0x02):
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
        status = 0x00
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
        self.gamepad_status = status

    def store16(self, address: int, value: int) -> None:
        return


class BasicRom(ROM):
    """ROM loader that understands the JR-100 PROG container format."""

    PROG_FILE_ID = b"PROG"

    def __init__(self, filename: str, start: int, length: int) -> None:
        super().__init__(start, length)
        if filename:
            self.read_rom(filename)

    def get_font_address(self) -> int:
        return 0xE000

    def read_rom(self, filename: str) -> None:
        path = Path(filename)
        if not path.exists():
            return
        with path.open("rb") as stream:
            header = stream.read(4)
            if header != self.PROG_FILE_ID:
                return
            stream.read(4)  # skip version field
            name_length = self._read_le32(stream)
            if name_length > 0:
                stream.read(name_length)
            start_address = self._read_le32(stream)
            data_length = self._read_le32(stream)
            self._read_le32(stream)  # skip reserved field
            if data_length <= 0:
                return
            if start_address < self.start or (start_address + data_length) > (self.start + self.length):
                data_length = min(data_length, self.length)
            payload = stream.read(data_length)
            for index, value in enumerate(payload):
                if index >= len(self.data):
                    break
                self.data[index] = value & 0xFF

    def _read_le32(self, stream) -> int:
        raw = stream.read(4)
        if len(raw) != 4:
            return 0
        return raw[0] | (raw[1] << 8) | (raw[2] << 16) | (raw[3] << 24)


__all__ = [
    "MainRam",
    "UserDefinedCharacterRam",
    "VideoRam",
    "ExtendedIOPort",
    "BasicRom",
]
