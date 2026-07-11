"""ROM BASIC beeper integration tests."""

from __future__ import annotations

from array import array

from jr100emu.jr100.computer import JR100Computer


def _advance(computer: JR100Computer, cycles: int) -> None:
    target = computer.clock_count + cycles
    while computer.clock_count < target:
        computer.tick(128)


def _press_key(
    computer: JR100Computer,
    row: int,
    bit: int,
    *,
    hold_cycles: int = 50_000,
    gap_cycles: int = 100_000,
) -> None:
    keyboard = computer.hardware.keyboard
    keyboard.press(row, bit)
    _advance(computer, hold_cycles)
    keyboard.release(row, bit)
    _advance(computer, gap_cycles)


def _active_segments(samples: array, window: int = 32) -> list[array]:
    windows = [
        any(samples[index : index + window]) for index in range(0, len(samples), window)
    ]
    segments: list[array] = []
    start: int | None = None
    for index, active in enumerate(windows + [False]):
        if active and start is None:
            start = index * window
        elif not active and start is not None:
            segments.append(samples[start : min(index * window, len(samples))])
            start = None
    return segments


def _estimated_frequency(samples: array, sample_rate: int) -> float:
    signs = [sample > 0 for sample in samples if sample != 0]
    crossings = sum(left != right for left, right in zip(signs, signs[1:]))
    duration = len(samples) / sample_rate
    return crossings / (2.0 * duration)


def test_rom_basic_key_and_syntax_error_beeps_are_stable(monkeypatch) -> None:
    computer = JR100Computer(rom_path="datas/jr100rom.prg", enable_audio=False)
    for _ in range(4_000):
        computer.tick(512)

    sound = computer.hardware.sound_processor
    assert sound.computer is computer
    sound.enable_audio = True
    sound._max_pending_chunks = 100
    monkeypatch.setattr(sound, "pump", lambda: None)

    _press_key(computer, 1, 0)
    _press_key(computer, 8, 3)
    _advance(computer, 200_000)

    samples = array("h")
    for chunk in sound._ready_chunks:
        samples.extend(chunk)
    samples.extend(sound._sample_buffer)
    segments = _active_segments(samples)

    assert len(segments) == 3
    for segment in segments:
        duration_ms = len(segment) * 1_000.0 / sound.sample_rate
        assert 85.0 <= duration_ms <= 89.0
        assert 2_550.0 <= _estimated_frequency(segment, sound.sample_rate) <= 2_650.0

    syntax = [computer.memory.load8(0xC100 + 5 * 32 + index) for index in range(6)]
    assert syntax == [ord(character) - 0x20 for character in "SYNTAX"]
