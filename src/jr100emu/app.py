"""JR-100 emulator demo application."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from jr100emu.jr100.computer import JR100Computer
from jr100emu.jr100.display import JR100Display
from jr100emu.jr100.keyboard import JR100Keyboard
from jr100emu.emulator.file import ProgramInfo, ProgramLoadError
from jr100emu.frontend.debug_overlay import DebugOverlay

# Mapping from pygame key constants to (row, bit) in the keyboard matrix.
KEY_MATRIX_MAP: Dict[int, Tuple[int, int]] = {
    # Simplified mapping for demonstration.
    # Rows/bits chosen arbitrarily; they do not match the real JR-100 yet.
    97: (1, 0),   # a
    115: (1, 1),  # s
    100: (1, 2),  # d
    102: (1, 3),  # f
    106: (2, 0),  # j
    107: (2, 1),  # k
    108: (2, 2),  # l
    59: (2, 3),   # ;
    273: (3, 0),  # up
    274: (3, 1),  # down
    276: (3, 2),  # left
    275: (3, 3),  # right
}

KEY_LABELS: Dict[int, str] = {
    97: "A",
    115: "S",
    100: "D",
    102: "F",
    106: "J",
    107: "K",
    108: "L",
    59: ";",
    273: "UP",
    274: "DOWN",
    276: "LEFT",
    275: "RIGHT",
}


STEP_CYCLES = 256
SNAPSHOT_DIR = Path("snapshots")
SNAPSHOT_SLOTS = ["slot0", "slot1", "slot2", "slot3"]
DEFAULT_SLOT = SNAPSHOT_SLOTS[0]


@dataclass
class Snapshot:
    memory: List[int]
    cpu_registers: dict
    cpu_flags: dict
    cpu_status: dict
    via_state: dict
    clock_count: int


def _generate_character_rom(display: JR100Display) -> List[int]:
    import pygame  # type: ignore

    pygame.font.init()
    font = pygame.font.SysFont("Courier", 12, bold=False)
    rom: List[int] = [0x00] * (256 * display.PPC)
    for code in range(32, 127):
        char = chr(code)
        glyph_surface = pygame.Surface((display.PPC, display.PPC))
        glyph_surface.fill((0, 0, 0))
        rendered = font.render(char, True, (255, 255, 255))
        # Center glyph inside 8x8 box
        rect = rendered.get_rect()
        rect.center = (display.PPC // 2, display.PPC // 2)
        glyph_surface.blit(rendered, rect)
        for line in range(display.PPC):
            value = 0
            for bit in range(display.PPC):
                pixel = glyph_surface.get_at((bit, line))
                if sum(pixel[:3]) > 0:
                    value |= 1 << (7 - bit)
            rom[code * display.PPC + line] = value
    return rom


def _handle_key_event(keyboard: JR100Keyboard, key: int, pressed: bool) -> None:
    mapping = KEY_MATRIX_MAP.get(key)
    if mapping is None:
        return
    row, bit = mapping
    if pressed:
        keyboard.press(row, bit)
    else:
        keyboard.release(row, bit)


def _load_program_for_demo(computer: JR100Computer, program_path: str | None) -> Tuple[str, Optional[ProgramInfo]]:
    base_caption = "JR-100 Emulator Demo"
    if program_path in (None, ""):
        return base_caption, None
    try:
        info = computer.load_user_program(program_path)
    except (ProgramLoadError, OSError) as exc:
        raise SystemExit(f"プログラムの読み込みに失敗しました: {exc}")
    caption = f"{base_caption} | Program: {info.name}"
    return caption, info


def _pygame_loop(scale: int, fps: int, program_path: str | None) -> None:
    import pygame  # type: ignore

    computer = JR100Computer()
    base_caption, program_info = _load_program_for_demo(computer, program_path)
    if program_info is not None and program_info.comment:
        print(f"Loaded program: {program_info.name} -- {program_info.comment}")

    display = computer.hardware.display
    display.load_character_rom(_generate_character_rom(display))

    keyboard = computer.hardware.keyboard
    overlay = DebugOverlay(computer)

    pygame.init()
    screen = pygame.display.set_mode(
        (display.WIDTH_CHARS * display.PPC * scale, display.HEIGHT_CHARS * display.PPC * scale)
    )
    pygame.display.set_caption(base_caption)
    clock = pygame.time.Clock()

    running = True
    debug_mode = False
    snapshot_slot = DEFAULT_SLOT
    snapshot_db = SnapshotDatabase()
    snapshot: Optional[Snapshot] = _read_snapshot_from_file(snapshot_slot)
    overlay.set_snapshot_available(snapshot is not None)
    overlay.set_slot_name(snapshot_slot)

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    debug_mode = not debug_mode
                    if debug_mode:
                        overlay.capture_state()
                        overlay.set_status("Debug paused")
                    else:
                        pygame.display.set_caption(base_caption)
                        overlay.set_status("")
                    continue
                if debug_mode and event.key == pygame.K_q:
                    running = False
                    continue
                if debug_mode:
                    if event.key == pygame.K_SPACE:
                        debug_mode = False
                        overlay.set_status("Resumed")
                        pygame.display.set_caption(base_caption)
                        continue
                    if event.key == pygame.K_n:
                        _execute_step(computer, overlay)
                        overlay.set_status("Stepped")
                        overlay.capture_state()
                        continue
                    if event.key == pygame.K_s:
                        snapshot = _take_snapshot(computer)
                        overlay.set_snapshot_available(snapshot is not None)
                        overlay.set_status("Snapshot saved" if snapshot else "Snapshot failed")
                        if snapshot is not None:
                            comment = "Paused snapshot"
                            _write_snapshot_to_file(snapshot_slot, snapshot, comment=comment)
                            snapshot_db.set_slot(snapshot_slot, comment=comment)
                            overlay.update_metadata(snapshot_slot, comment)
                        overlay.capture_state()
                        continue
                    if event.key == pygame.K_r:
                        if snapshot is not None:
                            _restore_snapshot(computer, snapshot)
                            overlay.set_status("Snapshot restored")
                            overlay.capture_state()
                        else:
                            loaded = _read_snapshot_from_file(snapshot_slot)
                            if loaded is not None:
                                snapshot = loaded
                                _restore_snapshot(computer, snapshot)
                                overlay.set_snapshot_available(True)
                                overlay.set_status("Snapshot restored (file)")
                                overlay.update_metadata(snapshot_slot, snapshot_db.get(snapshot_slot).comment if snapshot_db.get(snapshot_slot) else "")
                                overlay.capture_state()
                            else:
                                overlay.set_status("No snapshot")
                        continue
                    if event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                        index = event.key - pygame.K_1
                        if 0 <= index < len(SNAPSHOT_SLOTS):
                            snapshot_slot = SNAPSHOT_SLOTS[index]
                            overlay.set_slot_name(snapshot_slot)
                            loaded = _read_snapshot_from_file(snapshot_slot)
                            snapshot = loaded
                            overlay.set_snapshot_available(snapshot is not None)
                            slot_meta = snapshot_db.get(snapshot_slot)
                            comment = slot_meta.comment if slot_meta else ""
                            overlay.update_metadata(snapshot_slot, comment)
                            overlay.set_status(f"Slot switched to {snapshot_slot}")
                            overlay.capture_state()
                        continue
                else:
                    _handle_key_event(keyboard, event.key, True)
            elif event.type == pygame.KEYUP and not debug_mode:
                _handle_key_event(keyboard, event.key, False)

        surface = display.render_pygame_surface(scale)
        screen.blit(surface, (0, 0))

        if debug_mode:
            overlay.render(screen)
            pygame.display.flip()
            clock.tick(fps)
            continue

        pressed_keys = [KEY_LABELS[k] for k in KEY_MATRIX_MAP if pygame.key.get_pressed()[k]]
        keys_summary = " ".join(pressed_keys) if pressed_keys else "-"
        pygame.display.set_caption(f"{base_caption} | Keys: {keys_summary}")

        cycles_per_frame = max(int(computer.get_clock_frequency() / fps), 1000)
        executed = 0
        timeslice = 512
        while executed < cycles_per_frame:
            step = min(timeslice, cycles_per_frame - executed)
            computer.tick(step)
            executed += step
            if computer.cpu_core is not None:
                overlay.record_execution(computer.cpu_core.registers.program_counter)
        overlay.capture_state()

        pygame.display.flip()
        clock.tick(fps)

    pygame.quit()


def _execute_step(computer: JR100Computer, overlay: DebugOverlay) -> None:
    computer.tick(STEP_CYCLES)
    if computer.cpu_core is not None:
        overlay.record_execution(computer.cpu_core.registers.program_counter)


def _take_snapshot(computer: JR100Computer) -> Optional[Snapshot]:
    cpu = computer.cpu_core
    via = computer.via
    memory = computer.memory
    if cpu is None or via is None or memory is None:
        return None
    memory_dump = [memory.load8(addr) & 0xFF for addr in range(0x10000)]
    cpu_regs = cpu.registers
    cpu_flags = cpu.flags
    cpu_status = cpu.status
    via_state = via._state
    snapshot = Snapshot(
        memory=memory_dump,
        cpu_registers=dict(
            acc_a=cpu_regs.acc_a,
            acc_b=cpu_regs.acc_b,
            index=cpu_regs.index,
            stack_pointer=cpu_regs.stack_pointer,
            program_counter=cpu_regs.program_counter,
        ),
        cpu_flags=dict(
            carry_h=cpu_flags.carry_h,
            carry_i=cpu_flags.carry_i,
            carry_n=cpu_flags.carry_n,
            carry_z=cpu_flags.carry_z,
            carry_v=cpu_flags.carry_v,
            carry_c=cpu_flags.carry_c,
        ),
        cpu_status=dict(
            reset_requested=cpu_status.reset_requested,
            nmi_requested=cpu_status.nmi_requested,
            irq_requested=cpu_status.irq_requested,
            halt_requested=cpu_status.halt_requested,
            halt_processed=cpu_status.halt_processed,
            fetch_wai=cpu_status.fetch_wai,
        ),
        via_state=dict(via_state.__dict__),
        clock_count=computer.clock_count,
    )
    return snapshot


def _restore_snapshot(computer: JR100Computer, snapshot: Snapshot) -> None:
    cpu = computer.cpu_core
    via = computer.via
    memory = computer.memory
    if cpu is None or via is None or memory is None:
        return
    for addr, value in enumerate(snapshot.memory):
        memory.store8(addr, value)

    regs = cpu.registers
    regs.acc_a = snapshot.cpu_registers["acc_a"]
    regs.acc_b = snapshot.cpu_registers["acc_b"]
    regs.index = snapshot.cpu_registers["index"]
    regs.stack_pointer = snapshot.cpu_registers["stack_pointer"]
    regs.program_counter = snapshot.cpu_registers["program_counter"]

    flags = cpu.flags
    for key, value in snapshot.cpu_flags.items():
        setattr(flags, key, value)

    status = cpu.status
    for key, value in snapshot.cpu_status.items():
        setattr(status, key, value)

    for key, value in snapshot.via_state.items():
        setattr(via._state, key, value)

    computer.clock_count = snapshot.clock_count


def _write_snapshot_to_file(slot: str, snapshot: Snapshot, *, comment: str = "") -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{slot}.json"
    serializable = {
        "memory": snapshot.memory,
        "cpu_registers": snapshot.cpu_registers,
        "cpu_flags": snapshot.cpu_flags,
        "cpu_status": snapshot.cpu_status,
        "via_state": snapshot.via_state,
        "clock_count": snapshot.clock_count,
        "comment": comment,
    }
    path.write_text(json.dumps(serializable))


def _read_snapshot_from_file(slot: str) -> Optional[Snapshot]:
    path = SNAPSHOT_DIR / f"{slot}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return Snapshot(
        memory=list(data.get("memory", [])),
        cpu_registers=dict(data.get("cpu_registers", {})),
        cpu_flags=dict(data.get("cpu_flags", {})),
        cpu_status=dict(data.get("cpu_status", {})),
        via_state=dict(data.get("via_state", {})),
        clock_count=int(data.get("clock_count", 0)),
    )


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="JR-100 emulator demo")
    parser.add_argument("--scale", type=int, default=2, help="Integer scaling factor for display (default: 2)")
    parser.add_argument("--fps", type=int, default=30, help="Target frames per second for the demo loop")
    parser.add_argument("--program", "-p", help="Path to a PROG/BASIC file to load at startup")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.scale <= 0:
        raise SystemExit("scale must be positive")
    if args.fps <= 0:
        raise SystemExit("fps must be positive")

    try:
        _pygame_loop(args.scale, args.fps, args.program)
    except RuntimeError as exc:
        raise SystemExit(str(exc))
if __name__ == "__main__":
    main()
