"""JR-100 emulator demo application."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Dict, Iterable, List, Optional, Tuple

from jr100emu.basic_loader import BasicLoader
from jr100emu.jr100.computer import JR100Computer
from jr100emu.jr100.display import JR100Display
from jr100emu.jr100.keyboard import JR100Keyboard
from jr100emu.emulator.file import ProgramInfo, ProgramLoadError
from jr100emu.frontend.debug_overlay import DebugOverlay
from jr100emu.frontend.file_menu import FileMenu
from jr100emu.frontend.snapshot_db import (
    SnapshotDatabase,
    SNAPSHOT_SLOTS,
    DEFAULT_SLOT,
    SNAPSHOT_DIR,
    SNAPSHOT_HISTORY_DIR,
)

# Mapping from pygame key constants to (row, bit) in the keyboard matrix.
BASE_CAPTION = "JR-100 Emulator Demo"
KEY_MATRIX_MAP: Dict[int, Tuple[int, int]] = {
    ord("c"): (0, 4),
    ord("x"): (0, 3),
    ord("z"): (0, 2),
    1073742049: (0, 1),  # pygame.K_LSHIFT
    1073742053: (0, 1),  # pygame.K_RSHIFT
    1073742048: (0, 0),  # pygame.K_LCTRL
    1073742052: (0, 0),  # pygame.K_RCTRL
    ord("g"): (1, 4),
    ord("f"): (1, 3),
    ord("d"): (1, 2),
    ord("s"): (1, 1),
    ord("a"): (1, 0),
    ord("t"): (2, 4),
    ord("r"): (2, 3),
    ord("e"): (2, 2),
    ord("w"): (2, 1),
    ord("q"): (2, 0),
    ord("5"): (3, 4),
    ord("4"): (3, 3),
    ord("3"): (3, 2),
    ord("2"): (3, 1),
    ord("1"): (3, 0),
    ord("0"): (4, 4),
    ord("9"): (4, 3),
    ord("8"): (4, 2),
    ord("7"): (4, 1),
    ord("6"): (4, 0),
    ord("p"): (5, 4),
    ord("o"): (5, 3),
    ord("i"): (5, 2),
    ord("u"): (5, 1),
    ord("y"): (5, 0),
    59: (6, 4),  # ';'
    ord("l"): (6, 3),
    ord("k"): (6, 2),
    ord("j"): (6, 1),
    ord("h"): (6, 0),
    44: (7, 4),  # ','
    ord("m"): (7, 3),
    ord("n"): (7, 2),
    ord("b"): (7, 1),
    ord("v"): (7, 0),
    45: (8, 4),  # '-'
    13: (8, 3),  # RETURN
    58: (8, 2),  # ':' key (JIS dedicated)
    42: (8, 2),  # '*' (shift + ':' on JIS)
    43: (8, 2),  # '+' (shift + ';' on ANSI)
    ord(" "): (8, 1),
    46: (8, 0),  # '.'
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


def _generate_character_rom(
    display: JR100Display,
    *,
    allow_background_events: bool = False,
) -> List[int]:
    if allow_background_events:
        os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
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


def _pygame_loop(
    scale: int,
    fps: int,
    *,
    rom_path: str | None = None,
    enable_audio: bool | None = None,
    enable_joystick: bool = False,
    joystick_config_path: str | None = None,
    joystick_index: int | None = None,
    joystick_name: str | None = None,
    joystick_keymap_path: str | None = None,
) -> None:
    import pygame  # type: ignore

    def _build_base_caption(info: Optional[ProgramInfo]) -> str:
        if info is None:
            return BASE_CAPTION
        return f"{BASE_CAPTION} | Program: {info.name}"

    computer = JR100Computer(rom_path=rom_path, enable_audio=enable_audio)
    if joystick_keymap_path:
        try:
            computer.load_joystick_keymap(joystick_keymap_path)
        except Exception as exc:
            print(f"ジョイスティックキーマップの読み込みに失敗しました: {exc}")

    program_info: Optional[ProgramInfo] = None
    base_caption = BASE_CAPTION

    loader = BasicLoader(computer)

    initial_menu_root = Path("datas")
    if not initial_menu_root.exists():
        initial_menu_root = Path.cwd()

    file_menu = FileMenu(initial_menu_root)

    computer.tick(80_000)

    display = computer.hardware.display
    if computer.basic_rom is not None:
        glyph_bytes = computer.basic_rom.data[: display.PPC * 256]
        if len(glyph_bytes) == display.PPC * 256:
            display.load_character_rom(glyph_bytes)
    else:
        display.load_character_rom(
            _generate_character_rom(display, allow_background_events=enable_joystick)
        )

    keyboard = computer.hardware.keyboard
    overlay = DebugOverlay(computer)
    sound_processor = getattr(computer.hardware, "sound_processor", None)

    pygame.init()
    screen = pygame.display.set_mode(
        (display.WIDTH_CHARS * display.PPC * scale, display.HEIGHT_CHARS * display.PPC * scale)
    )
    pygame.display.set_caption(base_caption)
    clock = pygame.time.Clock()

    gamepad_device = getattr(computer, "gamepad", None)
    if enable_joystick and gamepad_device is not None:
        if joystick_config_path:
            try:
                gamepad_device.load_mapping(joystick_config_path)
            except Exception as exc:
                print(f"ジョイスティックマッピングの読み込みに失敗しました: {exc}")
        gamepad_device.enable_pygame_backend(
            device_index=joystick_index,
            name_filter=joystick_name,
        )
        backend = gamepad_device.backend
        if backend is not None:
            try:
                backend.initialize()
            except Exception:
                enable_joystick = False
    else:
        enable_joystick = False

    trace_pc_vram = os.getenv("JR100EMU_TRACE_PC_VRAM") is not None
    running = True
    debug_mode = False
    snapshot_slot = DEFAULT_SLOT
    snapshot_db = SnapshotDatabase()
    snapshot: Optional[Snapshot] = _read_snapshot_from_file(snapshot_slot)
    overlay.set_snapshot_available(snapshot is not None)
    overlay.set_slot_name(snapshot_slot)
    slot_meta = snapshot_db.get(snapshot_slot)
    comment_buffer = slot_meta.comment if slot_meta else ""
    editing_comment = False


    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if file_menu.active:
                result = file_menu.handle_event(event)
                if result:
                    action, payload = result
                    if action == "close":
                        overlay.set_status("File menu closed")
                    elif action == "load" and payload is not None:
                        loader.queue(payload)
                        overlay.set_status(f"Loading {payload.name}")
                        base_caption = f"{BASE_CAPTION} | Loading..."
                        file_menu.root = payload.parent
                        file_menu.refresh()
                        file_menu.close()
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F1 and not debug_mode:
                    toggled = file_menu.toggle()
                    if toggled:
                        file_menu.refresh()
                        overlay.set_status("File menu opened")
                    else:
                        overlay.set_status("File menu closed")
                    continue

                if event.key == pygame.K_ESCAPE:
                    debug_mode = not debug_mode
                    if debug_mode:
                        overlay.capture_state()
                        overlay.set_status("Debug paused")
                        slot_meta = snapshot_db.get(snapshot_slot)
                        comment_buffer = slot_meta.comment if slot_meta else comment_buffer
                        overlay.set_comment_buffer(None)
                    else:
                        pygame.display.set_caption(base_caption)
                        overlay.set_status("")
                        editing_comment = False
                        overlay.set_comment_buffer(None)
                    continue
                if debug_mode and event.key == pygame.K_q:
                    running = False
                    continue
                if debug_mode:
                    if editing_comment:
                        if event.key == pygame.K_RETURN and (event.mod & pygame.KMOD_SHIFT):
                            comment_buffer += "\n"
                            overlay.set_status("Editing comment")
                            overlay.set_comment_buffer(comment_buffer)
                            continue
                        if event.key == pygame.K_RETURN:
                            snapshot_db.set_slot(snapshot_slot, comment=comment_buffer)
                            snapshot_db = SnapshotDatabase()
                            if snapshot is not None:
                                _write_snapshot_to_file(snapshot_slot, snapshot, comment=comment_buffer)
                            overlay.update_metadata(snapshot_slot, comment_buffer)
                            overlay.set_status("Comment saved")
                            editing_comment = False
                            overlay.set_comment_buffer(None)
                        elif event.key == pygame.K_ESCAPE:
                            overlay.set_status("Comment edit cancelled")
                            editing_comment = False
                            overlay.set_comment_buffer(None)
                        elif event.key == pygame.K_BACKSPACE:
                            comment_buffer = comment_buffer[:-1]
                            overlay.set_status(f"Editing comment: {comment_buffer}")
                            overlay.set_comment_buffer(comment_buffer)
                        else:
                            if event.unicode and event.unicode.isprintable():
                                comment_buffer += event.unicode
                                overlay.set_status(f"Editing comment: {comment_buffer}")
                                overlay.set_comment_buffer(comment_buffer)
                        continue
                    if event.key == pygame.K_SPACE:
                        debug_mode = False
                        overlay.set_status("Resumed")
                        pygame.display.set_caption(base_caption)
                        editing_comment = False
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
                            if not comment_buffer:
                                comment_buffer = "Snapshot"
                            data = _write_snapshot_to_file(snapshot_slot, snapshot, comment=comment_buffer)
                            history_path = _write_history_snapshot(snapshot_slot, data)
                            snapshot_db.set_slot(snapshot_slot, comment=comment_buffer)
                            snapshot_db.record_history(data, history_path)
                            snapshot_db = SnapshotDatabase()
                            overlay.update_metadata(snapshot_slot, comment_buffer)
                            overlay.clear_preview()
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
                                slot_meta = snapshot_db.get(snapshot_slot)
                                comment_buffer = slot_meta.comment if slot_meta else comment_buffer
                                overlay.update_metadata(snapshot_slot, comment_buffer)
                                overlay.set_status("Snapshot restored (file)")
                                overlay.clear_preview()
                                overlay.capture_state()
                            else:
                                overlay.set_status("No snapshot")
                        continue
                    if event.key == pygame.K_c:
                        if snapshot is None and _read_snapshot_from_file(snapshot_slot) is None:
                            overlay.set_status("No snapshot to comment")
                        else:
                            slot_meta = snapshot_db.get(snapshot_slot)
                            comment_buffer = slot_meta.comment if slot_meta else comment_buffer
                            overlay.set_status(f"Editing comment: {comment_buffer}")
                            overlay.set_comment_buffer(comment_buffer)
                            editing_comment = True
                        continue
                    if event.key in (pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
                        direction = -1 if event.key == pygame.K_LEFTBRACKET else 1
                        entry = overlay.move_history(direction)
                        snapshot_db = SnapshotDatabase()
                        overlay.clear_preview()
                        if entry is not None:
                            overlay.set_status(f"History selected: {entry.slot} {entry.format_timestamp()}")
                        else:
                            overlay.set_status("No history")
                        continue
                    if event.key == pygame.K_p:
                        entry = overlay.current_history_entry()
                        if entry is None:
                            overlay.set_status("No history to preview")
                        else:
                            preview_snapshot = _read_snapshot_path(entry.path)
                            if preview_snapshot is None:
                                overlay.set_status("History snapshot unreadable")
                            else:
                                current_snapshot = _snapshot_current_state(computer)
                                overlay.set_preview_lines(
                                    _make_preview_lines(entry, preview_snapshot, current_snapshot)
                                )
                                overlay.set_status("History preview")
                        continue
                    if event.key == pygame.K_l:
                        entry = overlay.current_history_entry()
                        if entry is None:
                            overlay.set_status("No history to load")
                        else:
                            restored = _read_snapshot_path(entry.path)
                            if restored is None:
                                overlay.set_status("History snapshot unreadable")
                            else:
                                _restore_snapshot(computer, restored)
                                data = _snapshot_to_dict(entry.slot, restored, entry.comment, entry.timestamp)
                                _write_snapshot_to_file(entry.slot, restored, comment=entry.comment, timestamp=entry.timestamp)
                                history_path = _write_history_snapshot(entry.slot, data)
                                snapshot_db.set_slot(entry.slot, comment=entry.comment)
                                snapshot_db.record_history(data, history_path)
                                snapshot_db = SnapshotDatabase()
                                snapshot_slot = entry.slot
                                snapshot = restored
                                comment_buffer = entry.comment
                                overlay.set_slot_name(snapshot_slot)
                                overlay.update_metadata(snapshot_slot, comment_buffer)
                                overlay.set_snapshot_available(True)
                                overlay.clear_preview()
                                overlay.set_status("History snapshot loaded")
                        continue
                    if event.key in (pygame.K_UP, pygame.K_DOWN):
                        direction = -1 if event.key == pygame.K_UP else 1
                        snapshot_slot = overlay.move_selection(direction)
                        snapshot_db = SnapshotDatabase()
                        snapshot = _read_snapshot_from_file(snapshot_slot)
                        overlay.set_snapshot_available(snapshot is not None)
                        slot_meta = snapshot_db.get(snapshot_slot)
                        comment_buffer = slot_meta.comment if slot_meta else ""
                        overlay.update_metadata(snapshot_slot, comment_buffer or "")
                        overlay.set_status(f"Slot switched to {snapshot_slot}")
                        overlay.set_comment_buffer(None)
                        overlay.capture_state()
                        continue
                    if event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                        index = event.key - pygame.K_1
                        if 0 <= index < len(SNAPSHOT_SLOTS):
                            snapshot_slot = SNAPSHOT_SLOTS[index]
                            overlay.set_slot_name(snapshot_slot)
                            snapshot_db = SnapshotDatabase()
                            loaded = _read_snapshot_from_file(snapshot_slot)
                            snapshot = loaded
                            overlay.set_snapshot_available(snapshot is not None)
                            slot_meta = snapshot_db.get(snapshot_slot)
                            comment_buffer = slot_meta.comment if slot_meta else ""
                            overlay.update_metadata(snapshot_slot, comment_buffer or "")
                            overlay.set_status(f"Slot switched to {snapshot_slot}")
                            overlay.set_comment_buffer(None)
                            overlay.capture_state()
                        continue
                    if event.key == pygame.K_d:
                        _delete_snapshot_files(snapshot_slot)
                        snapshot_db.clear_slot(snapshot_slot)
                        snapshot_db = SnapshotDatabase()
                        snapshot = None
                        comment_buffer = ""
                        overlay.set_snapshot_available(False)
                        overlay.set_slot_name(snapshot_slot)
                        overlay.set_status("Snapshot deleted")
                        overlay.set_comment_buffer(None)
                        overlay.capture_state()
                        continue
                else:
                    _handle_key_event(keyboard, event.key, True)
            elif event.type == pygame.KEYUP and not debug_mode and not file_menu.active:
                _handle_key_event(keyboard, event.key, False)

        if loader.pending:
            previous_info = program_info
            try:
                program_info = loader.process()
            except (ProgramLoadError, OSError) as exc:
                program_info = previous_info
                overlay.set_status(f"Load failed: {exc}")
                base_caption = _build_base_caption(program_info)
            else:
                if program_info is not None:
                    base_caption = _build_base_caption(program_info)
                    status = f"Loaded {program_info.name}"
                    if program_info.comment:
                        status = f"{status} ({program_info.comment})"
                    overlay.set_status(status)
                else:
                    base_caption = _build_base_caption(program_info)
                    overlay.set_status("Program cleared")

        surface = display.render_pygame_surface(scale)
        screen.blit(surface, (0, 0))

        if file_menu.active:
            file_menu.render(screen)

        if debug_mode:
            overlay.render(screen)
            pygame.display.flip()
            clock.tick(fps)
            continue

        joy_caption = "off"
        joy_raw = None
        gamepad = getattr(computer, "gamepad", None)
        ext_port = getattr(computer, "ext_port", None)
        if gamepad is not None:
            state = gamepad.current_state()
            active: List[str] = []
            if state.left:
                active.append("L")
            if state.right:
                active.append("R")
            if state.up:
                active.append("U")
            if state.down:
                active.append("D")
            if state.switch:
                active.append("S")
            joy_caption = "".join(active) if active else "-"
        if ext_port is not None and hasattr(ext_port, "get_gamepad_status"):
            joy_raw = ext_port.get_gamepad_status()

        caption = f"{base_caption} | Joy: {joy_caption}"
        if joy_raw is not None:
            caption += f" ({joy_raw:02X})"
        pygame.display.set_caption(caption)

        cycles_per_frame = max(int(computer.get_clock_frequency() / fps), 1000)
        executed = 0
        timeslice = 512
        while executed < cycles_per_frame:
            step = min(timeslice, cycles_per_frame - executed)
            computer.tick(step)
            executed += step
            if computer.cpu_core is not None:
                pc_value = computer.cpu_core.registers.program_counter
                overlay.record_execution(pc_value)
                if trace_pc_vram:
                    if pc_value >= 0xC000:
                        status = computer.cpu_core.status
                        via = getattr(computer, "via", None)
                        if via is not None:
                            ifr = getattr(via, "_state").IFR
                            ier = getattr(via, "_state").IER
                        else:
                            ifr = ier = -1
                        print(
                            f"TRACE-PC pc={pc_value:04X} wai={int(status.fetch_wai)} "
                            f"irq_req={int(status.irq_requested)} IF R={ifr:02X} IER={ier:02X} "
                            f"clock={computer.clock_count}",
                            flush=True,
                        )
                    else:
                        via = getattr(computer, "via", None)
                        if via is not None:
                            state = getattr(via, "_state")
                            if state.IER == 0 and state.IFR != 0:
                                status = computer.cpu_core.status
                                print(
                                    f"TRACE-IFR pc={pc_value:04X} wai={int(status.fetch_wai)} "
                                    f"IFR={state.IFR:02X} clock={computer.clock_count}",
                                    flush=True,
                                )
        if sound_processor is not None:
            sound_processor.pump()
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


def _snapshot_current_state(computer: JR100Computer) -> Optional[Snapshot]:
    return _take_snapshot(computer)


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


def _snapshot_to_dict(slot: str, snapshot: Snapshot, comment: str, timestamp: Optional[float] = None) -> dict:
    return {
        "slot": slot,
        "timestamp": timestamp if timestamp is not None else time.time(),
        "comment": comment,
        "memory": snapshot.memory,
        "cpu_registers": snapshot.cpu_registers,
        "cpu_flags": snapshot.cpu_flags,
        "cpu_status": snapshot.cpu_status,
        "via_state": snapshot.via_state,
        "clock_count": snapshot.clock_count,
    }


def _snapshot_from_dict(data: dict) -> Snapshot:
    return Snapshot(
        memory=list(data.get("memory", [])),
        cpu_registers=dict(data.get("cpu_registers", {})),
        cpu_flags=dict(data.get("cpu_flags", {})),
        cpu_status=dict(data.get("cpu_status", {})),
        via_state=dict(data.get("via_state", {})),
        clock_count=int(data.get("clock_count", 0)),
    )


def _write_snapshot_to_file(slot: str, snapshot: Snapshot, *, comment: str = "", timestamp: Optional[float] = None) -> dict:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    data = _snapshot_to_dict(slot, snapshot, comment, timestamp)
    path = SNAPSHOT_DIR / f"{slot}.json"
    path.write_text(json.dumps(data))
    return data


def _write_history_snapshot(slot: str, data: dict) -> Path:
    SNAPSHOT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = data.get("timestamp", time.time())
    history_path = SNAPSHOT_HISTORY_DIR / f"{slot}-{int(timestamp * 1000)}.json"
    history_path.write_text(json.dumps(data))
    return history_path


def _read_snapshot_from_file(slot: str) -> Optional[Snapshot]:
    path = SNAPSHOT_DIR / f"{slot}.json"
    return _read_snapshot_path(path)


def _read_snapshot_path(path: Path) -> Optional[Snapshot]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return _snapshot_from_dict(data)


def _delete_snapshot_files(slot: str) -> None:
    json_path = SNAPSHOT_DIR / f"{slot}.json"
    meta_path = SNAPSHOT_DIR / f"{slot}.meta.json"
    for path in (json_path, meta_path):
        if path.exists():
            path.unlink()
    if SNAPSHOT_HISTORY_DIR.exists():
        for path in SNAPSHOT_HISTORY_DIR.glob(f"{slot}-*.json"):
            path.unlink()


def _make_preview_lines(entry, snapshot: Snapshot, current: Optional[Snapshot] = None) -> List[str]:
    regs = snapshot.cpu_registers
    pc = int(regs.get("program_counter", 0)) & 0xFFFF
    sp = int(regs.get("stack_pointer", 0)) & 0xFFFF
    ix = int(regs.get("index", 0)) & 0xFFFF
    lines = [
        f"Slot: {entry.slot}",
        f"Time: {entry.format_timestamp()}",
        f"Comment: {entry.comment}",
        f"PC:{pc:04X} SP:{sp:04X} IX:{ix:04X}",
    ]
    flags = snapshot.cpu_flags
    lines.append(
        "FLAGS:" + " ".join(f"{name.upper()}={int(value)}" for name, value in flags.items())
    )
    if current is not None:
        diff_lines = _snapshot_diff_lines(current, snapshot)
        lines.append("Diff:")
        lines.extend(diff_lines)
    return lines


def _snapshot_diff_lines(current: Snapshot, target: Snapshot) -> List[str]:
    diffs: List[str] = []
    reg_specs = [
        ("program_counter", "PC", 4),
        ("stack_pointer", "SP", 4),
        ("index", "IX", 4),
        ("acc_a", "A", 2),
        ("acc_b", "B", 2),
    ]
    for key, label, width in reg_specs:
        curr_val = int(current.cpu_registers.get(key, 0)) & 0xFFFF
        tgt_val = int(target.cpu_registers.get(key, 0)) & 0xFFFF
        if curr_val != tgt_val:
            fmt = f"0{width}X"
            diffs.append(f"  {label}: {format(curr_val, fmt)} -> {format(tgt_val, fmt)}")

    flag_order = ["carry_h", "carry_i", "carry_n", "carry_z", "carry_v", "carry_c"]
    for flag in flag_order:
        curr_flag = bool(current.cpu_flags.get(flag, False))
        tgt_flag = bool(target.cpu_flags.get(flag, False))
        if curr_flag != tgt_flag:
            diffs.append(f"  Flag {flag.upper()}: {int(curr_flag)} -> {int(tgt_flag)}")

    memory_diffs = []
    diff_count = 0
    for addr, (curr_byte, tgt_byte) in enumerate(zip(current.memory, target.memory)):
        if curr_byte != tgt_byte:
            if len(memory_diffs) < 4:
                memory_diffs.append((addr, curr_byte, tgt_byte))
            diff_count += 1
    if diff_count:
        diffs.append(f"  Memory bytes differ: {diff_count}")
        for addr, curr_byte, tgt_byte in memory_diffs:
            diffs.append(f"    {addr:04X}: {curr_byte:02X}->{tgt_byte:02X}")

    if not diffs:
        diffs.append("  (no differences)")
    return diffs


def _write_joystick_template(path: Path) -> None:
    template = {
        "left": ["axis", 0, -0.5],
        "right": ["axis", 0, 0.5],
        "up": ["axis", 1, -0.5],
        "down": ["axis", 1, 0.5],
        "switch": ["button", 0, 0.5],
    }
    path.write_text(json.dumps(template, indent=2), encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="JR-100 emulator demo")
    parser.add_argument(
        "--write-joystick-template",
        metavar="PATH",
        help="Write a JSON joystick mapping template to the given path and exit",
    )
    parser.add_argument("--scale", type=int, default=2, help="Integer scaling factor for display (default: 2)")
    parser.add_argument("--fps", type=int, default=30, help="Target frames per second for the demo loop")
    parser.add_argument(
        "--rom",
        help="Path to the JR-100 BASIC ROM (PROG format). Defaults to datas/jr100rom.prg if omitted",
    )
    parser.add_argument(
        "--audio",
        dest="audio",
        action="store_true",
        help="Enable square-wave audio output (requires pygame mixer)",
    )
    parser.add_argument(
        "--no-audio",
        dest="audio",
        action="store_false",
        help="Force audio output off even if ROM/default settings enable it",
    )
    parser.set_defaults(audio=None)
    parser.add_argument("--joystick", action="store_true", help="Enable pygame joystick input mapping to the JR-100 gamepad port")
    parser.add_argument(
        "--joystick-config",
        help="Path to JSON file that defines axis/button mappings for the gamepad",
    )
    parser.add_argument(
        "--joystick-index",
        type=int,
        default=None,
        help="Select a specific pygame joystick device index when multiple controllers are present",
    )
    parser.add_argument(
        "--joystick-name",
        type=str,
        default=None,
        help="Select joysticks whose OS name contains the given substring",
    )
    parser.add_argument(
        "--joystick-keymap",
        type=str,
        default=None,
        help="Path to JSON file mapping joystick directions to JR-100 keyboard matrix keys",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.write_joystick_template:
        _write_joystick_template(Path(args.write_joystick_template))
        return

    if args.scale <= 0:
        raise SystemExit("scale must be positive")
    if args.fps <= 0:
        raise SystemExit("fps must be positive")

    try:
        _pygame_loop(
            args.scale,
            args.fps,
            rom_path=args.rom,
            enable_audio=args.audio,
            enable_joystick=(
                args.joystick
                or args.joystick_index is not None
                or args.joystick_name is not None
            ),
            joystick_config_path=args.joystick_config,
            joystick_index=args.joystick_index,
            joystick_name=args.joystick_name,
            joystick_keymap_path=args.joystick_keymap,
        )
    except RuntimeError as exc:
        raise SystemExit(str(exc))
if __name__ == "__main__":
    main()
