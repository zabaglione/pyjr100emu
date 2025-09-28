"""CLI helper tests."""

from pathlib import Path

from jr100emu.app import _write_joystick_template


def test_write_joystick_template(tmp_path: Path) -> None:
    target = tmp_path / "template.json"
    _write_joystick_template(target)
    data = target.read_text(encoding="utf-8")
    assert "\"left\"" in data
    assert "axis" in data
    assert "button" in data
