from __future__ import annotations

import struct
from pathlib import Path

from jr100emu import debug_runner


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
