"""JR-100 sound processor with optional square-wave playback."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from array import array
from typing import List, Optional, Tuple


@dataclass
class JR100SoundProcessor:
    """Square wave beeper that mirrors the JR-100 cassette tone output."""

    history: List[Tuple[str, Tuple[float, ...]]] = field(default_factory=list)
    sample_rate: int = 44100
    volume: float = 0.3
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
        self._chunk_samples = 256
        self._needs_refresh = False
        self._live_sounds: List[object] = []
        self._max_queue = 2

    # ------------------------------------------------------------------
    # VIA callbacks
    # ------------------------------------------------------------------

    def set_frequency(self, timestamp: float, frequency: float) -> None:
        self.history.append(("set_frequency", (timestamp, frequency)))
        self._current_frequency = frequency
        rank = self._rank_for_frequency(frequency)
        if frequency > 0.0:
            self._delta = (self._table_length * frequency) / float(self.sample_rate)
        else:
            self._delta = 0.0
        self._current_table = self._tables[rank]
        self._needs_refresh = True

    def set_line_on(self) -> None:
        self.history.append(("set_line_on", tuple()))
        self._status = 1
        self._needs_refresh = True

    def set_line_off(self) -> None:
        self.history.append(("set_line_off", tuple()))
        self._status = 0
        self._needs_refresh = True

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

    def pump(self) -> None:
        if not self.enable_audio:
            return
        if not self._ensure_mixer():
            return
        if self._channel is None:
            return
        try:
            import pygame  # type: ignore
        except Exception:
            return

        channel = self._channel
        busy = channel.get_busy()
        queued = None
        if hasattr(channel, "get_queue"):
            try:
                queued = channel.get_queue()
            except Exception:
                queued = None

        queue_depth = 1 if busy else 0
        if queued not in (None, False):
            queue_depth += 1

        if queue_depth >= self._max_queue and not self._needs_refresh:
            self._trim_live_sounds()
            return

        chunk = self._render_chunk()
        if chunk is None:
            return
        sound = pygame.mixer.Sound(buffer=chunk)
        self._retain_sound(sound)
        self._needs_refresh = False

        target_volume = self.volume if self._status else 0.0

        try:
            if not busy:
                channel.play(sound)
                channel.set_volume(target_volume)
            else:
                channel.queue(sound)
                channel.set_volume(target_volume)
        except Exception:
            try:
                channel.play(sound)
                channel.set_volume(target_volume)
            except Exception:
                return

    def _render_chunk(self) -> Optional[array]:
        table = self._current_table
        delta = self._delta
        phase = self._phase
        status = self._status

        table_len = self._table_length
        if table_len <= 0:
            return None

        amplitude = int(self.volume * 32767)
        gain = amplitude if status else 0

        buffer = array("h", [0] * self._chunk_samples)
        for index in range(self._chunk_samples):
            table_index = int(phase)
            if table_index >= table_len:
                table_index %= table_len
            sample = int(table[table_index] * gain) if gain else 0
            buffer[index] = sample
            phase += delta
            if phase >= table_len:
                phase -= table_len

        self._phase = phase
        return buffer

    def _retain_sound(self, sound: object) -> None:
        self._live_sounds.append(sound)
        if len(self._live_sounds) > 8:
            self._live_sounds = self._live_sounds[-8:]

    def _trim_live_sounds(self) -> None:
        if len(self._live_sounds) > 8:
            self._live_sounds = self._live_sounds[-8:]
