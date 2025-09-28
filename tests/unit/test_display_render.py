"""Tests for JR100Display rendering."""

from jr100emu.jr100.display import JR100Display


def test_render_pixels_uses_character_rom() -> None:
    display = JR100Display()
    rom = [0x00] * (256 * display.PPC)
    # Character 0: diagonal pattern
    for line in range(display.PPC):
        rom[line] = 1 << (7 - line)
    display.load_character_rom(rom)
    vram = [0] + [0] * (display.WIDTH_CHARS * display.HEIGHT_CHARS - 1)
    display.set_video_ram(vram)

    pixels = display.render_pixels()
    assert pixels[0][0] == display.color_map[1][0]
    assert pixels[display.PPC - 1][display.PPC - 1] == display.color_map[1][0]
    assert pixels[0][display.PPC - 1] == display.color_map[0][0]


def test_user_defined_font_updates_plane1() -> None:
    display = JR100Display()
    rom = [0x00] * (256 * display.PPC)
    display.load_character_rom(rom)
    display.set_current_font(display.FONT_USER_DEFINED)

    display.update_font(0, 0, 0xFF)
    display.set_video_ram([128] + [0] * (display.WIDTH_CHARS * display.HEIGHT_CHARS - 1))

    pixels = display.render_pixels()
    first_row = pixels[0][:display.PPC]
    assert all(color == display.color_map[1][128] for color in first_row)
