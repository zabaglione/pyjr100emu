"""Headless runner for JR-100 machine-language debugging workflows."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, TextIO, Tuple

from jr100emu.emulator.file import ProgramLoadError
from jr100emu.jr100.computer import JR100Computer


DEFAULT_WARMUP_CYCLES = 80_000
DEFAULT_MAX_CYCLES = 1_000_000
DEFAULT_STACK_POINTER = 0x0244
BOOT_STACK_POINTER = 0x0000
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


def _setup_computer(
    rom_path: str | None,
    *,
    warmup_cycles: int = DEFAULT_WARMUP_CYCLES,
) -> JR100Computer:
    computer = JR100Computer(rom_path=rom_path, enable_audio=False)
    if warmup_cycles > 0:
        computer.tick(warmup_cycles)
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


def _clear_registers(computer: JR100Computer) -> None:
    """Normalise A/B/IX and flags for reproducible lockstep runs."""
    cpu = computer.cpu_core
    if cpu is None:
        raise RuntimeError("CPU core is not available")
    cpu.registers.acc_a = 0x00
    cpu.registers.acc_b = 0x00
    cpu.registers.index = 0x0000
    cpu.flags.carry_h = False
    cpu.flags.carry_i = False
    cpu.flags.carry_n = False
    cpu.flags.carry_z = False
    cpu.flags.carry_v = False
    cpu.flags.carry_c = False


def _normalise_boot_state(computer: JR100Computer) -> None:
    """Set deterministic registers while preserving the reset-vector PC."""
    cpu = computer.cpu_core
    if cpu is None:
        raise RuntimeError("CPU core is not available")
    cpu.registers.acc_a = 0x00
    cpu.registers.acc_b = 0x00
    cpu.registers.index = 0x0000
    cpu.registers.stack_pointer = BOOT_STACK_POINTER
    cpu.flags.carry_h = False
    cpu.flags.carry_i = True
    cpu.flags.carry_n = False
    cpu.flags.carry_z = False
    cpu.flags.carry_v = False
    cpu.flags.carry_c = False


def _normalise_program_via_state(computer: JR100Computer) -> None:
    """Zero the reset-exempt VIA storage for program-mode lockstep runs.

    R6522 RES preserves T1/T2 counters, latches, and SR, so after the
    warmup + reset sequence they hold warmup residue that a cold-started
    DUT cannot reproduce. Program mode zeroes them as a comparison
    convention; boot mode starts cold and needs no normalisation.
    """
    state = computer.via._state
    state.timer1 = 0
    state.timer2 = 0
    state.latch1 = 0
    state.latch2 = 0
    state.SR = 0


def _save_memory_image(memory, target: Path) -> None:
    """Write the full 64 KiB address space as a raw binary image."""
    data = bytearray(0x10000)
    for address in range(0x10000):
        data[address] = memory.load8(address) & 0xFF
    target.write_bytes(bytes(data))


def _ccr_byte(flags) -> int:
    """Pack CPU flags into the MB8861 CCR byte (11HINZVC)."""
    ccr = 0xC0
    if flags.carry_h:
        ccr |= 0x20
    if flags.carry_i:
        ccr |= 0x10
    if flags.carry_n:
        ccr |= 0x08
    if flags.carry_z:
        ccr |= 0x04
    if flags.carry_v:
        ccr |= 0x02
    if flags.carry_c:
        ccr |= 0x01
    return ccr


def _format_trace_line(computer: JR100Computer, *, sample_index: int) -> str:
    """Format one instruction-boundary sample (docs/TRACE_FORMAT.md v1)."""
    cpu = computer.cpu_core
    if cpu is None:
        raise RuntimeError("CPU core is not available")
    regs = cpu.registers
    via_state = computer.via._state
    return (
        f"S n={sample_index}"
        f" clk={int(computer.clock_count)}"
        f" pc={regs.program_counter & ADDRESS_MASK:04X}"
        f" a={regs.acc_a & 0xFF:02X}"
        f" b={regs.acc_b & 0xFF:02X}"
        f" ix={regs.index & ADDRESS_MASK:04X}"
        f" sp={regs.stack_pointer & ADDRESS_MASK:04X}"
        f" cc={_ccr_byte(cpu.flags):02X}"
        f" ora={via_state.ORA & 0xFF:02X}"
        f" orb={via_state.ORB & 0xFF:02X}"
        f" ddra={via_state.DDRA & 0xFF:02X}"
        f" ddrb={via_state.DDRB & 0xFF:02X}"
        f" acr={via_state.ACR & 0xFF:02X}"
        f" pcr={via_state.PCR & 0xFF:02X}"
        f" ifr={via_state.IFR & 0xFF:02X}"
        f" ier={via_state.IER & 0xFF:02X}"
        f" sr={via_state.SR & 0xFF:02X}"
        f" t1={via_state.timer1 & ADDRESS_MASK:04X}"
        f" t1l={via_state.latch1 & ADDRESS_MASK:04X}"
        f" t2={via_state.timer2 & ADDRESS_MASK:04X}"
        f" t2l={via_state.latch2 & ADDRESS_MASK:04X}"
    )


def _execute_program(
    computer: JR100Computer,
    *,
    max_cycles: int | None,
    breakpoints: Sequence[int],
    max_seconds: float | None,
    trace_sink: TextIO | None = None,
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
    sample_index = 0
    # Tracing samples at every instruction boundary, so it steps one tick at
    # a time; untraced runs keep the faster chunked execution.
    chunk = 1 if trace_sink is not None else EXECUTION_CHUNK

    while remaining is None or remaining > 0:
        step = chunk if remaining is None else min(chunk, remaining)
        before = computer.clock_count
        computer.tick(step)
        after = computer.clock_count
        executed = after - before
        if executed <= 0:
            executed = step
        elif trace_sink is not None:
            sample_index += 1
            print(_format_trace_line(computer, sample_index=sample_index), file=trace_sink)
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
    parser.add_argument(
        "--boot",
        action="store_true",
        help="Trace ROM startup from the hardware reset state",
    )
    parser.add_argument("--rom", type=str, default=None, help="Path to JR-100 BASIC ROM image")
    parser.add_argument("--program", type=str, default=None, help="User program (.prg/.prog/.bas)")
    parser.add_argument("--start", type=str, default=None, help="Hex start address for PC (e.g. 0x0300)")
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
        default=None,
        help="Stack pointer initial value (hex). Defaults to JR-100 BASIC USR entry value.",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Skip issuing a system reset after loading the program",
    )
    parser.add_argument(
        "--trace",
        type=str,
        default=None,
        help="Write an instruction-boundary trace to the given file ('-' for stdout)",
    )
    parser.add_argument(
        "--clear-regs",
        action="store_true",
        help="Zero A/B/IX and clear all flags before execution (lockstep runs)",
    )
    parser.add_argument(
        "--save-initial-memory",
        type=str,
        default=None,
        help="Write the pre-execution 64 KiB memory image to the given file",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_argument_parser()
    args = parser.parse_args(argv)

    if args.boot:
        if args.rom is None:
            parser.error("--boot requires --rom")
        if not Path(args.rom).is_file():
            parser.error("--boot ROM path must reference an existing file")
        if args.program is not None or args.start is not None:
            parser.error("--boot cannot be combined with --program or --start")
        if args.no_reset:
            parser.error("--boot cannot be combined with --no-reset")
        if args.clear_regs:
            parser.error("--boot cannot be combined with --clear-regs")
        if args.stack_pointer is not None:
            parser.error("--boot cannot be combined with --stack-pointer")
        start_address = None
        stack_pointer = BOOT_STACK_POINTER
    else:
        if args.program is None or args.start is None:
            parser.error("--program and --start are required unless --boot is specified")
        try:
            start_address = _parse_hex(args.start)
        except ValueError as exc:
            parser.error(f"invalid start address: {exc}")
        try:
            stack_pointer = _parse_hex(
                args.stack_pointer
                if args.stack_pointer is not None
                else f"0x{DEFAULT_STACK_POINTER:04X}"
            )
        except ValueError as exc:
            parser.error(f"invalid stack pointer: {exc}")

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

    computer = _setup_computer(
        args.rom,
        warmup_cycles=0 if args.boot else DEFAULT_WARMUP_CYCLES,
    )

    if args.boot:
        computer.reset()
        computer.tick(1)
        _normalise_boot_state(computer)
    else:
        try:
            _load_program(computer, args.program)
        except (OSError, ProgramLoadError) as exc:
            print(f"Failed to load program: {exc}", file=sys.stderr)
            return 1

        if not args.no_reset:
            computer.reset()
            # Zero the reset-exempt VIA storage before the reset tick so
            # the timer phase matches a cold-started DUT (same structure
            # as the boot flow, where the storage is zero at reset).
            _normalise_program_via_state(computer)
            computer.tick(1)

        _initialise_cpu_state(
            computer,
            start_address=start_address,
            stack_pointer=stack_pointer,
        )

        if args.clear_regs:
            _clear_registers(computer)

    if args.save_initial_memory is not None:
        _save_memory_image(computer.memory, Path(args.save_initial_memory))

    cycle_limit = args.cycles if args.cycles > 0 else None

    trace_sink: TextIO | None = None
    trace_file: TextIO | None = None
    if args.trace is not None:
        if args.trace == "-":
            trace_sink = sys.stdout
        else:
            trace_file = Path(args.trace).open("w", encoding="utf-8")
            trace_sink = trace_file
        print("# jr100-trace v1", file=trace_sink)
        print("# generator: pyjr100emu debug_runner", file=trace_sink)
        source_path = args.rom if args.boot else args.program
        print(f"# program: {Path(source_path).name}", file=trace_sink)

    try:
        executed_cycles, break_hit, timeout_hit, cycle_hit = _execute_program(
            computer,
            max_cycles=cycle_limit,
            breakpoints=breakpoints,
            max_seconds=args.seconds,
            trace_sink=trace_sink,
        )
    finally:
        if trace_file is not None:
            trace_file.close()

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
