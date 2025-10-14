"""Headless runner for JR-100 machine-language debugging workflows."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from jr100emu.emulator.file import ProgramLoadError
from jr100emu.jr100.computer import JR100Computer


DEFAULT_WARMUP_CYCLES = 80_000
DEFAULT_MAX_CYCLES = 1_000_000
DEFAULT_STACK_POINTER = 0x0244
EXECUTION_CHUNK = 256
ADDRESS_MASK = 0xFFFF


@dataclass(frozen=True)
class DumpRange:
    """Inclusive memory range used for dumping."""

    start: int
    end: int

    def iter_addresses(self) -> Iterable[int]:
        for address in range(self.start, self.end + 1):
            yield address & ADDRESS_MASK


def _parse_hex(value: str) -> int:
    text = value.strip().lower()
    if text.startswith("0x"):
        text = text[2:]
    if not text:
        raise ValueError("empty hexadecimal value")
    result = int(text, 16)
    if not (0 <= result <= ADDRESS_MASK):
        raise ValueError("hex value out of range")
    return result


def _parse_range(spec: str) -> DumpRange:
    start_str, sep, end_str = spec.partition(":")
    if not sep:
        raise ValueError("range specification must contain ':'")
    start = _parse_hex(start_str)
    end = _parse_hex(end_str)
    if end < start:
        raise ValueError("range end must be >= start")
    return DumpRange(start, end)


def _merge_ranges(ranges: Sequence[DumpRange]) -> List[DumpRange]:
    if not ranges:
        return [DumpRange(0x0000, ADDRESS_MASK)]
    ordered = sorted(ranges, key=lambda r: (r.start, r.end))
    merged: List[DumpRange] = []
    for current in ordered:
        if not merged:
            merged.append(current)
            continue
        last = merged[-1]
        if current.start <= last.end + 1:
            merged[-1] = DumpRange(last.start, max(last.end, current.end))
        else:
            merged.append(current)
    return merged


def _format_hex_dump(memory, dump_ranges: Sequence[DumpRange]) -> str:
    lines: List[str] = []
    header = "ADDR " + " ".join(f"+{offset:X}" for offset in range(16))
    for index, dump_range in enumerate(dump_ranges):
        if index:
            lines.append("")
        lines.append(header)
        start_line = dump_range.start & ~0x0F
        end_line = dump_range.end | 0x0F
        for base in range(start_line, end_line + 1, 16):
            row = [f"{base & ADDRESS_MASK:04X}"]
            for offset in range(16):
                address = (base + offset) & ADDRESS_MASK
                value = memory.load8(address) & 0xFF
                row.append(f"{value:02X}")
            lines.append(" ".join(row))
    return "\n".join(lines)


def _write_dump(memory, dump_ranges: Sequence[DumpRange], *, target: Path | None, fmt: str) -> None:
    ranges = _merge_ranges(dump_ranges)
    if fmt == "bin":
        data = bytearray()
        for dump_range in ranges:
            for address in dump_range.iter_addresses():
                data.append(memory.load8(address) & 0xFF)
        if target is None:
            sys.stdout.buffer.write(bytes(data))
            return
        target.write_bytes(bytes(data))
        return

    text = _format_hex_dump(memory, ranges)
    if target is None:
        print(text)
    else:
        target.write_text(text + "\n")


def _setup_computer(rom_path: str | None) -> JR100Computer:
    computer = JR100Computer(rom_path=rom_path, enable_audio=False)
    computer.tick(DEFAULT_WARMUP_CYCLES)
    return computer


def _load_program(computer: JR100Computer, program_path: str) -> None:
    computer.load_user_program(program_path)


def _initialise_cpu_state(
    computer: JR100Computer,
    *,
    start_address: int,
    stack_pointer: int,
) -> None:
    cpu = computer.cpu_core
    if cpu is None:
        raise RuntimeError("CPU core is not available")
    cpu.registers.stack_pointer = stack_pointer & ADDRESS_MASK
    cpu.registers.program_counter = start_address & ADDRESS_MASK


def _execute_program(
    computer: JR100Computer,
    *,
    max_cycles: int | None,
    breakpoints: Sequence[int],
    max_seconds: float | None,
) -> Tuple[int, bool, bool, bool]:
    cpu = computer.cpu_core
    if cpu is None:
        raise RuntimeError("CPU core is not available")
    remaining = max_cycles
    break_set = {value & ADDRESS_MASK for value in breakpoints}
    break_hit = False
    timeout_hit = False
    cycle_hit = False
    deadline: float | None = None
    if max_seconds is not None and max_seconds >= 0:
        deadline = time.monotonic() + max_seconds
    executed_total = 0

    while remaining is None or remaining > 0:
        step = EXECUTION_CHUNK if remaining is None else min(EXECUTION_CHUNK, remaining)
        before = computer.clock_count
        computer.tick(step)
        after = computer.clock_count
        executed = after - before
        if executed <= 0:
            executed = step
        executed_total += executed
        if remaining is not None:
            remaining -= executed
        pc_value = cpu.registers.program_counter & ADDRESS_MASK
        if break_set and pc_value in break_set:
            break_hit = True
            break
        if deadline is not None and time.monotonic() >= deadline:
            timeout_hit = True
            break
        if remaining is not None and remaining <= 0:
            cycle_hit = True
            break

    return executed_total, break_hit, timeout_hit, cycle_hit


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jr100-debug-runner",
        description="Headless JR-100 runner for machine language diagnostics.",
    )
    parser.add_argument("--rom", type=str, default=None, help="Path to JR-100 BASIC ROM image")
    parser.add_argument("--program", type=str, required=True, help="User program (.prg/.prog/.bas)")
    parser.add_argument("--start", type=str, required=True, help="Hex start address for PC (e.g. 0x0300)")
    parser.add_argument(
        "--cycles",
        type=int,
        default=DEFAULT_MAX_CYCLES,
        help="Maximum cycles to execute (0 or negative disables the limit)",
    )
    parser.add_argument(
        "--break-pc",
        action="append",
        default=[],
        help="Break when PC reaches the given hex address (repeatable)",
    )
    parser.add_argument(
        "--dump",
        type=str,
        default=None,
        help="File path for memory dump (defaults to stdout)",
    )
    parser.add_argument(
        "--dump-range",
        action="append",
        default=[],
        help="Memory range to dump in START:END hex form (inclusive). Repeat to add multiple ranges.",
    )
    parser.add_argument(
        "--dump-format",
        choices=("hex", "bin"),
        default="hex",
        help="Dump format (hex table or raw binary)",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=None,
        help="Maximum wall-clock seconds to run before dumping memory",
    )
    parser.add_argument(
        "--stack-pointer",
        type=str,
        default=f"0x{DEFAULT_STACK_POINTER:04X}",
        help="Stack pointer initial value (hex). Defaults to JR-100 BASIC USR entry value.",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Skip issuing a system reset after loading the program",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_argument_parser()
    args = parser.parse_args(argv)

    try:
        start_address = _parse_hex(args.start)
    except ValueError as exc:
        parser.error(f"invalid start address: {exc}")

    breakpoints: List[int] = []
    for spec in args.break_pc:
        try:
            breakpoints.append(_parse_hex(spec))
        except ValueError as exc:
            parser.error(f"invalid breakpoint address '{spec}': {exc}")

    dump_ranges: List[DumpRange] = []
    for spec in args.dump_range:
        try:
            dump_ranges.append(_parse_range(spec))
        except ValueError as exc:
            parser.error(f"invalid dump range '{spec}': {exc}")

    try:
        stack_pointer = _parse_hex(args.stack_pointer)
    except ValueError as exc:
        parser.error(f"invalid stack pointer: {exc}")

    computer = _setup_computer(args.rom)

    try:
        _load_program(computer, args.program)
    except (OSError, ProgramLoadError) as exc:
        print(f"Failed to load program: {exc}", file=sys.stderr)
        return 1

    if not args.no_reset:
        computer.reset()
        computer.tick(1)

    _initialise_cpu_state(computer, start_address=start_address, stack_pointer=stack_pointer)

    cycle_limit = args.cycles if args.cycles > 0 else None

    executed_cycles, break_hit, timeout_hit, cycle_hit = _execute_program(
        computer,
        max_cycles=cycle_limit,
        breakpoints=breakpoints,
        max_seconds=args.seconds,
    )

    dump_target = Path(args.dump) if args.dump is not None else None
    memory = computer.memory
    _write_dump(memory, dump_ranges, target=dump_target, fmt=args.dump_format)

    if break_hit:
        return 0
    if timeout_hit:
        print("Execution stopped: time limit reached", file=sys.stderr)
        return 3
    if cycle_hit and args.cycles > 0:
        print("Execution stopped: cycle limit reached", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
