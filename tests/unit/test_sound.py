"""Sound processor tests."""

from __future__ import annotations

from array import array
import sys

import pytest

from jr100emu.jr100.sound import JR100SoundProcessor


class DummySound:
    def __init__(self, buffer):
        self.buffer = buffer


class DummyChannel:
    def __init__(self, mixer):
        self.mixer = mixer
        self.busy = False
        self.queued = None

    def play(self, sound, loops=-1):
        self.mixer.last_sound = sound
        self.mixer.last_loops = loops
        self.mixer.play_count += 1
        self.busy = True

    def queue(self, sound):
        self.queued = sound
        self.mixer.queue_count += 1

    def get_busy(self):
        return self.busy

    def get_queue(self):
        return self.queued

    def set_volume(self, volume):
        self.mixer.last_volume = volume

    def stop(self):
        self.mixer.stopped = True
        self.busy = False
        self.queued = None


class DummyMixer:
    def __init__(self):
        self.initialized = False
        self.last_sound = None
        self.last_volume = None
        self.last_loops = None
        self.stopped = False
        self.play_count = 0
        self.queue_count = 0
        self.quit_count = 0
        self.init_kwargs = None
        self.channel = DummyChannel(self)

    def init(self, **kwargs):
        self.initialized = (kwargs["frequency"], kwargs["size"], kwargs["channels"])
        self.init_kwargs = kwargs

    def get_init(self):
        return self.initialized

    def quit(self):
        self.initialized = False
        self.quit_count += 1

    def Channel(self, index):
        return self.channel

    def Sound(self, *args, **kwargs):
        buffer = kwargs.get("buffer") or (args[0] if args else None)
        return DummySound(buffer)


class DummyPygame:
    def __init__(self):
        self.mixer = DummyMixer()


class DummyComputer:
    clock_count = 0
    base_time = 0
    cpu_clock_frequency = 1_000_000.0


def _pending_samples(sound: JR100SoundProcessor) -> array:
    samples = array("h")
    for chunk in sound._ready_chunks:
        samples.extend(chunk)
    samples.extend(sound._sample_buffer)
    return samples


def test_sound_processor_history_only():
    sp = JR100SoundProcessor()
    sp.set_frequency(0.0, 440.0)
    sp.set_line_on()
    sp.set_line_off()
    assert [entry[0] for entry in sp.history] == [
        "set_frequency",
        "set_line_on",
        "set_line_off",
    ]


def test_sound_processor_audio(monkeypatch):
    dummy = DummyPygame()
    monkeypatch.setitem(sys.modules, "pygame", dummy)

    sp = JR100SoundProcessor(enable_audio=True)
    sp.set_frequency(0.0, 440.0)
    sp.set_line_on()
    assert dummy.mixer.last_sound is not None
    assert dummy.mixer.last_volume == pytest.approx(1.0)
    assert dummy.mixer.init_kwargs["channels"] == 1
    assert dummy.mixer.init_kwargs["buffer"] == sp.mixer_buffer_samples
    sp.set_line_off()
    assert dummy.mixer.stopped is False


def test_frequency_change_does_not_restart_active_channel(monkeypatch):
    dummy = DummyPygame()
    monkeypatch.setitem(sys.modules, "pygame", dummy)

    sp = JR100SoundProcessor(enable_audio=True)
    sp.set_frequency(0.0, 440.0)
    sp.set_line_on()
    assert dummy.mixer.play_count == 1

    sp.set_frequency(1.0, 880.0)

    assert dummy.mixer.play_count == 1


def test_mixer_is_reinitialized_when_existing_format_is_stereo(monkeypatch):
    dummy = DummyPygame()
    dummy.mixer.initialized = (44100, -16, 2)
    monkeypatch.setitem(sys.modules, "pygame", dummy)

    sp = JR100SoundProcessor(enable_audio=True)
    sp.set_frequency(0.0, 440.0)
    sp.set_line_on()

    assert dummy.mixer.quit_count == 1
    assert dummy.mixer.get_init() == (44100, -16, 1)


def test_pump_queues_pcm_without_restarting_channel(monkeypatch):
    dummy = DummyPygame()
    monkeypatch.setitem(sys.modules, "pygame", dummy)

    sp = JR100SoundProcessor(enable_audio=True)
    sp.set_frequency(0.0, 440.0)
    sp.set_line_on()
    sp._ready_chunks.append(sp._render_chunk())
    sp.pump()

    assert dummy.mixer.play_count == 1
    assert dummy.mixer.queue_count == 1
    assert dummy.mixer.channel.queued is not None


def test_line_off_renders_silence_without_stopping_channel(monkeypatch):
    dummy = DummyPygame()
    monkeypatch.setitem(sys.modules, "pygame", dummy)

    sp = JR100SoundProcessor(enable_audio=True)
    sp.set_frequency(0.0, 440.0)
    sp.set_line_on()
    sp.set_line_off()

    silence = sp._render_chunk()

    assert dummy.mixer.stopped is False
    assert set(silence) == {0}


def test_history_is_bounded() -> None:
    sp = JR100SoundProcessor(history_limit=3)

    for _ in range(5):
        sp.set_line_on()

    assert len(sp.history) == 3


def test_timed_line_event_is_not_expanded_to_full_chunk() -> None:
    sp = JR100SoundProcessor(enable_audio=False)
    sp.computer = DummyComputer()
    sp.set_frequency(0.0, 440.0)
    sp.set_line_on(0.0)
    sp.set_line_off(1_000_000.0)

    sp._render_until(10_000_000.0)
    samples = _pending_samples(sp)

    assert any(samples[:45])
    assert not any(samples[45:])


def test_brief_rom_setup_transient_keeps_final_pitch_stable() -> None:
    sp = JR100SoundProcessor(enable_audio=False)
    sp.computer = DummyComputer()
    sp.set_frequency(0.0, 223_721.562)
    sp.set_line_on(0.0)
    sp.set_frequency(18_000.0, 2_601.414)
    sp.set_line_off(20_000_000.0)

    sp._render_until(20_000_000.0)
    samples = _pending_samples(sp)
    signs = [sample > 0 for sample in samples if sample != 0]
    zero_crossings = sum(left != right for left, right in zip(signs, signs[1:]))

    assert 95 <= zero_crossings <= 110


def test_audio_callback_consumes_pcm_and_zero_fills_underrun() -> None:
    sp = JR100SoundProcessor()
    sp._ready_chunks.append(array("h", [100, -100]))
    stream = bytearray(8)

    sp._audio_callback(None, stream)

    samples = array("h")
    samples.frombytes(stream)
    assert samples.tolist() == [100, -100, 0, 0]
    assert sp.underrun_count == 1
