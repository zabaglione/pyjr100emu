"""pygame dependent tests for JR100Display."""

import pytest

pygame = pytest.importorskip("pygame")

from jr100emu.jr100.display import JR100Display


def test_render_pygame_surface_scaling_two():
    display = JR100Display()
    display.set_color_map_entry(display.FONT_NORMAL, 0, 0x123456)
    display.set_video_ram([0x00] + [0x80] * (display.WIDTH_CHARS * display.HEIGHT_CHARS - 1))

    surface = display.render_pygame_surface(scaling=2)

    assert surface.get_width() == display.WIDTH_CHARS * display.PPC * 2
    assert surface.get_height() == display.HEIGHT_CHARS * display.PPC * 2

    top_left = surface.get_at((0, 0))
    assert tuple(top_left)[:3] == (0x12, 0x34, 0x56)
