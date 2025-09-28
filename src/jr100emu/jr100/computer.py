"""JR-100 system wiring, mirroring the Java `JR100` class."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional

from jr100emu.cpu.cpu import MB8861
from jr100emu.jr100.display import JR100Display
from jr100emu.jr100.hardware import JR100Hardware
from jr100emu.jr100.keyboard import JR100Keyboard
from jr100emu.jr100.memory import (
    BasicRom,
    ExtendedIOPort,
    MainRam,
    UserDefinedCharacterRam,
    VideoRam,
)
from jr100emu.jr100.r6522 import JR100R6522
from jr100emu.jr100.sound import JR100SoundProcessor
from jr100emu.emulator.file import ProgramInfo, ProgramLoadError, load_basic_text, load_prog
from jr100emu.memory import MemorySystem
from jr100emu.system.computer import Computer


@dataclass
class JR100Computer(Computer):
    """Concrete JR-100 computer model."""

    hardware: JR100Hardware
    via: JR100R6522
    cpu_core: MB8861
    program_info: Optional[ProgramInfo] = None

    MEMORY_CAPACITY = 0x10000
    MAIN_RAM_STANDARD = 0x4000
    MAIN_RAM_EXTENDED = 0x8000
    USER_CHAR_START = 0xC000
    USER_CHAR_LENGTH = 0x0100
    VIDEO_RAM_START = 0xC100
    VIDEO_RAM_LENGTH = 0x0300
    VIA_START = 0xC800
    EXT_IO_START = 0xCC00
    BASIC_ROM_START = 0xE000
    BASIC_ROM_LENGTH = 0x2000

    ENV_ROM_PATH = "JR100EMU_ROM"

    def __init__(self, rom_path: str | os.PathLike[str] | None = None, *, extended_ram: bool = False) -> None:
        memory = MemorySystem()
        memory.allocate_space(self.MEMORY_CAPACITY)

        display = JR100Display()
        keyboard = JR100Keyboard()
        sound = JR100SoundProcessor()
        hardware = JR100Hardware(
            memory=memory,
            display=display,
            keyboard=keyboard,
            sound_processor=sound,
        )

        super().__init__(hardware=hardware)

        self._extended_ram = extended_ram
        self._rom_path = self._resolve_rom_path(rom_path)
        self.program_info = None

        self._install_memory_map(memory)
        self.cpu_core = MB8861(self)
        self.set_cpu(self.cpu_core)
        self.cpu_core.reset()
        self.cpu_core.execute(1)

        self.via = JR100R6522(self, self.VIA_START)
        memory.register_memory(self.via)
        self.add_device(self.via)

    # ------------------------------------------------------------------
    # Memory installation
    # ------------------------------------------------------------------
    def _install_memory_map(self, memory: MemorySystem) -> None:
        main_ram_length = self.MAIN_RAM_EXTENDED if self._extended_ram else self.MAIN_RAM_STANDARD
        main_ram = MainRam(0x0000, main_ram_length)
        memory.register_memory(main_ram)

        user_chars = UserDefinedCharacterRam(self.USER_CHAR_START, self.USER_CHAR_LENGTH)
        user_chars.set_display(self.hardware.display)
        memory.register_memory(user_chars)

        video_ram = VideoRam(self.VIDEO_RAM_START, self.VIDEO_RAM_LENGTH)
        video_ram.set_display(self.hardware.display)
        memory.register_memory(video_ram)

        ext_port = ExtendedIOPort(self.EXT_IO_START)
        memory.register_memory(ext_port)

        rom_path = str(self._rom_path) if self._rom_path is not None else ""
        basic_rom = BasicRom(rom_path, self.BASIC_ROM_START, self.BASIC_ROM_LENGTH)
        memory.register_memory(basic_rom)

    # ------------------------------------------------------------------
    # Accessors mirroring Java behaviour
    # ------------------------------------------------------------------
    def get_clock_frequency(self) -> float:
        return self.cpu_clock_frequency

    def set_clock_frequency(self, frequency: float) -> None:
        self.cpu_clock_frequency = frequency

    def request_reset(self) -> None:
        self.cpu_core.reset()

    @property
    def memory(self) -> MemorySystem:
        return self.hardware.memory

    def load_basic_rom(self, path: str) -> None:
        rom = BasicRom(path, self.BASIC_ROM_START, self.BASIC_ROM_LENGTH)
        self.hardware.memory.register_memory(rom)

    def has_extended_ram(self) -> bool:
        return self._extended_ram

    def attach_external_io(self, io: ExtendedIOPort) -> None:
        self.hardware.memory.register_memory(io)

    # ------------------------------------------------------------------
    # ROM helpers
    # ------------------------------------------------------------------
    def _resolve_rom_path(self, rom_path: str | os.PathLike[str] | None) -> Optional[Path]:
        candidates: list[Path] = []
        if rom_path is not None and str(rom_path):
            candidates.append(Path(rom_path))
        env_value = os.getenv(self.ENV_ROM_PATH)
        if env_value:
            candidates.append(Path(env_value))
        base = Path(__file__).resolve().parents[3]
        candidates.append(base / "datas" / "jr100rom.prg")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    @property
    def rom_path(self) -> Optional[Path]:
        return self._rom_path

    # ------------------------------------------------------------------
    # User program loading
    # ------------------------------------------------------------------
    def load_user_program(self, path: str | os.PathLike[str]) -> ProgramInfo:
        file_path = Path(path)
        suffix = file_path.suffix.lower()
        if suffix in {".prg", ".prog"}:
            info = load_prog(self.memory, file_path)
        elif suffix == ".bas":
            info = load_basic_text(self.memory, file_path)
        else:
            raise ProgramLoadError(f"unsupported program format: {file_path.suffix}")
        if not info.name:
            info.name = file_path.stem.upper()
        info.path = file_path
        self.program_info = info
        if self.cpu_core is not None:
            self.cpu_core.reset()
            # Ensure reset vector is fetched before returning.
            self.cpu_core.execute(1)
        return info
