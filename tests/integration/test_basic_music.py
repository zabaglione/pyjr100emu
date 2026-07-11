"""ROM BASIC music playback integration tests."""

from __future__ import annotations

from array import array
from pathlib import Path

import pytest

from jr100emu.jr100.computer import JR100Computer


NOTE_FREQUENCIES = {
    1: 523.0,
    2: 589.0,
    3: 666.0,
    4: 700.0,
    5: 786.0,
    6: 884.0,
    7: 990.0,
    8: 1054.0,
}
TWINKLE_NOTES = [
    1,
    1,
    5,
    5,
    6,
    6,
    5,
    4,
    4,
    3,
    3,
    2,
    2,
    1,
    5,
    5,
    4,
    4,
    3,
    3,
    2,
    5,
    5,
    4,
    4,
    3,
    3,
    2,
    1,
    1,
    5,
    5,
    6,
    6,
    5,
    4,
    4,
    3,
    3,
    2,
    2,
    1,
]


def _advance(computer: JR100Computer, cycles: int) -> None:
    target = computer.clock_count + cycles
    while computer.clock_count < target:
        computer.tick(512)


def _press_key(computer: JR100Computer, row: int, bit: int) -> None:
    keyboard = computer.hardware.keyboard
    keyboard.press(row, bit)
    _advance(computer, 50_000)
    keyboard.release(row, bit)
    _advance(computer, 100_000)


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
    return crossings * sample_rate / (2.0 * len(samples))


def _longest_zero_run(samples: array) -> int:
    longest = 0
    current = 0
    for sample in samples:
        if sample == 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def _run_music(
    monkeypatch: pytest.MonkeyPatch, path: Path, note_count: int
) -> tuple[JR100Computer, list[array]]:
    computer = JR100Computer(rom_path="datas/jr100rom.prg", enable_audio=False)
    _advance(computer, 2_048_000)
    computer.load_user_program(path)

    sound = computer.hardware.sound_processor
    sound.enable_audio = True
    sound._max_pending_chunks = 512
    monkeypatch.setattr(sound, "pump", lambda: None)

    # Type RUN, retaining the Return beep as the first captured segment.
    _press_key(computer, 2, 3)
    _press_key(computer, 5, 1)
    _press_key(computer, 7, 2)
    sound.history.clear()
    with sound._queue_lock:
        sound._ready_chunks.clear()
        sound._chunk_byte_offset = 0
    sound._sample_buffer = array("h")
    _press_key(computer, 8, 3)

    expected_line_offs = note_count + 1
    for _ in range(80_000):
        if (
            sum(name == "set_line_off" for name, _ in sound.history)
            >= expected_line_offs
        ):
            break
        computer.tick(512)
    else:
        raise AssertionError(f"music did not finish: {path}")
    _advance(computer, 100_000)

    samples = array("h")
    for chunk in sound._ready_chunks:
        samples.extend(chunk)
    samples.extend(sound._sample_buffer)
    return computer, _active_segments(samples)


@pytest.mark.parametrize(
    ("path", "notes"),
    [
        (Path("datas/doremi_scale.bas"), list(range(1, 9))),
        (Path("datas/twinkle_star.bas"), TWINKLE_NOTES),
    ],
)
def test_basic_music_has_stable_uninterrupted_notes(
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
    notes: list[int],
) -> None:
    computer, segments = _run_music(monkeypatch, path, len(notes))
    sound = computer.hardware.sound_processor

    # Segment zero is the Return key beep; subsequent segments are the music.
    assert len(segments) == len(notes) + 1
    music_segments = segments[1:]
    measured = [
        _estimated_frequency(segment, sound.sample_rate) for segment in music_segments
    ]
    expected = [NOTE_FREQUENCIES[note] for note in notes]

    assert measured == pytest.approx(expected, abs=15.0)
    assert max(_longest_zero_run(segment[32:-32]) for segment in music_segments) <= 64

    # Timer updates must occur while output is off, never during a sounding note.
    sounding = False
    for name, _ in sound.history:
        if name == "set_line_on":
            sounding = True
        elif name == "set_line_off":
            sounding = False
        elif name == "set_frequency":
            assert not sounding
