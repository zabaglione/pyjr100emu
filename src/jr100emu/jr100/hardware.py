"""JR-100 hardware bundle used by the VIA and other subsystems."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from jr100emu.jr100.display import JR100Display
from jr100emu.jr100.keyboard import JR100Keyboard
from jr100emu.jr100.sound import JR100SoundProcessor
from jr100emu.memory import MemorySystem

if TYPE_CHECKING:  # pragma: no cover - 型補完専用
    from jr100emu.emulator.device import GamepadDevice
else:  # pragma: no cover - 実行時は循環参照を避ける
    GamepadDevice = object


@dataclass
class JR100Hardware:
    memory: MemorySystem
    display: JR100Display
    keyboard: JR100Keyboard
    sound_processor: JR100SoundProcessor
    gamepad: Optional[GamepadDevice] = None
