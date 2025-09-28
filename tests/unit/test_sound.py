"""Sound processor tests."""

from __future__ import annotations

import sys

import pytest

from jr100emu.jr100.sound import JR100SoundProcessor


class DummySound:
    def __init__(self, buffer):
        self.buffer = buffer


class DummyChannel:
    def __init__(self, mixer):
        self.mixer = mixer

    def play(self, sound, loops=-1):
        self.mixer.last_sound = sound
        self.mixer.last_loops = loops

    def set_volume(self, volume):
        self.mixer.last_volume = volume

    def stop(self):
        self.mixer.stopped = True


class DummyMixer:
    def __init__(self):
        self.initialized = False
        self.last_sound = None
        self.last_volume = None
        self.last_loops = None
        self.stopped = False

    def init(self, **kwargs):
        self.initialized = True

    def get_init(self):
        return self.initialized

    def Channel(self, index):
        return DummyChannel(self)

    def Sound(self, *args, **kwargs):
        buffer = kwargs.get("buffer") or (args[0] if args else None)
        return DummySound(buffer)


class DummyPygame:
    def __init__(self):
        self.mixer = DummyMixer()


def test_sound_processor_history_only():
    sp = JR100SoundProcessor()
    sp.set_frequency(0.0, 440.0)
    sp.set_line_on()
    sp.set_line_off()
    assert [entry[0] for entry in sp.history] == ["set_frequency", "set_line_on", "set_line_off"]


def test_sound_processor_audio(monkeypatch):
    dummy = DummyPygame()
    monkeypatch.setitem(sys.modules, "pygame", dummy)

    sp = JR100SoundProcessor(enable_audio=True)
    sp.set_frequency(0.0, 440.0)
    sp.set_line_on()
    assert dummy.mixer.last_sound is not None
    assert dummy.mixer.last_volume == pytest.approx(sp.volume)
    sp.set_line_off()
    assert dummy.mixer.stopped is True
