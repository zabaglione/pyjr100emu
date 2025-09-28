"""JR-100 hardware bundle used by the VIA and other subsystems."""

from __future__ import annotations

from dataclasses import dataclass

from jr100emu.jr100.display import JR100Display
from jr100emu.jr100.keyboard import JR100Keyboard
from jr100emu.jr100.sound import JR100SoundProcessor
from jr100emu.memory import MemorySystem


@dataclass
class JR100Hardware:
    memory: MemorySystem
    display: JR100Display
    keyboard: JR100Keyboard
    sound_processor: JR100SoundProcessor
