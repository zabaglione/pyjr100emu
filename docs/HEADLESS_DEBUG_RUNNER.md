# Headless Debug Runner Design

## Goals

- Provide a command line workflow to load a ROM, inject a PROG/BASIC user program, start execution from a specified address, and dump memory without launching the pygame frontend.
- Focus on machine language diagnostics (e.g. Maze tests described in `DEBUG.md`) where BASIC never regains control.
- Produce deterministic output that can be redirected to files or standard output; make the tool scriptable for CI/regression automation.

## Command Line Interface

Executable entry point (subject to implementation): `python -m jr100emu.debug_runner`

Required arguments:

- `--rom PATH`: JR-100 BASIC ROM path. Defaults to auto-detected ROM if omitted, but we allow explicit override for testing.
- `--program PATH`: User program to load (`.prg`/`.prog`/`.bas`). Mandatory.
- `--start ADDRESS`: Hex start address (`0x` prefix optional) used to initialize the program counter before execution.

Optional arguments (initial scope):

- `--cycles N`: Maximum CPU cycles to execute (N ≤ 0 disables the cycle limit). Default `1_000_000`.
- `--break-pc ADDRESS`: Stop when `PC == ADDRESS` after executing the current instruction. Accepts multiple occurrences. Matches Java-style breakpoint support.
- `--dump FILE`: Destination for memory dump. If omitted, dump to stdout.
- `--dump-range START:END`: One or more inclusive ranges (hex) limiting the dump. Default: full 0x0000–0xFFFF.
- `--dump-format {hex,bin}`: Hexadecimal text (default) or raw binary dump.
- `--seconds FLOAT`: Wall-clock time limit. When elapsed, execution stops and memory is dumped (exit code 3).
- `--stack-pointer HEX`: Override the initial stack pointer (defaults to `0x0244`, matching BASIC's USR entry state).
- `--no-reset`: Skip automatic machine reset before execution (for advanced users chaining runs).

Arguments intentionally **not** included in v1:

- Inline BASIC loader scheduling (BASIC text requires post-ROM init; this tool targets machine code first).
- Peripheral emulation toggles (audio, joystick) – headless mode keeps them disabled.
- Interactive stepping – out-of-scope for batch pipeline.

## Execution Flow

1. Instantiate `JR100Computer` with `enable_audio=False`, `extended_ram` flag optional via CLI.
2. Perform initial `computer.tick(ROM_WARMUP_CYCLES)` similar to frontend to ensure hardware settles.
3. Load the user program via `computer.load_user_program`. For BASIC text we reuse `BasicLoader`-style pointer fix-ups only after guaranteeing ROM BASIC pointers updated (defer to existing loader).
4. Force CPU register state:
   - Reset CPU (ensuring memory/peripheral reset).
   - Set `PC` to `--start`.
   - Optionally set `SR`/`A`/`B`/`IX` via future CLI expansion (not in initial delivery).
5. Enter execution loop up to `--cycles` (unless disabled) and/or until `--seconds` expires. On each iteration:
   - Execute chunk-sized ticks (e.g. 128 cycles) for efficiency.
   - Check breakpoint conditions. Breakpoint hit triggers memory dump and exit with code 0.
6. If cycles are exhausted (and the limit is enabled), exit with code 2. If the time limit expires, exit with code 3. If PC hits `--break-pc`, exit 0. Unexpected exceptions exit 1.

## Memory Dump Format

Default `hex` output:

```
ADDR +0 +1 … +F
0000 00 01 … 0F
...
```

This mirrors the F2 hex viewer layout for consistency. When `--dump-format bin`, emit raw bytes concatenated in address order.

Multiple `--dump-range` options allow splitting output; ranges outside 0–0xFFFF are clamped. Overlapping ranges are merged.

## Logging/Diagnostics

- Support `--trace-via` style toggles (future) to mirror existing environment var debugging.
- Non-zero exits accompany human-readable message to stderr.

## Interaction with Existing Systems

- Shares ROM/user-program loaders with the frontend (`load_prog`, `load_basic_text`).
- Must *not* disturb `BasicLoader` queue semantics already used by the pygame app; the new module runs independently.
- Reuses `jr100emu.memory` for dumps; avoid duplicating hex formatting logic by factoring helper used by both debug runner and F2 viewer (possibly `jr100emu.frontend.hexformat` utility).

## Testing Strategy

- Unit tests covering:
  - Argument parsing (valid/invalid addresses, multiple ranges).
  - Execution loop stops on cycle limit and breakpoints (using synthetic CPU stubs or short programs).
  - Dump formatting (hex/bin) and range clipping.
- Integration test running a small PROG sample that writes sentinel bytes and halts via `BRA` loop; verify dump matches expectation.
- Guard against regression where BASIC loads require UI intervention (explicit tests for machine-code PROG path).

## Open Questions / Future Work

- Optional trace logging (e.g. CSV of executed opcodes).
- Support BASIC text loading by scheduling pointer stabilization after ROM warm-up (mirroring `BasicLoader`). Needs careful sequencing to avoid previous issues.
- Optionally expose CPU registers/flags initialization.
- Provide scriptable snapshot/restore around machine code runs.
