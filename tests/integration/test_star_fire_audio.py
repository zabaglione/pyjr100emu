"""Audio regression checks for the STARFIRE program."""

from __future__ import annotations

from array import array

from jr100emu.jr100.computer import JR100Computer


def _captured_samples(computer: JR100Computer) -> array:
    sound = computer.hardware.sound_processor
    samples = array("h")
    for chunk in sound._ready_chunks:
        samples.extend(chunk)
    samples.extend(sound._sample_buffer)
    return samples


def test_starfire_timer1_high_frequency_does_not_alias_into_audio() -> None:
    computer = JR100Computer(rom_path="datas/jr100rom.prg", enable_audio=True)
    computer.load_user_program("datas/STARFIRE.prg")
    sound = computer.hardware.sound_processor
    sound.pump = lambda: None
    computer.cpu_core.registers.program_counter = 0x0D00

    while computer.clock_count < 20_000:
        computer.tick(512)

    assert sound._current_frequency > sound.sample_rate / 2.0
    assert all(sample == 0 for sample in _captured_samples(computer))
