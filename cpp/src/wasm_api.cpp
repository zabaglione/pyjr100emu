#include "jr100/core.hpp"

#include <emscripten/emscripten.h>

#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <memory>
#include <optional>
#include <sstream>
#include <span>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

std::unique_ptr<jr100::Core> core;
std::vector<std::uint8_t> input_buffer;
std::vector<std::uint8_t> memory_buffer;
std::string result_buffer;
std::string last_error;

jr100::Core& require_core() {
    if (!core) {
        throw std::runtime_error("ROM is not loaded");
    }
    return *core;
}

std::string json_string(const std::string& value) {
    std::ostringstream out;
    out << '"';
    for (const auto character : value) {
        const auto byte = static_cast<unsigned char>(character);
        switch (character) {
        case '"':
            out << "\\\"";
            break;
        case '\\':
            out << "\\\\";
            break;
        case '\b':
            out << "\\b";
            break;
        case '\f':
            out << "\\f";
            break;
        case '\n':
            out << "\\n";
            break;
        case '\r':
            out << "\\r";
            break;
        case '\t':
            out << "\\t";
            break;
        default:
            if (byte < 0x20) {
                out << "\\u" << std::hex << std::setw(4) << std::setfill('0')
                    << static_cast<int>(byte) << std::dec;
            } else {
                out << character;
            }
        }
    }
    out << '"';
    return out.str();
}

template <typename Value>
void optional_json(std::ostringstream& out, const std::optional<Value>& value) {
    if (value.has_value()) {
        out << *value;
    } else {
        out << "null";
    }
}

std::string flags_string(std::uint8_t flags) {
    std::string result = "------";
    constexpr std::uint8_t masks[] = {0x20, 0x10, 0x08, 0x04, 0x02, 0x01};
    constexpr char names[] = {'H', 'I', 'N', 'Z', 'V', 'C'};
    for (std::size_t index = 0; index < 6; ++index) {
        if ((flags & masks[index]) != 0) {
            result[index] = names[index];
        }
    }
    return result;
}

std::string rom_json(const jr100::RomInfo& info) {
    std::ostringstream out;
    out << "{\"format\":" << json_string(info.format) << ",\"name\":"
        << json_string(info.name) << ",\"startAddress\":" << info.start_address
        << ",\"size\":" << info.size << '}';
    return out.str();
}

std::string program_json(const jr100::ProgramInfo& info) {
    std::ostringstream out;
    out << "{\"name\":" << json_string(info.name) << ",\"comment\":"
        << json_string(info.comment) << ",\"version\":" << info.version
        << ",\"basic\":" << (info.basic ? "true" : "false") << ",\"entryPoint\":";
    optional_json(out, info.entry_point);
    out << ",\"suggestedEntryPoint\":";
    optional_json(out, info.suggested_entry_point);
    out << ",\"entrySource\":" << json_string(info.entry_source)
        << ",\"autostartCommand\":" << json_string(info.autostart_command)
        << ",\"regions\":[";
    for (std::size_t index = 0; index < info.regions.size(); ++index) {
        if (index != 0) {
            out << ',';
        }
        const auto& region = info.regions[index];
        out << "{\"start\":" << region.start << ",\"end\":" << region.end
            << ",\"comment\":" << json_string(region.comment) << '}';
    }
    out << "]}";
    return out.str();
}

std::string state_json(const jr100::MachineState& state) {
    std::ostringstream out;
    out << "{\"clockCount\":" << state.clock_count << ",\"programCounter\":"
        << state.cpu.pc << ",\"runningStatus\":" << state.running_status
        << ",\"joystickMask\":" << static_cast<int>(state.joystick_mask)
        << ",\"graphicsMode\":" << (state.graphics_mode ? "true" : "false")
        << ",\"extendedRam\":" << (state.extended_ram ? "true" : "false")
        << ",\"autotypeActive\":" << (state.autotype_active ? "true" : "false")
        << ",\"breakpointHit\":";
    optional_json(out, state.breakpoint_hit);
    out << '}';
    return out.str();
}

std::string debug_json(const jr100::MachineState& state) {
    const auto& cpu_state = state.cpu;
    const auto& via_state = state.via;
    std::ostringstream out;
    out << "{\"clockCount\":" << state.clock_count << ",\"extendedRam\":"
        << (state.extended_ram ? "true" : "false") << ",\"graphicsMode\":"
        << (state.graphics_mode ? "true" : "false") << ",\"cpu\":{\"a\":"
        << static_cast<int>(cpu_state.a) << ",\"b\":" << static_cast<int>(cpu_state.b)
        << ",\"ix\":" << cpu_state.ix << ",\"sp\":" << cpu_state.sp
        << ",\"pc\":" << cpu_state.pc << ",\"flags\":"
        << json_string(flags_string(cpu_state.flags)) << "},\"via\":{\"ora\":"
        << static_cast<int>(via_state.ora) << ",\"orb\":"
        << static_cast<int>(via_state.orb) << ",\"ddra\":"
        << static_cast<int>(via_state.ddra) << ",\"ddrb\":"
        << static_cast<int>(via_state.ddrb) << ",\"acr\":"
        << static_cast<int>(via_state.acr) << ",\"pcr\":"
        << static_cast<int>(via_state.pcr) << ",\"ifr\":"
        << static_cast<int>(via_state.ifr) << ",\"ier\":"
        << static_cast<int>(via_state.ier) << ",\"t1\":" << via_state.timer1
        << ",\"t2\":" << via_state.timer2 << "}}";
    return out.str();
}

template <typename Action>
int guarded(Action action) {
    try {
        last_error.clear();
        action();
        return 0;
    } catch (const std::exception& error) {
        last_error = error.what();
        return -1;
    }
}

}  // namespace

extern "C" {

EMSCRIPTEN_KEEPALIVE std::uint8_t* jr_input_resize(std::size_t size) {
    input_buffer.resize(size);
    return input_buffer.data();
}

EMSCRIPTEN_KEEPALIVE int jr_create_core(std::size_t size, int extended_ram) {
    return guarded([&] {
        if (size != input_buffer.size()) {
            throw std::runtime_error("ROM input size does not match the transfer buffer");
        }
        core = std::make_unique<jr100::Core>(input_buffer, extended_ram != 0);
        result_buffer = rom_json(core->rom_info());
    });
}

EMSCRIPTEN_KEEPALIVE const char* jr_last_error() {
    return last_error.c_str();
}

EMSCRIPTEN_KEEPALIVE const char* jr_result_json() {
    return result_buffer.c_str();
}

EMSCRIPTEN_KEEPALIVE int jr_reset() {
    return guarded([] { require_core().reset(); });
}

EMSCRIPTEN_KEEPALIVE int jr_run_frame(int cycles) {
    return guarded([&] { require_core().run_frame(cycles); });
}

EMSCRIPTEN_KEEPALIVE int jr_set_key(int row, int bit, int pressed) {
    return guarded([&] { require_core().set_key(row, bit, pressed != 0); });
}

EMSCRIPTEN_KEEPALIVE int jr_clear_keys() {
    return guarded([] { require_core().clear_keys(); });
}

EMSCRIPTEN_KEEPALIVE int jr_set_joystick(int mask) {
    return guarded([&] { require_core().set_joystick_mask(static_cast<std::uint8_t>(mask)); });
}

EMSCRIPTEN_KEEPALIVE const std::uint8_t* jr_frame_data() {
    return require_core().frame_buffer().data();
}

EMSCRIPTEN_KEEPALIVE std::size_t jr_frame_size() {
    return require_core().frame_buffer().size();
}

EMSCRIPTEN_KEEPALIVE const std::int16_t* jr_audio_data() {
    return require_core().audio_buffer().data();
}

EMSCRIPTEN_KEEPALIVE std::size_t jr_audio_size() {
    return require_core().audio_buffer().size();
}

EMSCRIPTEN_KEEPALIVE int jr_clear_audio() {
    return guarded([] { require_core().clear_audio_buffer(); });
}

EMSCRIPTEN_KEEPALIVE const std::uint8_t* jr_font_data() {
    return require_core().font_data().data();
}

EMSCRIPTEN_KEEPALIVE std::size_t jr_font_size() {
    return require_core().font_data().size();
}

EMSCRIPTEN_KEEPALIVE const std::uint8_t* jr_normal_codes() {
    return require_core().normal_key_codes().data();
}

EMSCRIPTEN_KEEPALIVE const std::uint8_t* jr_shift_codes() {
    return require_core().shift_key_codes().data();
}

EMSCRIPTEN_KEEPALIVE std::size_t jr_key_code_size() {
    return require_core().normal_key_codes().size();
}

EMSCRIPTEN_KEEPALIVE int jr_load_program(std::size_t size, const char* filename) {
    return guarded([&] {
        if (size != input_buffer.size()) {
            throw std::runtime_error("program input size does not match the transfer buffer");
        }
        const auto info = require_core().load_program(input_buffer, filename == nullptr ? "" : filename);
        result_buffer = program_json(info);
    });
}

EMSCRIPTEN_KEEPALIVE int jr_run_entry(std::uint16_t address) {
    return guarded([&] { result_buffer = require_core().run_entry(address); });
}

EMSCRIPTEN_KEEPALIVE const char* jr_state_json() {
    result_buffer = state_json(require_core().state());
    return result_buffer.c_str();
}

EMSCRIPTEN_KEEPALIVE const char* jr_debug_json() {
    result_buffer = debug_json(require_core().state());
    return result_buffer.c_str();
}

EMSCRIPTEN_KEEPALIVE const std::uint8_t* jr_read_memory(std::uint16_t start,
                                                        std::size_t length) {
    try {
        last_error.clear();
        memory_buffer = require_core().read_memory(start, length);
        return memory_buffer.data();
    } catch (const std::exception& error) {
        last_error = error.what();
        memory_buffer.clear();
        return nullptr;
    }
}

EMSCRIPTEN_KEEPALIVE std::size_t jr_read_memory_size() {
    return memory_buffer.size();
}

EMSCRIPTEN_KEEPALIVE int jr_set_breakpoints(std::size_t count) {
    return guarded([&] {
        if (input_buffer.size() != count * 2) {
            throw std::runtime_error("breakpoint input size does not match the transfer buffer");
        }
        std::vector<std::uint16_t> addresses;
        addresses.reserve(count);
        for (std::size_t index = 0; index < count; ++index) {
            addresses.push_back(static_cast<std::uint16_t>(
                input_buffer[index * 2] | (input_buffer[index * 2 + 1] << 8U)));
        }
        require_core().set_breakpoints(addresses);
    });
}

EMSCRIPTEN_KEEPALIVE int jr_continue() {
    return guarded([] { require_core().continue_execution(); });
}

EMSCRIPTEN_KEEPALIVE int jr_step() {
    return guarded([] { require_core().step_instruction(); });
}

}  // extern "C"
