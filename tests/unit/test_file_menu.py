"""Unit tests for the pygame-based file menu."""

from __future__ import annotations

from pathlib import Path

import pytest

from jr100emu.frontend.file_menu import FileMenu


@pytest.fixture(autouse=True)
def _force_dummy_video(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")


def _init_pygame():
    pygame = pytest.importorskip("pygame")
    pygame.init()
    return pygame


def test_refresh_lists_supported_entries(tmp_path: Path) -> None:
    (tmp_path / "alpha.bas").write_text("10 REM TEST\n")
    (tmp_path / "beta.prg").write_bytes(b"dummy")
    (tmp_path / "gamma.bin").write_bytes(b"ignored")
    subdir = tmp_path / "subdir"
    subdir.mkdir()

    menu = FileMenu(tmp_path)
    menu.refresh()

    assert subdir in menu.entries
    assert (tmp_path / "alpha.bas") in menu.entries
    assert (tmp_path / "beta.prg") in menu.entries
    assert (tmp_path / "gamma.bin") not in menu.entries


def test_key_enter_returns_load_action(tmp_path: Path) -> None:
    pygame = _init_pygame()
    try:
        target = tmp_path / "hello.bas"
        target.write_text("10 PRINT \"HELLO\"\n")

        menu = FileMenu(tmp_path)
        menu.refresh()
        menu.selected_index = menu.entries.index(target)

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        action = menu.handle_event(event)

        assert action == ("load", target.resolve())
    finally:
        pygame.quit()


def test_select_directory_changes_root(tmp_path: Path) -> None:
    pygame = _init_pygame()
    try:
        child = tmp_path / "folder"
        child.mkdir()
        (child / "demo.bas").write_text("10 END\n")

        menu = FileMenu(tmp_path)
        menu.refresh()
        menu.selected_index = menu.entries.index(child)

        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)
        result = menu.handle_event(event)

        assert result is None
        assert menu.root == child
        assert any(entry.name == "demo.bas" for entry in menu.entries)
    finally:
        pygame.quit()


def test_joystick_button_zero_confirms_selection(tmp_path: Path) -> None:
    pygame = _init_pygame()
    try:
        target = tmp_path / "padtest.bas"
        target.write_text("10 END\n")

        menu = FileMenu(tmp_path)
        menu.refresh()
        menu.selected_index = menu.entries.index(target)

        event = pygame.event.Event(pygame.JOYBUTTONDOWN, button=0)
        action = menu.handle_event(event)

        assert action == ("load", target.resolve())
    finally:
        pygame.quit()


def test_joystick_axis_navigation(tmp_path: Path, monkeypatch) -> None:
    pygame = _init_pygame()
    try:
        for idx in range(6):
            (tmp_path / f"file{idx}.bas").write_text(f"10 REM {idx}\n")

        menu = FileMenu(tmp_path)
        menu.refresh()

        monkeypatch.setattr(pygame.time, "get_ticks", lambda: 1000)
        event = pygame.event.Event(pygame.JOYAXISMOTION, axis=1, value=1.0)
        menu.handle_event(event)
        assert menu.selected_index == 1

        monkeypatch.setattr(pygame.time, "get_ticks", lambda: 1300)
        event = pygame.event.Event(pygame.JOYAXISMOTION, axis=0, value=1.0)
        menu.handle_event(event)
        assert menu.selected_index >= 1
    finally:
        pygame.quit()
