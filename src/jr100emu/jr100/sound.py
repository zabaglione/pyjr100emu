"""JR-100 sound processor with optional square-wave playback."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import threading
import time
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
        self._thread: Optional[threading.Thread] = None
        self._thread_stop = threading.Event()
        self._lock = threading.Lock()
        self._chunk_samples = 512

    # ------------------------------------------------------------------
    # VIA callbacks
    # ------------------------------------------------------------------

    def set_frequency(self, timestamp: float, frequency: float) -> None:
        self.history.append(("set_frequency", (timestamp, frequency)))
        self._current_frequency = frequency
        rank = self._rank_for_frequency(frequency)
        delta = 0.0
        if frequency > 0.0:
            delta = (self._table_length * frequency) / float(self.sample_rate)
        with self._lock:
            self._current_table = self._tables[rank]
            self._delta = delta

    def set_line_on(self) -> None:
        self.history.append(("set_line_on", tuple()))
        if not self.enable_audio:
            return
        if not self._ensure_mixer():
            return
        self._status = 1
        self._start_thread()

    def set_line_off(self) -> None:
        self.history.append(("set_line_off", tuple()))
        self._status = 0

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

    def _start_thread(self) -> None:
        if not self._audio_initialized or self._channel is None:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread_stop.clear()
        self._thread = threading.Thread(target=self._audio_loop, name="JR100Sound", daemon=True)
        self._thread.start()

    def _audio_loop(self) -> None:
        try:
            import pygame  # type: ignore
        except Exception:
            return

        amplitude = int(self.volume * 32767)
        while not self._thread_stop.is_set():
            if not self._audio_initialized or self._channel is None:
                time.sleep(0.01)
                continue

            busy = self._channel.get_busy()
            queued = None
            if hasattr(self._channel, "get_queue"):
                queued = self._channel.get_queue()

            if not busy or queued is None:
                chunk = self._render_chunk(amplitude)
                if chunk is None:
                    time.sleep(0.005)
                    continue
                sound = pygame.mixer.Sound(buffer=chunk)
                try:
                    if not busy:
                        self._channel.play(sound)
                    else:
                        self._channel.queue(sound)
                except Exception:
                    try:
                        self._channel.play(sound)
                    except Exception:
                        time.sleep(0.01)
                        continue
            else:
                # Enough data buffered; yield briefly.
                time.sleep(0.002)

    def _render_chunk(self, amplitude: int) -> Optional[array]:
        with self._lock:
            table = self._current_table
            delta = self._delta
            phase = self._phase
            status = self._status

        buffer = array("h")
        buffer.extend([0] * self._chunk_samples)
        table_len = self._table_length
        if table_len <= 0:
            return buffer

        # When status is zero the ring buffer still advances phase to avoid pops.
        gain = amplitude if status else 0

        for index in range(self._chunk_samples):
            table_index = int(phase)
            if table_index >= table_len:
                table_index %= table_len
            sample_value = int(table[table_index] * gain) if gain else 0
            buffer[index] = sample_value
            phase += delta
            if phase >= table_len:
                phase -= table_len

        with self._lock:
            self._phase = phase

        return buffer
