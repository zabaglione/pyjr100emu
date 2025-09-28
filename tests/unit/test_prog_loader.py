from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from jr100emu.emulator.file import ProgramLoadError, load_prog
from jr100emu.memory import MemorySystem, RAM


def test_load_prog_pbin_without_comment() -> None:
    memory = MemorySystem()
    memory.allocate_space(0x10000)
    memory.register_memory(RAM(0x0000, 0x10000))

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
            start.to_bytes(4, "little")
            + len(payload).to_bytes(4, "little")
            + payload
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
