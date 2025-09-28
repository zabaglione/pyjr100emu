"""CLI helper tests."""

from pathlib import Path

import sys

import pytest

from jr100emu.app import _write_joystick_template
from jr100emu.tools import joystick_monitor


def test_write_joystick_template(tmp_path: Path) -> None:
    target = tmp_path / "template.json"
    _write_joystick_template(target)
    data = target.read_text(encoding="utf-8")
    assert "\"left\"" in data
    assert "axis" in data
    assert "button" in data


def test_monitor_without_pygame(monkeypatch):
    monkeypatch.delitem(sys.modules, "pygame", raising=False)
    exit_code = joystick_monitor.monitor()
    assert exit_code == 1
