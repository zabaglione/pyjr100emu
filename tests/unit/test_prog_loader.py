from __future__ import annotations

import io
from pathlib import Path
import struct
from tempfile import NamedTemporaryFile

import pytest

from jr100emu.emulator.file import load_prog, load_prog_bytes
from jr100emu.memory import MemorySystem, RAM


@pytest.fixture
def memory() -> MemorySystem:
    system = MemorySystem()
    system.allocate_space(0x10000)
    system.register_memory(RAM(0x0000, 0x10000))
    return system


def test_load_prog_pbin_without_comment(memory: MemorySystem) -> None:
    start = 0x0600
    payload = b"\x01\x02\x03"

    def build_prog() -> bytes:
        chunks: list[bytes] = []
        chunks.append(b"PROG")
        chunks.append((2).to_bytes(4, "little"))
        # Optional PNAM section (empty)
        chunks.append(b"PNAM")
        chunks.append((4).to_bytes(4, "little"))
        chunks.append((0).to_bytes(4, "little"))
        # PBIN without comment
        section_payload = (
            start.to_bytes(4, "little") + len(payload).to_bytes(4, "little") + payload
        )
        chunks.append(b"PBIN")
        chunks.append(len(section_payload).to_bytes(4, "little"))
        chunks.append(section_payload)
        return b"".join(chunks)

    with NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(build_prog())

    try:
        info = load_prog(memory, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    assert info.address_regions[0].start == start
    assert info.address_regions[0].end == start + len(payload) - 1
    assert memory.load8(start) == payload[0]
    assert memory.load8(start + 1) == payload[1]
    assert memory.load8(start + 2) == payload[2]


def _prog_v2(*sections: tuple[bytes, bytes]) -> bytes:
    stream = io.BytesIO()
    stream.write(b"PROG")
    stream.write(struct.pack("<I", 2))
    for identifier, payload in sections:
        stream.write(identifier)
        stream.write(struct.pack("<I", len(payload)))
        stream.write(payload)
    return stream.getvalue()


def _pbin(start: int, data: bytes, comment: str = "") -> bytes:
    encoded_comment = comment.encode("utf-8")
    return (
        struct.pack("<I", start)
        + struct.pack("<I", len(data))
        + data
        + struct.pack("<I", len(encoded_comment))
        + encoded_comment
    )


def test_load_prog_bytes_uses_explicit_v2_entry_comment(memory: MemorySystem) -> None:
    data = _prog_v2(
        (b"PBIN", _pbin(0x4000, b"\x01\x02", "entry=$4010")),
        (b"PBIN", _pbin(0x4100, b"\x03")),
    )

    info = load_prog_bytes(memory, data, filename="demo.prg")

    assert info.version == 2
    assert info.entry_point == 0x4010
    assert info.entry_source == "comment"
    assert info.name == "DEMO"
    assert memory.load8(0x4001) == 0x02
    assert memory.load8(0x4100) == 0x03


def test_load_prog_bytes_falls_back_to_first_v2_binary_start(
    memory: MemorySystem,
) -> None:
    data = _prog_v2(
        (b"PBIN", _pbin(0x3200, b"\x20\xfe")),
        (b"PBIN", _pbin(0x3000, b"\x00")),
    )

    info = load_prog_bytes(memory, data)

    assert info.version == 2
    assert info.entry_point is None
    assert info.suggested_entry_point == 0x3200
    assert info.entry_source == "pbin-start"
