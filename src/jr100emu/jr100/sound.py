"""JR-100 sound processor with optional square-wave playback."""

from __future__ import annotations

from array import array
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


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
        self._sound_cache: Dict[int, object] = {}

    # ------------------------------------------------------------------
    # VIA callbacks
    # ------------------------------------------------------------------

    def set_frequency(self, timestamp: float, frequency: float) -> None:
        self.history.append(("set_frequency", (timestamp, frequency)))
        self._current_frequency = frequency
        self._update_playback()

    def set_line_on(self) -> None:
        self.history.append(("set_line_on", tuple()))
        self._start_playback()

    def set_line_off(self) -> None:
        self.history.append(("set_line_off", tuple()))
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

    def _sound_for_frequency(self, frequency: float) -> Optional[object]:
        if not self.enable_audio or frequency <= 0.0:
            return None
        try:
            import pygame  # type: ignore
        except Exception:
            return None

        period_samples = max(int(self.sample_rate / frequency), 2)
        cache_key = period_samples
        if cache_key in self._sound_cache:
            return self._sound_cache[cache_key]

        half_period = period_samples // 2
        amplitude = int(0.8 * 32767)
        buffer = array("h")
        for index in range(period_samples):
            value = amplitude if index < half_period else -amplitude
            buffer.append(value)

        sound = pygame.mixer.Sound(buffer=buffer)
        self._sound_cache[cache_key] = sound
        return sound

    def _start_playback(self) -> None:
        if not self._ensure_mixer():
            return
        sound = self._sound_for_frequency(self._current_frequency)
        if sound is None:
            return
        self._channel.play(sound, loops=-1)
        self._channel.set_volume(self.volume)

    def _update_playback(self) -> None:
        if self._channel is None:
            return
        sound = self._sound_for_frequency(self._current_frequency)
        if sound is not None:
            self._channel.play(sound, loops=-1)
            self._channel.set_volume(self.volume)

    def _stop_playback(self) -> None:
        if self._channel is not None:
            self._channel.stop()
