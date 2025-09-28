"""JR-100 sound processor stub."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class JR100SoundProcessor:
    """Records frequency changes and line on/off events."""

    history: List[Tuple[str, Tuple[float, ...]]] = field(default_factory=list)

    def set_frequency(self, timestamp: float, frequency: float) -> None:
        self.history.append(("set_frequency", (timestamp, frequency)))

    def set_line_on(self) -> None:
        self.history.append(("set_line_on", tuple()))

    def set_line_off(self) -> None:
        self.history.append(("set_line_off", tuple()))
