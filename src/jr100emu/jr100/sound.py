"""JR-100 sound processor with optional square-wave playback."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from array import array
from typing import Dict, List, Optional, Tuple


@dataclass
class JR100SoundProcessor:
    """Square wave beeper that mirrors the JR-100 cassette tone output."""

    history: List[Tuple[str, Tuple[float, ...]]] = field(default_factory=list)
    sample_rate: int = 44100
    volume: int = 30
    enable_audio: bool = False

    def __post_init__(self) -> None:
        self._current_frequency: float = 0.0
        self._audio_initialized: bool = False
        self._channel = None
        self._max_rank = 30
        self._table_length = 8192
        self._tables = self._build_tables()
        self._current_table: List[float] = self._tables[0]
        self._delta: float = 0.0
        self._phase: float = 0.0
        self._status: int = 0
        self._sounds: Dict[Tuple[int, int], object] = {}
        self._current_rank = 0
        self._amplitude = self._calculate_amplitude(self.volume)
        self._channel_volume = self._calculate_channel_volume(self.volume)

    # ------------------------------------------------------------------
    # VIA callbacks
    # ------------------------------------------------------------------

    def set_frequency(self, timestamp: float, frequency: float) -> None:
        self.history.append(("set_frequency", (timestamp, frequency)))
        self._current_frequency = frequency
        self._current_rank = self._rank_for_frequency(frequency)
        self._update_playback()

    def set_line_on(self) -> None:
        self.history.append(("set_line_on", tuple()))
        self._status = 1
        self._start_playback()

    def set_line_off(self) -> None:
        self.history.append(("set_line_off", tuple()))
        self._status = 0
        self._stop_playback()

    # ------------------------------------------------------------------
    # Audio control helpers
    # ------------------------------------------------------------------

    def _ensure_mixer(self) -> bool:
        if not self.enable_audio:
            return False
        if self._audio_initialized:
            return True
        try:
            import pygame  # type: ignore

            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=self.sample_rate, size=-16, channels=1)
            self._channel = pygame.mixer.Channel(0)
            self._audio_initialized = True
        except Exception:
            self.enable_audio = False
            self._channel = None
            self._audio_initialized = False
        return self._audio_initialized

    def _rank_for_frequency(self, frequency: float) -> int:
        if frequency <= 0.0:
            return 0
        value = (self.sample_rate / (2.0 * frequency) + 1.0) / 2.0
        if value < 1.0:
            return 1
        rank = int(math.floor(value))
        if rank > self._max_rank:
            rank = self._max_rank
        return rank

    def _build_tables(self) -> List[List[float]]:
        tables: List[List[float]] = []
        for rank in range(self._max_rank + 1):
            table: List[float] = []
            if rank == 0:
                table = [0.0] * self._table_length
            else:
                for i in range(self._table_length):
                    phase = (i / self._table_length)
                    x = 2.0 * math.pi * phase
                    temp = 0.0
                    for k in range(1, rank + 1):
                        temp += math.sin((2 * k - 1) * x) / (2 * k - 1)
                    table.append((4.0 * temp) / math.pi)
            tables.append(table)
        return tables

    def _sound_for_frequency(self, frequency: float) -> Optional[object]:
        if not self.enable_audio or frequency <= 0.0:
            return None
        try:
            import pygame  # type: ignore
        except Exception:
            return None

        period_samples = max(int(self.sample_rate / frequency), 8)
        cache_key = (self._current_rank, period_samples)
        if cache_key in self._sounds:
            return self._sounds[cache_key]

        amplitude = int(self._amplitude * ((1 << 15) - 1))
        table = self._tables[self._current_rank]
        buffer = array("h")
        for index in range(period_samples):
            phase = (index / period_samples) * self._table_length
            table_index = int(phase) % self._table_length
            sample = int(table[table_index] * amplitude)
            buffer.append(sample)

        try:
            sound = pygame.mixer.Sound(buffer=buffer)
        except Exception:
            return None
        self._sounds[cache_key] = sound
        return sound

    def _start_playback(self) -> None:
        if self._status == 0:
            return
        if not self._ensure_mixer():
            return
        channel = self._channel
        if channel is None:
            return
        sound = self._sound_for_frequency(self._current_frequency)
        if sound is None:
            return
        try:
            channel.play(sound, loops=-1)
            channel.set_volume(self._channel_volume)
        except Exception:
            pass

    def _update_playback(self) -> None:
        if self._status == 0:
            return
        channel = self._channel
        if channel is None or not self._audio_initialized:
            return
        sound = self._sound_for_frequency(self._current_frequency)
        if sound is None:
            return
        try:
            channel.play(sound, loops=-1)
            channel.set_volume(self._channel_volume)
        except Exception:
            pass

    def _stop_playback(self) -> None:
        channel = self._channel
        if channel is None:
            return
        try:
            channel.stop()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Volume helpers (mirrors Java implementation)
    # ------------------------------------------------------------------
    def _calculate_amplitude(self, volume: int) -> float:
        if volume <= 0:
            return 0.0
        coeff = 19.36708871
        db = coeff * (math.log10(volume) - 2.0)
        return math.pow(10.0, (math.log10(2.0) / 3.0) * db) * 0.8

    def _calculate_channel_volume(self, volume: int) -> float:
        if volume <= 0:
            return 0.0
        if volume >= 50:
            return 1.0
        # scale roughly to pygame channel volume (0.0 - 1.0)
        return min(1.0, max(0.0, volume / 30.0))
