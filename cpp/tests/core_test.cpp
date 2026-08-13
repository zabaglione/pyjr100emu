#include "jr100/core.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string_view>
#include <vector>

namespace {

void require(bool condition, std::string_view message) {
    if (!condition) {
        throw std::runtime_error(std::string(message));
    }
}

std::vector<std::uint8_t> synthetic_rom() {
    std::vector<std::uint8_t> rom(0x2000, 0);
    rom[0x0400] = 0x20;
    rom[0x0401] = 0xfe;
    const std::array<std::uint8_t, 43> normal = {
        0x5a, 0x58, 0x43, 0x41, 0x53, 0x44, 0x46, 0x47, 0x51, 0x57, 0x45,
        0x52, 0x54, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39,
        0x30, 0x59, 0x55, 0x49, 0x4f, 0x50, 0x48, 0x4a, 0x4b, 0x4c, 0x3b,
        0x56, 0x42, 0x4e, 0x4d, 0x2c, 0x2e, 0x20, 0x3a, 0x0d, 0x2d,
    };
    const std::array<std::uint8_t, 43> shifted = {
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29,
        0x5e, 0x00, 0x40, 0x5c, 0x5b, 0x5d, 0x00, 0x00, 0x3f, 0x2f, 0x2b,
        0x00, 0x00, 0x00, 0x5f, 0x3c, 0x3e, 0x20, 0x2a, 0x0d, 0x3d,
    };
    std::copy(normal.begin(), normal.end(), rom.begin() + 0x1a6c);
    std::copy(shifted.begin(), shifted.end(), rom.begin() + 0x1a99);
    rom[0x1ffe] = 0xe4;
    rom[0x1fff] = 0x00;
    return rom;
}

std::vector<std::uint8_t> sound_rom() {
    auto rom = synthetic_rom();
    const std::array<std::uint8_t, 30> program = {
        0x8e, 0x3f, 0xff,        // LDS #$3fff
        0x86, 0xc0,              // LDAA #$c0
        0xb7, 0xc8, 0x0b,        // STAA $c80b
        0x86, 0xaa,              // LDAA #$aa
        0xb7, 0xc8, 0x04,        // STAA $c804
        0x4f,                    // CLRA
        0xb7, 0xc8, 0x05,        // STAA $c805
        0xce, 0x10, 0x00,        // LDX #$1000
        0x09,                    // DEX
        0x26, 0xfd,              // BNE DEX
        0x4f,                    // CLRA
        0xb7, 0xc8, 0x0b,        // STAA $c80b
        0xb7, 0xc8, 0x05,        // STAA $c805
    };
    std::copy(program.begin(), program.end(), rom.begin() + 0x0400);
    rom[0x0400 + program.size()] = 0x20;
    rom[0x0401 + program.size()] = 0xfe;
    return rom;
}

std::vector<std::uint8_t> level_irq_rom() {
    auto rom = synthetic_rom();
    const std::array<std::uint8_t, 29> program = {
        0x8e, 0x3f, 0xff,        // LDS #$3fff
        0x4f,                    // CLRA
        0xb7, 0x00, 0x00,        // STAA $0000
        0x4f,                    // CLRA
        0xb7, 0xc8, 0x0b,        // STAA $c80b
        0x86, 0xff,              // LDAA #$ff
        0xb7, 0xc8, 0x04,        // STAA $c804
        0x4f,                    // CLRA
        0xb7, 0xc8, 0x05,        // STAA $c805
        0x86, 0xc0,              // LDAA #$c0
        0xb7, 0xc8, 0x0e,        // STAA $c80e
        0x0e,                    // CLI
        0x3e,                    // WAI
        0x20, 0xfe,              // BRA *
    };
    const std::array<std::uint8_t, 14> interrupt = {
        0x7c, 0x00, 0x00,        // INC $0000
        0xb6, 0x00, 0x00,        // LDAA $0000
        0x81, 0x03,              // CMPA #$03
        0x26, 0x03,              // BNE RTI
        0xb6, 0xc8, 0x04,        // LDAA $c804
        0x3b,                    // RTI
    };
    std::copy(program.begin(), program.end(), rom.begin() + 0x0400);
    std::copy(interrupt.begin(), interrupt.end(), rom.begin() + 0x0440);
    rom[0x1ff8] = 0xe4;
    rom[0x1ff9] = 0x40;
    return rom;
}

void test_invalid_rom_is_rejected() {
    bool rejected = false;
    try {
        const std::array<std::uint8_t, 3> invalid = {1, 2, 3};
        jr100::Core core(invalid);
    } catch (const std::invalid_argument&) {
        rejected = true;
    }
    require(rejected, "invalid ROM must be rejected");
}

void test_core_exposes_browser_seam() {
    const auto rom = synthetic_rom();
    jr100::Core core(rom, true);

    require(core.rom_info().format == "raw", "raw ROM format must be reported");
    require(core.rom_info().size == 0x2000, "ROM payload size must be reported");
    require(core.font_data().size() == 1024, "font data must contain 128 glyphs");
    require(core.normal_key_codes().front() == 0x5a, "normal key table must come from ROM");
    require(core.shift_key_codes()[13] == 0x21, "shift key table must come from ROM");

    core.set_joystick_mask(0xff);
    core.run_frame(32);
    core.run_frame(32);
    const auto state = core.state();
    require(state.extended_ram, "extended RAM state must be visible");
    require(state.joystick_mask == 0x1f, "joystick mask must be limited to five bits");
    require(core.read_memory(0xcc02, 1).front() == 0x1f,
            "joystick state must be readable through the extended I/O port");
    require(state.clock_count >= 32, "frame execution must advance the CPU clock");
    require(core.frame_buffer().size() == 256 * 192, "frame size must match JR-100 video");
}

void test_timestamped_sound_is_one_short_segment() {
    const auto rom = sound_rom();
    jr100::Core core(rom);
    core.run_frame();
    for (int frame = 0; frame < 5; ++frame) {
        core.run_frame();
    }

    const auto audio = core.audio_buffer();
    require(audio.size() > 2'000, "sound core must render a continuous PCM timeline");
    std::size_t first = audio.size();
    std::size_t last = 0;
    std::size_t longest_internal_silence = 0;
    std::size_t silence = 0;
    for (std::size_t index = 0; index < audio.size(); ++index) {
        const bool nonzero = audio[index] != 0;
        if (nonzero) {
            first = std::min(first, index);
            last = index;
            longest_internal_silence = std::max(longest_internal_silence, silence);
            silence = 0;
        } else if (first != audio.size()) {
            ++silence;
        }
    }
    require(first != audio.size(), "VIA gate interval must contain audible PCM");
    require(longest_internal_silence < 64,
            "one VIA gate interval must not be retriggered as separate bursts");
    const auto duration = static_cast<double>(last - first + 1) / jr100::Core::sample_rate;
    require(duration > 0.030 && duration < 0.045, "VIA gate duration must stay short");
}

void test_via_irq_remains_asserted_until_ifr_is_cleared() {
    const auto rom = level_irq_rom();
    jr100::Core core(rom);
    for (int frame = 0; frame < 5; ++frame) {
        core.run_frame();
    }

    require(core.read_memory(0x0000, 1).front() == 3,
            "a level IRQ must re-enter the handler while T1 IFR remains set");
    require((core.state().via.ifr & 0xc0) == 0,
            "reading T1CL must clear both the T1 flag and the IRQ level");
}

void append_u32(std::vector<std::uint8_t>& data, std::uint32_t value) {
    for (int shift = 0; shift < 32; shift += 8) {
        data.push_back(static_cast<std::uint8_t>(value >> shift));
    }
}

void test_basic_and_prog_loaders_use_core_memory() {
    const auto rom = synthetic_rom();
    jr100::Core core(rom, true);
    const std::string basic = "10 print a\n20 data \\1b\\7f\n";
    const auto basic_bytes = std::span(
        reinterpret_cast<const std::uint8_t*>(basic.data()), basic.size());
    const auto basic_info = core.load_program(basic_bytes, "demo.bas");
    require(basic_info.basic, "BASIC text must be marked as BASIC");
    require(basic_info.name == "DEMO", "BASIC name must come from the file stem");
    require(basic_info.autostart_command == "RUN", "BASIC must queue RUN autostart");
    const auto basic_memory = core.read_memory(0x0246, 24);
    require(basic_memory[0] == 0x00 && basic_memory[1] == 0x0a,
            "BASIC line number must use big-endian JR-100 memory order");
    require(std::equal(basic_memory.begin() + 2, basic_memory.begin() + 9, "PRINT A"),
            "BASIC source must be canonicalized to uppercase");

    std::vector<std::uint8_t> prog{'P', 'R', 'O', 'G'};
    append_u32(prog, 1);
    append_u32(prog, 4);
    prog.insert(prog.end(), {'T', 'E', 'S', 'T'});
    append_u32(prog, 0x2000);
    append_u32(prog, 3);
    append_u32(prog, 1);
    prog.insert(prog.end(), {0x86, 0x42, 0x39});
    const auto binary_info = core.load_program(prog, "ignored.prg");
    require(binary_info.name == "TEST", "PROG v1 name must be decoded");
    require(binary_info.entry_point == 0x2000, "PROG v1 start must be the entry point");
    require(binary_info.autostart_command == "A=USR($2000)",
            "binary PROG must queue its USR command");
    require(core.read_memory(0x2000, 3) == std::vector<std::uint8_t>({0x86, 0x42, 0x39}),
            "PROG payload must be written into emulated RAM");
}

}  // namespace

int main() {
    try {
        test_invalid_rom_is_rejected();
        test_core_exposes_browser_seam();
        test_timestamped_sound_is_one_short_segment();
        test_via_irq_remains_asserted_until_ifr_is_cleared();
        test_basic_and_prog_loaders_use_core_memory();
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    std::cout << "jr100 core tests passed\n";
    return 0;
}
