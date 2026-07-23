from __future__ import annotations

import struct
from pathlib import Path

import pytest

from jr100emu import debug_runner
from jr100emu.cpu.cpu import MB8861


class FakeTime:
    def __init__(self) -> None:
        self.current = 0.0

    def monotonic(self) -> float:
        value = self.current
        self.current += 0.6
        return value


def _write_prog(path: Path, *, start: int, payload: bytes, name: str = "TEST") -> None:
    with path.open("wb") as stream:
        stream.write(b"PROG")
        stream.write(struct.pack("<I", 1))  # version
        name_bytes = name.encode("utf-8")
        stream.write(struct.pack("<I", len(name_bytes)))
        stream.write(name_bytes)
        stream.write(struct.pack("<I", start))
        stream.write(struct.pack("<I", len(payload)))
        stream.write(struct.pack("<I", 1))  # binary payload flag
        stream.write(payload)


def _write_rom(path: Path, code: bytes, *, start: int = 0xE000) -> None:
    payload = bytearray(0x2000)
    payload[: len(code)] = code
    payload[0x1FFE] = (start >> 8) & 0xFF
    payload[0x1FFF] = start & 0xFF
    _write_prog(path, start=0xE000, payload=bytes(payload), name="ROM")


def test_debug_runner_breaks_and_dumps(tmp_path, capsys) -> None:
    prog_path = tmp_path / "loop.prog"
    _write_prog(prog_path, start=0x0300, payload=bytes([0x20, 0xFE]))

    exit_code = debug_runner.main(
        [
            "--program",
            str(prog_path),
            "--start",
            "0x0300",
            "--cycles",
            "512",
            "--break-pc",
            "0x0300",
            "--dump-range",
            "0300:030F",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    output_lines = [line for line in captured.out.strip().splitlines() if line]
    assert output_lines[0].startswith("ADDR")
    assert "0300 20 FE" in output_lines[1]


def test_debug_runner_time_limit(tmp_path, capsys, monkeypatch) -> None:
    prog_path = tmp_path / "loop.prog"
    _write_prog(prog_path, start=0x0300, payload=bytes([0x20, 0xFE]))

    fake_time = FakeTime()
    monkeypatch.setattr(debug_runner, "time", fake_time)

    exit_code = debug_runner.main(
        [
            "--program",
            str(prog_path),
            "--start",
            "0x0300",
            "--cycles",
            "0",
            "--seconds",
            "1",
            "--dump-range",
            "0300:0300",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 3
    assert "time limit" in captured.err


def test_debug_runner_boot_uses_reset_vector_and_normalised_registers(
    tmp_path, capsys
) -> None:
    rom_path = tmp_path / "boot.prg"
    dump_path = tmp_path / "registers.bin"
    code = bytes(
        [
            MB8861.OP_STAA_EXT,
            0x00,
            0x00,
            MB8861.OP_STAB_EXT,
            0x00,
            0x01,
            MB8861.OP_STX_EXT,
            0x00,
            0x02,
            MB8861.OP_STS_EXT,
            0x00,
            0x04,
            MB8861.OP_BRA_REL,
            0xFE,
        ]
    )
    _write_rom(rom_path, code)

    exit_code = debug_runner.main(
        [
            "--boot",
            "--rom",
            str(rom_path),
            "--cycles",
            "32",
            "--dump",
            str(dump_path),
            "--dump-range",
            "0000:0005",
            "--dump-format",
            "bin",
        ]
    )

    capsys.readouterr()
    assert exit_code == 2
    assert dump_path.read_bytes() == bytes(6)


def test_debug_runner_boot_uses_hardware_reset_condition_code(tmp_path, capsys) -> None:
    rom_path = tmp_path / "boot_cc.prg"
    dump_path = tmp_path / "cc.bin"
    code = bytes(
        [
            MB8861.OP_TPA_IMP,
            MB8861.OP_STAA_EXT,
            0x00,
            0x06,
            MB8861.OP_BRA_REL,
            0xFE,
        ]
    )
    _write_rom(rom_path, code)

    exit_code = debug_runner.main(
        [
            "--boot",
            "--rom",
            str(rom_path),
            "--cycles",
            "16",
            "--dump",
            str(dump_path),
            "--dump-range",
            "0006:0006",
            "--dump-format",
            "bin",
        ]
    )

    capsys.readouterr()
    assert exit_code == 2
    assert dump_path.read_bytes() == bytes([0xD0])


@pytest.mark.parametrize(
    "incompatible_args",
    [
        ["--program", "dummy.prg"],
        ["--start", "0x0300"],
    ],
)
def test_debug_runner_boot_rejects_program_entry_arguments(
    tmp_path, incompatible_args
) -> None:
    rom_path = tmp_path / "boot.prg"
    _write_rom(rom_path, bytes([MB8861.OP_BRA_REL, 0xFE]))

    with pytest.raises(SystemExit) as exc_info:
        debug_runner.main(["--boot", "--rom", str(rom_path), *incompatible_args])

    assert exc_info.value.code == 2


def test_debug_runner_boot_requires_explicit_rom() -> None:
    with pytest.raises(SystemExit) as exc_info:
        debug_runner.main(["--boot"])

    assert exc_info.value.code == 2
