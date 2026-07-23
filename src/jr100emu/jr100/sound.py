"""JR-100 sound processor with timestamped buffered playback."""

from __future__ import annotations

from array import array
from collections import deque
from dataclasses import dataclass, field
import heapq
import math
import threading
from typing import Deque, List, Optional, Tuple


@dataclass
class JR100SoundProcessor:
    """Render timestamped beeper changes into a phase-continuous PCM stream."""

    history: List[Tuple[str, Tuple[float, ...]]] = field(default_factory=list)
    computer: object | None = field(default=None, init=False, repr=False)
    sample_rate: int = 44100
    volume: int = 30
    enable_audio: bool = False
    chunk_samples: int = 2048
    mixer_buffer_samples: int = 512
    history_limit: int = 4096

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
        self._scheduled_frequency: float = 0.0
        self._scheduled_status: int = 0
        self._amplitude = self._calculate_amplitude(self.volume)
        self._events: list[tuple[float, int, str, float]] = []
        self._event_order = 0
        self._render_time_ns: Optional[float] = None
        self._sample_period_ns = 1_000_000_000.0 / self.sample_rate
        self._sample_buffer = array("h")
        self._ready_chunks: Deque[array] = deque()
        self._queue_lock = threading.Lock()
        self._chunk_byte_offset = 0
        self._live_sounds: List[object] = []
        self._prebuffer_chunks = 4
        self._max_pending_chunks = 8
        self._audio_device = None
        self._audio_backend: Optional[str] = None
        self._underrun_count = 0

    # ------------------------------------------------------------------
    # VIA callbacks
    # ------------------------------------------------------------------

    def set_frequency(self, timestamp: float, frequency: float) -> None:
        self._record_history("set_frequency", (timestamp, frequency))
        self._scheduled_frequency = frequency
        if self._uses_timeline(timestamp):
            self._schedule_event(timestamp, "frequency", frequency)
            return
        self._apply_frequency(frequency)

    def set_line_on(self, timestamp: float | None = None) -> None:
        if self._uses_timeline(timestamp):
            if self._scheduled_status == 1:
                return
            self._record_history("set_line_on", tuple())
            self._scheduled_status = 1
            self._schedule_event(timestamp, "status", 1.0)
            return

        self._record_history("set_line_on", tuple())
        was_on = self._status != 0
        self._scheduled_status = 1
        self._status = 1
        if not was_on and self.enable_audio:
            while self._ready_chunk_count() < self._prebuffer_chunks:
                self._append_ready_chunk(self._render_chunk())
            self.pump()

    def set_line_off(self, timestamp: float | None = None) -> None:
        if self._uses_timeline(timestamp):
            if self._scheduled_status == 0:
                return
            self._record_history("set_line_off", tuple())
            self._scheduled_status = 0
            self._schedule_event(timestamp, "status", 0.0)
            return

        self._record_history("set_line_off", tuple())
        self._scheduled_status = 0
        self._status = 0

    def _uses_timeline(self, timestamp: float | None) -> bool:
        return timestamp is not None and getattr(self, "computer", None) is not None

    def _schedule_event(self, timestamp: float, kind: str, value: float) -> None:
        heapq.heappush(
            self._events,
            (float(timestamp), self._event_order, kind, value),
        )
        self._event_order += 1
        if self._render_time_ns is None:
            self._render_time_ns = float(timestamp)

    def _record_history(self, name: str, values: Tuple[float, ...]) -> None:
        self.history.append((name, values))
        overflow = len(self.history) - self.history_limit
        if overflow > 0:
            del self.history[:overflow]

    # ------------------------------------------------------------------
    # Device and timeline control
    # ------------------------------------------------------------------

    def execute(self) -> None:
        target_time_ns = self._emulated_time_ns()
        if target_time_ns is None:
            return
        if self.enable_audio:
            self._render_until(target_time_ns)
            self.pump()
        else:
            self._advance_without_audio(target_time_ns)

    def reset(self) -> None:
        self._current_frequency = 0.0
        self._current_table = self._tables[0]
        self._delta = 0.0
        self._phase = 0.0
        self._status = 0
        self._scheduled_frequency = 0.0
        self._scheduled_status = 0
        self._events.clear()
        self._event_order = 0
        self._render_time_ns = None
        self._sample_buffer = array("h")
        with self._queue_lock:
            self._ready_chunks.clear()
            self._chunk_byte_offset = 0
        self._live_sounds.clear()
        if self._channel is not None:
            try:
                self._channel.stop()
            except Exception:
                pass

    def _emulated_time_ns(self) -> Optional[float]:
        computer = getattr(self, "computer", None)
        if computer is None:
            return None
        frequency = float(getattr(computer, "cpu_clock_frequency", 0.0))
        if frequency <= 0.0:
            return None
        clock_count = int(getattr(computer, "clock_count", 0))
        base_time = int(getattr(computer, "base_time", 0))
        return base_time + (clock_count * 1_000_000_000.0) / frequency

    def _render_until(self, target_time_ns: float) -> None:
        if self._render_time_ns is None or target_time_ns <= self._render_time_ns:
            return

        while self._render_time_ns < target_time_ns:
            self._apply_events_through(self._render_time_ns)
            self._append_sample(self._next_sample())
            self._render_time_ns += self._sample_period_ns

    def _advance_without_audio(self, target_time_ns: float) -> None:
        self._apply_events_through(target_time_ns)
        if self._render_time_ns is not None:
            self._render_time_ns = max(self._render_time_ns, target_time_ns)

    def _apply_events_through(self, timestamp: float) -> None:
        while self._events and self._events[0][0] <= timestamp:
            _, _, kind, value = heapq.heappop(self._events)
            if kind == "frequency":
                self._apply_frequency(value)
            else:
                self._status = int(value)

    def _apply_frequency(self, frequency: float) -> None:
        self._current_frequency = frequency
        if frequency <= 0.0 or frequency >= self.sample_rate / 2.0:
            self._current_table = self._tables[0]
            self._delta = 0.0
            return

        rank = self._rank_for_frequency(frequency)
        self._current_table = self._tables[rank]
        self._delta = (self._table_length * frequency) / float(self.sample_rate)

    def _append_sample(self, sample: int) -> None:
        self._sample_buffer.append(sample)
        if len(self._sample_buffer) < self.chunk_samples:
            return
        self._append_ready_chunk(self._sample_buffer)
        self._sample_buffer = array("h")

    def _append_ready_chunk(self, chunk: array) -> None:
        with self._queue_lock:
            self._ready_chunks.append(chunk)
            while len(self._ready_chunks) > self._max_pending_chunks:
                self._ready_chunks.popleft()
                self._chunk_byte_offset = 0

    def _ready_chunk_count(self) -> int:
        with self._queue_lock:
            return len(self._ready_chunks)

    # ------------------------------------------------------------------
    # Mixer queue control
    # ------------------------------------------------------------------

    def _ensure_sdl_audio(self) -> bool:
        if not self.enable_audio:
            return False
        try:
            import pygame  # type: ignore

            if not hasattr(pygame, "__path__"):
                return False
            import pygame._sdl2 as sdl2  # type: ignore

            if pygame.mixer.get_init():
                pygame.mixer.quit()
            sdl2.init_subsystem(sdl2.INIT_AUDIO)
            device_names = sdl2.get_audio_device_names(False)
            if not device_names:
                return False
            self._audio_device = sdl2.AudioDevice(
                devicename=device_names[0],
                iscapture=False,
                frequency=self.sample_rate,
                audioformat=sdl2.AUDIO_S16,
                numchannels=1,
                chunksize=self.mixer_buffer_samples,
                allowed_changes=0,
                callback=self._audio_callback,
            )
            self._audio_backend = "sdl2"
            self._audio_initialized = True
            self._audio_device.pause(False)
            return True
        except Exception:
            self._audio_device = None
            self._audio_backend = None
            self._audio_initialized = False
            return False

    def _audio_callback(self, device: object, stream: object) -> None:
        output = bytearray(len(stream))
        output_offset = 0
        with self._queue_lock:
            while output_offset < len(output) and self._ready_chunks:
                chunk = self._ready_chunks[0]
                chunk_bytes = memoryview(chunk).cast("B")
                available = len(chunk_bytes) - self._chunk_byte_offset
                copy_length = min(len(output) - output_offset, available)
                output[output_offset : output_offset + copy_length] = chunk_bytes[
                    self._chunk_byte_offset : self._chunk_byte_offset + copy_length
                ]
                output_offset += copy_length
                self._chunk_byte_offset += copy_length
                if self._chunk_byte_offset >= len(chunk_bytes):
                    self._ready_chunks.popleft()
                    self._chunk_byte_offset = 0
        if output_offset < len(output):
            self._underrun_count += 1
        stream[:] = output

    @property
    def underrun_count(self) -> int:
        return self._underrun_count

    def _ensure_mixer(self) -> bool:
        if not self.enable_audio:
            return False
        if self._audio_initialized:
            return True
        try:
            import pygame  # type: ignore

            expected_format = (self.sample_rate, -16, 1)
            mixer_format = pygame.mixer.get_init()
            if mixer_format and tuple(mixer_format) != expected_format:
                pygame.mixer.quit()
                mixer_format = None
            if not mixer_format:
                pygame.mixer.init(
                    frequency=self.sample_rate,
                    size=-16,
                    channels=1,
                    buffer=self.mixer_buffer_samples,
                )
            self._channel = pygame.mixer.Channel(0)
            self._audio_backend = "mixer"
            self._audio_initialized = True
        except Exception:
            self.enable_audio = False
            self._channel = None
            self._audio_initialized = False
        return self._audio_initialized

    def pump(self) -> None:
        ready_count = self._ready_chunk_count()
        if not self.enable_audio or ready_count == 0:
            return
        if not self._audio_initialized and ready_count < self._prebuffer_chunks:
            return
        if not self._audio_initialized:
            if self._ensure_sdl_audio():
                return
            if not self._ensure_mixer():
                return
        if self._audio_backend == "sdl2":
            return
        if self._channel is None:
            return
        try:
            import pygame  # type: ignore

            busy = bool(self._channel.get_busy())
            if not busy:
                chunk = self._pop_mixer_chunk()
                if chunk is None:
                    return
                self._channel.play(self._make_sound(pygame, chunk))
                busy = True

            queued = self._channel.get_queue()
            if busy and queued in (None, False):
                chunk = self._pop_mixer_chunk()
                if chunk is not None:
                    self._channel.queue(self._make_sound(pygame, chunk))
            self._channel.set_volume(1.0)
        except Exception:
            return

    def _pop_mixer_chunk(self) -> Optional[array]:
        with self._queue_lock:
            if not self._ready_chunks:
                return None
            self._chunk_byte_offset = 0
            return self._ready_chunks.popleft()

    def close(self) -> None:
        if self._audio_device is not None:
            try:
                self._audio_device.close()
            except Exception:
                pass
            self._audio_device = None
        if self._channel is not None:
            try:
                self._channel.stop()
            except Exception:
                pass
            self._channel = None
        self._audio_initialized = False
        self._audio_backend = None

    def _make_sound(self, pygame: object, samples: array) -> object:
        sound = pygame.mixer.Sound(buffer=samples)
        self._retain_sound(sound)
        return sound

    def _retain_sound(self, sound: object) -> None:
        self._live_sounds.append(sound)
        if len(self._live_sounds) > 8:
            self._live_sounds = self._live_sounds[-8:]

    # ------------------------------------------------------------------
    # Waveform and volume helpers
    # ------------------------------------------------------------------

    def _next_sample(self) -> int:
        table_index = int(self._phase) % self._table_length
        gain = int(self._amplitude * ((1 << 15) - 1)) if self._status else 0
        sample = int(self._current_table[table_index] * gain) if gain else 0
        self._phase += self._delta
        if self._phase >= self._table_length:
            self._phase %= self._table_length
        return max(-32768, min(32767, sample))

    def _render_chunk(self) -> array:
        return array("h", (self._next_sample() for _ in range(self.chunk_samples)))

    def _rank_for_frequency(self, frequency: float) -> int:
        if frequency <= 0.0:
            return 0
        value = (self.sample_rate / (2.0 * frequency) + 1.0) / 2.0
        if value < 1.0:
            return 1
        return min(self._max_rank, int(math.floor(value)))

    def _build_tables(self) -> List[List[float]]:
        tables: List[List[float]] = []
        for rank in range(self._max_rank + 1):
            if rank == 0:
                tables.append([0.0] * self._table_length)
                continue
            table: List[float] = []
            for index in range(self._table_length):
                x = 2.0 * math.pi * index / self._table_length
                value = 0.0
                for harmonic in range(1, rank + 1):
                    odd = 2 * harmonic - 1
                    value += math.sin(odd * x) / odd
                table.append((4.0 * value) / math.pi)
            tables.append(table)
        return tables

    def _calculate_amplitude(self, volume: int) -> float:
        if volume <= 0:
            return 0.0
        coeff = 19.36708871
        db = coeff * (math.log10(volume) - 2.0)
        return math.pow(10.0, (math.log10(2.0) / 3.0) * db) * 0.8
