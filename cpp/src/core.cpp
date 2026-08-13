#include "core_internal.hpp"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstring>
#include <memory>
#include <regex>
#include <stdexcept>
#include <utility>

namespace jr100::detail {
namespace {

constexpr std::uint32_t read_u32_le(std::span<const std::uint8_t> data, std::size_t offset) {
    if (offset + 4 > data.size()) {
        throw std::invalid_argument("truncated 32-bit field");
    }
    return static_cast<std::uint32_t>(data[offset]) |
           (static_cast<std::uint32_t>(data[offset + 1]) << 8U) |
           (static_cast<std::uint32_t>(data[offset + 2]) << 16U) |
           (static_cast<std::uint32_t>(data[offset + 3]) << 24U);
}

std::string ascii_string(std::span<const std::uint8_t> data) {
    std::string result;
    result.reserve(data.size());
    for (const auto value : data) {
        result.push_back(value < 0x80 ? static_cast<char>(value) : '?');
    }
    return result;
}

bool has_extension(const std::string& filename, const std::string& extension) {
    if (filename.size() < extension.size()) {
        return false;
    }
    const auto start = filename.size() - extension.size();
    for (std::size_t index = 0; index < extension.size(); ++index) {
        const auto left = static_cast<unsigned char>(filename[start + index]);
        const auto right = static_cast<unsigned char>(extension[index]);
        if (std::tolower(left) != std::tolower(right)) {
            return false;
        }
    }
    return true;
}

std::string file_stem_upper(const std::string& filename) {
    const auto slash = filename.find_last_of("/\\");
    const auto start = slash == std::string::npos ? 0 : slash + 1;
    auto end = filename.find_last_of('.');
    if (end == std::string::npos || end < start) {
        end = filename.size();
    }
    auto stem = filename.substr(start, end - start);
    std::transform(stem.begin(), stem.end(), stem.begin(), [](unsigned char value) {
        return static_cast<char>(std::toupper(value));
    });
    return stem;
}

std::string trim(const std::string& value) {
    const auto first = std::find_if_not(value.begin(), value.end(), [](unsigned char character) {
        return std::isspace(character) != 0;
    });
    const auto last = std::find_if_not(value.rbegin(), value.rend(), [](unsigned char character) {
        return std::isspace(character) != 0;
    }).base();
    if (first >= last) {
        return {};
    }
    return std::string(first, last);
}

std::optional<std::uint16_t> entry_from_comment(const std::string& comment) {
    static const std::regex pattern(
        R"((^|\s)(entry|usr)\s*=\s*(\$|0x)([0-9a-f]{1,4})(\s|$))",
        std::regex_constants::icase);
    std::smatch match;
    if (!std::regex_search(comment, match, pattern)) {
        return std::nullopt;
    }
    return static_cast<std::uint16_t>(std::stoul(match[4].str(), nullptr, 16));
}

}  // namespace

Emulator::Emulator(std::span<const std::uint8_t> rom, bool extended_ram)
    : extended_ram_(extended_ram), cpu_(*this), via_(*this) {
    decode_rom(rom);
    reset();
}

void Emulator::decode_rom(std::span<const std::uint8_t> rom) {
    if (rom.size() == basic_rom_length) {
        std::copy(rom.begin(), rom.end(), rom_.begin());
        rom_info_ = RomInfo{"raw", "", basic_rom_start, basic_rom_length};
        return;
    }
    if (rom.size() < 32 || !std::equal(rom.begin(), rom.begin() + 4, "PROG")) {
        throw std::invalid_argument("ROM must be 8192 bytes raw or a valid PROG container");
    }
    const auto version = read_u32_le(rom, 4);
    if (version != 1) {
        throw std::invalid_argument("ROM PROG container must use version 1");
    }
    const auto name_length = static_cast<std::size_t>(read_u32_le(rom, 8));
    const auto name_start = std::size_t{12};
    const auto name_end = name_start + name_length;
    if (name_end + 12 > rom.size()) {
        throw std::invalid_argument("PROG ROM metadata is truncated");
    }
    const auto start = read_u32_le(rom, name_end);
    const auto length = read_u32_le(rom, name_end + 4);
    const auto flag = read_u32_le(rom, name_end + 8);
    const auto payload_start = name_end + 12;
    if (start != basic_rom_start || length != basic_rom_length || flag == 0 ||
        payload_start + length != rom.size()) {
        throw std::invalid_argument("PROG ROM does not contain one complete JR-100 ROM image");
    }
    std::copy(rom.begin() + static_cast<std::ptrdiff_t>(payload_start), rom.end(), rom_.begin());
    rom_info_ = RomInfo{
        "prog-v1",
        ascii_string(rom.subspan(name_start, name_length)),
        basic_rom_start,
        basic_rom_length,
    };
}

std::uint8_t Emulator::load8(std::uint16_t address) const {
    if (address >= via_start && address <= via_start + 0x0f) {
        return const_cast<Via&>(via_).load8(address);
    }
    if (address >= 0xcc00 && address <= 0xcfff) {
        return address == 0xcc02 ? joystick_mask_ : 0;
    }
    if (address >= basic_rom_start) {
        return rom_[address - basic_rom_start];
    }
    const bool main_ram = address < 0x4000 || (extended_ram_ && address < 0x8000);
    const bool character_ram = address >= 0xc000 && address <= 0xc0ff;
    const bool video_ram = address >= 0xc100 && address <= 0xc3ff;
    if (main_ram || character_ram || video_ram) {
        return memory_[address];
    }
    return address == 0xd000 ? 0xaa : 0;
}

std::uint16_t Emulator::load16(std::uint16_t address) const {
    const auto high = static_cast<std::uint16_t>(load8(address));
    const auto low = static_cast<std::uint16_t>(load8(static_cast<std::uint16_t>(address + 1)));
    return static_cast<std::uint16_t>((high << 8U) | low);
}

void Emulator::store8(std::uint16_t address, std::uint8_t value) {
    if (address >= via_start && address <= via_start + 0x0f) {
        via_.store8(address, value);
        return;
    }
    if (address >= 0xcc00 && address <= 0xcfff) {
        if (address == 0xcc02) {
            joystick_mask_ = value;
        }
        return;
    }
    const bool main_ram = address < 0x4000 || (extended_ram_ && address < 0x8000);
    const bool character_ram = address >= 0xc000 && address <= 0xc0ff;
    const bool video_ram = address >= 0xc100 && address <= 0xc3ff;
    if (main_ram || character_ram || video_ram) {
        memory_[address] = value;
    }
}

void Emulator::store16(std::uint16_t address, std::uint16_t value) {
    store8(address, static_cast<std::uint8_t>(value >> 8U));
    store8(static_cast<std::uint16_t>(address + 1), static_cast<std::uint8_t>(value));
}

void Emulator::reset() {
    release_autotype_cells();
    autotype_queue_.clear();
    autotype_frames_remaining_ = 0;
    breakpoint_hit_.reset();
    clock_count_ = 0;
    cpu_.reset();
    via_.reset();
    sound_.reset();
}

void Emulator::tick(int cycles) {
    if (cycles <= 0) {
        return;
    }
    cpu_.execute(cycles);
    via_.execute(clock_count_);
    sound_.execute(clock_count_);
}

void Emulator::run_frame(int cycles) {
    advance_autotype();
    if (cycles <= 0 || breakpoint_hit_.has_value()) {
        return;
    }
    if (breakpoints_.empty()) {
        tick(cycles);
        return;
    }
    const auto target = clock_count_ + cycles;
    while (clock_count_ < target) {
        const auto pc = cpu_.registers().pc;
        if (breakpoints_.contains(pc)) {
            if (skip_breakpoint_once_ == pc) {
                skip_breakpoint_once_.reset();
            } else {
                breakpoint_hit_ = pc;
                return;
            }
        }
        const auto before = clock_count_;
        tick(1);
        if (clock_count_ == before) {
            tick(1);
        }
    }
}

void Emulator::set_key(int row, int bit, bool pressed) {
    if (row < 0 || row >= static_cast<int>(keyboard_.size()) || bit < 0 || bit >= 5) {
        throw std::out_of_range("keyboard row or bit is out of range");
    }
    const auto mask = static_cast<std::uint8_t>(1U << static_cast<unsigned>(bit));
    if (pressed) {
        keyboard_[static_cast<std::size_t>(row)] |= mask;
    } else {
        keyboard_[static_cast<std::size_t>(row)] &= static_cast<std::uint8_t>(~mask);
    }
    keyboard_[static_cast<std::size_t>(row)] &= 0x1f;
}

void Emulator::clear_keys() {
    keyboard_.fill(0);
}

void Emulator::set_joystick_mask(std::uint8_t mask) {
    joystick_mask_ = mask & 0x1f;
}

std::span<const std::uint8_t> Emulator::frame_buffer() {
    render_frame();
    return frame_;
}

void Emulator::render_frame() {
    for (int y_character = 0; y_character < 24; ++y_character) {
        for (int x_character = 0; x_character < 32; ++x_character) {
            const auto code = memory_[0xc100 + y_character * 32 + x_character];
            for (int line = 0; line < 8; ++line) {
                std::uint8_t glyph = 0;
                if (!user_font_ || code < 128) {
                    glyph = rom_[(code & 0x7f) * 8 + line];
                    if (!user_font_ && code >= 128) {
                        glyph ^= 0xff;
                    }
                } else {
                    glyph = memory_[0xc000 + (code - 128) * 8 + line];
                }
                const auto row = (y_character * 8 + line) * Core::frame_width;
                const auto cell = row + x_character * 8;
                for (int bit = 0; bit < 8; ++bit) {
                    frame_[static_cast<std::size_t>(cell + bit)] =
                        static_cast<std::uint8_t>((glyph >> (7 - bit)) & 1U);
                }
            }
        }
    }
}

std::vector<std::uint8_t> Emulator::read_memory(std::uint16_t start,
                                                std::size_t length) const {
    if (length > 0x10000) {
        throw std::out_of_range("memory length is out of range");
    }
    std::vector<std::uint8_t> result;
    result.reserve(length);
    for (std::size_t offset = 0; offset < length; ++offset) {
        result.push_back(load8(static_cast<std::uint16_t>(start + offset)));
    }
    return result;
}

ProgramInfo Emulator::load_program(std::span<const std::uint8_t> data,
                                   const std::string& filename) {
    constexpr std::uint16_t basic_start = 0x0246;
    constexpr std::size_t max_basic_line = 72;

    const auto finalize_basic = [this](std::uint16_t last_data_address) {
        constexpr std::uint16_t start = 0x0246;
        constexpr std::uint16_t pointer_base = 0x0006;
        const auto after_zero = static_cast<std::uint16_t>(last_data_address + 1);
        for (int offset = 0; offset < 3; ++offset) {
            store8(static_cast<std::uint16_t>(after_zero + offset), 0xdf);
        }
        store8(pointer_base - 2, static_cast<std::uint8_t>(start >> 8U));
        store8(pointer_base - 1, static_cast<std::uint8_t>(start));
        auto pointer = static_cast<std::uint16_t>(after_zero + 1);
        for (int index = 0; index < 4; ++index) {
            const auto address = static_cast<std::uint16_t>(pointer_base + index * 2);
            store8(address, static_cast<std::uint8_t>(pointer >> 8U));
            store8(static_cast<std::uint16_t>(address + 1), static_cast<std::uint8_t>(pointer));
            pointer = static_cast<std::uint16_t>(pointer + 1);
        }
    };
    const auto write_block = [this](std::uint32_t start, std::span<const std::uint8_t> block) {
        if (start + block.size() > 0x10000U) {
            throw std::runtime_error("program exceeds PROG limits");
        }
        for (std::size_t index = 0; index < block.size(); ++index) {
            store8(static_cast<std::uint16_t>(start + index), block[index]);
        }
    };

    ProgramInfo info;
    if (has_extension(filename, ".bas") || has_extension(filename, ".txt")) {
        info.name = file_stem_upper(filename);
        info.basic = true;
        std::uint32_t address = basic_start;
        const auto source = std::string(reinterpret_cast<const char*>(data.data()), data.size());
        std::size_t line_start = 0;
        while (line_start <= source.size()) {
            const auto newline = source.find('\n', line_start);
            const auto line_end = newline == std::string::npos ? source.size() : newline;
            auto line = source.substr(line_start, line_end - line_start);
            if (!line.empty() && line.back() == '\r') {
                line.pop_back();
            }
            line = trim(line);
            std::transform(line.begin(), line.end(), line.begin(), [](unsigned char value) {
                return static_cast<char>(std::toupper(value));
            });
            if (!line.empty()) {
                std::size_t digit_end = 0;
                while (digit_end < line.size() &&
                       std::isdigit(static_cast<unsigned char>(line[digit_end])) != 0) {
                    ++digit_end;
                }
                if (digit_end == 0) {
                    throw std::runtime_error("BASIC line number is missing");
                }
                const auto line_number = std::stoul(line.substr(0, digit_end));
                if (line_number < 1 || line_number > 32767) {
                    throw std::runtime_error("BASIC line number is out of range");
                }
                auto content = trim(line.substr(digit_end));
                std::vector<std::uint8_t> encoded;
                encoded.reserve(content.size());
                for (std::size_t index = 0; index < content.size();) {
                    if (content[index] != '\\') {
                        encoded.push_back(static_cast<std::uint8_t>(content[index]));
                        ++index;
                        continue;
                    }
                    if (index + 2 >= content.size() ||
                        std::isxdigit(static_cast<unsigned char>(content[index + 1])) == 0 ||
                        std::isxdigit(static_cast<unsigned char>(content[index + 2])) == 0) {
                        throw std::runtime_error("invalid BASIC hexadecimal escape");
                    }
                    encoded.push_back(static_cast<std::uint8_t>(
                        std::stoul(content.substr(index + 1, 2), nullptr, 16)));
                    index += 3;
                }
                if (encoded.size() + 2 > max_basic_line || address + encoded.size() + 2 > 0x7fff) {
                    throw std::runtime_error("BASIC line does not fit in memory");
                }
                store16(static_cast<std::uint16_t>(address),
                        static_cast<std::uint16_t>(line_number));
                address += 2;
                for (const auto byte : encoded) {
                    store8(static_cast<std::uint16_t>(address++), byte);
                }
                store8(static_cast<std::uint16_t>(address++), 0);
            }
            if (newline == std::string::npos) {
                break;
            }
            line_start = newline + 1;
        }
        const auto last = static_cast<std::uint16_t>(address - 1);
        if (address + 3 > 0x7fff) {
            throw std::runtime_error("BASIC program does not fit in memory");
        }
        finalize_basic(last);
        info.regions.push_back({basic_start, last, ""});
        info.autostart_command = "RUN";
        queue_autotype(info.autostart_command + '\r');
        return info;
    }

    if (data.size() < 8 || !std::equal(data.begin(), data.begin() + 4, "PROG")) {
        throw std::runtime_error("invalid PROG magic");
    }
    const auto version = read_u32_le(data, 4);
    if (version < 1 || version > 2) {
        throw std::runtime_error("unsupported PROG version");
    }
    info.version = static_cast<int>(version);
    if (version == 1) {
        auto offset = std::size_t{8};
        const auto name_length = static_cast<std::size_t>(read_u32_le(data, offset));
        offset += 4;
        if (name_length > 256 || offset + name_length + 12 > data.size()) {
            throw std::runtime_error("invalid PROG v1 metadata");
        }
        info.name.assign(reinterpret_cast<const char*>(data.data() + offset), name_length);
        offset += name_length;
        const auto start = read_u32_le(data, offset);
        const auto length = static_cast<std::size_t>(read_u32_le(data, offset + 4));
        const auto flag = read_u32_le(data, offset + 8);
        offset += 12;
        if (start + length > 0x10000U || offset + length != data.size()) {
            throw std::runtime_error("invalid PROG v1 payload");
        }
        write_block(start, data.subspan(offset, length));
        if (flag == 0) {
            const auto last = static_cast<std::uint16_t>(
                length == 0 ? basic_start - 1 : start + length - 1);
            finalize_basic(last);
            info.basic = true;
            info.regions.push_back({basic_start, last, ""});
        } else {
            const auto end = static_cast<std::uint16_t>(length == 0 ? start : start + length - 1);
            info.regions.push_back({static_cast<std::uint16_t>(start), end, ""});
            info.entry_point = static_cast<std::uint16_t>(start);
            info.entry_source = "v1-start";
        }
    } else {
        constexpr std::uint32_t section_pnam = 0x4d414e50;
        constexpr std::uint32_t section_pbas = 0x53414250;
        constexpr std::uint32_t section_pbin = 0x4e494250;
        constexpr std::uint32_t section_cmnt = 0x544e4d43;
        std::size_t offset = 8;
        bool seen_name = false;
        bool seen_basic = false;
        bool seen_comment = false;
        int binary_count = 0;
        std::optional<std::uint16_t> first_binary;
        while (offset < data.size()) {
            if (data.size() - offset < 8) {
                const bool all_zero = std::all_of(data.begin() + static_cast<std::ptrdiff_t>(offset),
                                                  data.end(),
                                                  [](std::uint8_t byte) { return byte == 0; });
                if (all_zero) {
                    break;
                }
                throw std::runtime_error("truncated PROG v2 section header");
            }
            const auto section = read_u32_le(data, offset);
            const auto length = static_cast<std::size_t>(read_u32_le(data, offset + 4));
            offset += 8;
            if (offset + length > data.size()) {
                throw std::runtime_error("truncated PROG v2 section");
            }
            const auto payload = data.subspan(offset, length);
            offset += length;
            if (section == section_pnam && !seen_name) {
                seen_name = true;
                if (payload.size() < 4) {
                    throw std::runtime_error("invalid PNAM section");
                }
                const auto size = static_cast<std::size_t>(read_u32_le(payload, 0));
                if (size > 256 || 4 + size > payload.size()) {
                    throw std::runtime_error("invalid PNAM section length");
                }
                info.name.assign(reinterpret_cast<const char*>(payload.data() + 4), size);
            } else if (section == section_pbas && !seen_basic) {
                seen_basic = true;
                if (payload.size() < 4) {
                    throw std::runtime_error("invalid PBAS section");
                }
                const auto size = static_cast<std::size_t>(read_u32_le(payload, 0));
                if (size + 4 != payload.size() || size > 0x10000) {
                    throw std::runtime_error("invalid PBAS section length");
                }
                write_block(basic_start, payload.subspan(4, size));
                const auto last = static_cast<std::uint16_t>(
                    size == 0 ? basic_start - 1 : basic_start + size - 1);
                finalize_basic(last);
                info.basic = true;
                info.regions.push_back({basic_start, last, ""});
            } else if (section == section_pbin && binary_count < 256) {
                ++binary_count;
                if (payload.size() < 8) {
                    throw std::runtime_error("invalid PBIN section");
                }
                const auto start = read_u32_le(payload, 0);
                const auto size = static_cast<std::size_t>(read_u32_le(payload, 4));
                if (start + size > 0x10000U || 8 + size > payload.size()) {
                    throw std::runtime_error("invalid PBIN payload");
                }
                std::string comment;
                const auto comment_offset = 8 + size;
                if (comment_offset < payload.size()) {
                    if (payload.size() - comment_offset < 4) {
                        throw std::runtime_error("invalid PBIN comment length");
                    }
                    const auto comment_size = static_cast<std::size_t>(
                        read_u32_le(payload, comment_offset));
                    if (comment_size > 1024 || comment_offset + 4 + comment_size > payload.size()) {
                        throw std::runtime_error("invalid PBIN comment");
                    }
                    comment.assign(
                        reinterpret_cast<const char*>(payload.data() + comment_offset + 4),
                        comment_size);
                }
                write_block(start, payload.subspan(8, size));
                const auto start16 = static_cast<std::uint16_t>(start);
                if (!first_binary.has_value()) {
                    first_binary = start16;
                }
                const auto end = static_cast<std::uint16_t>(size == 0 ? start : start + size - 1);
                info.regions.push_back({start16, end, comment});
                if (!info.entry_point.has_value()) {
                    info.entry_point = entry_from_comment(comment);
                    if (info.entry_point.has_value()) {
                        info.entry_source = "comment";
                    }
                }
            } else if (section == section_cmnt && !seen_comment) {
                seen_comment = true;
                if (payload.size() < 4) {
                    throw std::runtime_error("invalid CMNT section");
                }
                const auto size = static_cast<std::size_t>(read_u32_le(payload, 0));
                if (size > 1024 || 4 + size > payload.size()) {
                    throw std::runtime_error("invalid CMNT payload");
                }
                info.comment.assign(reinterpret_cast<const char*>(payload.data() + 4), size);
            }
        }
        if (!info.entry_point.has_value() && first_binary.has_value()) {
            info.suggested_entry_point = first_binary;
            info.entry_source = "pbin-start";
        }
    }
    if (info.name.empty()) {
        info.name = file_stem_upper(filename);
    }
    if (info.basic) {
        info.autostart_command = "RUN";
    } else if (info.entry_point.has_value()) {
        const char digits[] = "0123456789ABCDEF";
        info.autostart_command = "A=USR($0000)";
        for (int shift = 12, index = 7; shift >= 0; shift -= 4, ++index) {
            info.autostart_command[static_cast<std::size_t>(index)] =
                digits[(*info.entry_point >> shift) & 0x0f];
        }
    }
    if (!info.autostart_command.empty()) {
        queue_autotype(info.autostart_command + '\r');
    }
    return info;
}

std::string Emulator::run_entry(std::uint16_t address) {
    reset();
    const char digits[] = "0123456789ABCDEF";
    std::string command = "A=USR($0000)";
    for (int shift = 12, index = 7; shift >= 0; shift -= 4, ++index) {
        command[static_cast<std::size_t>(index)] = digits[(address >> shift) & 0x0f];
    }
    queue_autotype(command + '\r');
    return command;
}

void Emulator::set_breakpoints(std::span<const std::uint16_t> addresses) {
    breakpoints_.clear();
    breakpoints_.insert(addresses.begin(), addresses.end());
    if (breakpoint_hit_.has_value() && !breakpoints_.contains(*breakpoint_hit_)) {
        breakpoint_hit_.reset();
    }
}

void Emulator::continue_execution() {
    skip_breakpoint_once_ = breakpoint_hit_;
    breakpoint_hit_.reset();
}

void Emulator::step_instruction() {
    breakpoint_hit_.reset();
    cpu_.step_instruction();
    via_.execute(clock_count_);
    sound_.execute(clock_count_);
}

MachineState Emulator::state() const {
    MachineState result;
    result.clock_count = static_cast<std::uint64_t>(std::max<std::int64_t>(clock_count_, 0));
    result.running_status = 0;
    result.joystick_mask = joystick_mask_;
    result.graphics_mode = (memory_[0x0014] & 0x10) != 0;
    result.extended_ram = extended_ram_;
    result.autotype_active = !autotype_queue_.empty() || !autotype_cells_.empty() ||
                             autotype_frames_remaining_ != 0;
    result.breakpoint_hit = breakpoint_hit_;
    const auto& cpu_registers = cpu_.registers();
    const auto& cpu_flags = cpu_.flags();
    result.cpu = CpuState{
        cpu_registers.a,
        cpu_registers.b,
        cpu_registers.ix,
        cpu_registers.sp,
        cpu_registers.pc,
        static_cast<std::uint8_t>((cpu_flags.h ? 0x20 : 0) |
                                  (cpu_flags.i ? 0x10 : 0) |
                                  (cpu_flags.n ? 0x08 : 0) |
                                  (cpu_flags.z ? 0x04 : 0) |
                                  (cpu_flags.v ? 0x02 : 0) |
                                  (cpu_flags.c ? 0x01 : 0)),
    };
    const auto& via_registers = via_.registers();
    result.via = ViaState{
        via_registers.ora,
        via_registers.orb,
        via_registers.ddra,
        via_registers.ddrb,
        via_registers.ifr,
        via_registers.ier,
        via_registers.acr,
        via_registers.pcr,
        static_cast<std::uint16_t>(via_registers.timer1),
        static_cast<std::uint16_t>(via_registers.timer2),
        via_registers.latch1,
        via_registers.latch2,
    };
    return result;
}

std::int64_t Emulator::clock_count() const {
    return clock_count_;
}

void Emulator::set_clock_count(std::int64_t value) {
    clock_count_ = value;
}

Cpu& Emulator::cpu() {
    return cpu_;
}

const Cpu& Emulator::cpu() const {
    return cpu_;
}

Via& Emulator::via() {
    return via_;
}

const Via& Emulator::via() const {
    return via_;
}

Sound& Emulator::sound() {
    return sound_;
}

const Sound& Emulator::sound() const {
    return sound_;
}

const std::array<std::uint8_t, 9>& Emulator::keyboard() const {
    return keyboard_;
}

void Emulator::set_font_plane(bool user_defined) {
    user_font_ = user_defined;
}

const RomInfo& Emulator::rom_info() const {
    return rom_info_;
}

std::span<const std::uint8_t> Emulator::rom_data() const {
    return rom_;
}

bool Emulator::extended_ram() const {
    return extended_ram_;
}

std::uint8_t Emulator::joystick_mask() const {
    return joystick_mask_;
}

void Emulator::advance_autotype() {
    if (autotype_frames_remaining_ > 0) {
        --autotype_frames_remaining_;
        return;
    }
    if (autotype_queue_.empty()) {
        release_autotype_cells();
        return;
    }
    auto stage = std::move(autotype_queue_.front());
    autotype_queue_.pop_front();
    set_autotype_cells(stage.cells);
    autotype_frames_remaining_ = std::max(0, stage.frames - 1);
}

void Emulator::release_autotype_cells() {
    for (const auto& [row, bit] : autotype_cells_) {
        set_key(row, bit, false);
    }
    autotype_cells_.clear();
}

void Emulator::set_autotype_cells(const std::vector<std::pair<int, int>>& cells) {
    release_autotype_cells();
    for (const auto& [row, bit] : cells) {
        set_key(row, bit, true);
    }
    autotype_cells_ = cells;
}

void Emulator::queue_autotype(const std::string& text) {
    release_autotype_cells();
    autotype_queue_.clear();
    autotype_frames_remaining_ = 0;
    autotype_queue_.push_back({{}, 100});
    queue_chord({{0, 0}}, {{0, 3}});
    for (const auto character : text) {
        const auto [cell, shifted] = key_for_character(character);
        if (shifted) {
            queue_chord({{0, 1}}, {cell});
        } else {
            autotype_queue_.push_back({{cell}, 8});
            autotype_queue_.push_back({{}, 6});
        }
    }
}

void Emulator::queue_chord(const std::vector<std::pair<int, int>>& modifiers,
                           const std::vector<std::pair<int, int>>& keys) {
    auto chord = modifiers;
    chord.insert(chord.end(), keys.begin(), keys.end());
    autotype_queue_.push_back({modifiers, 4});
    autotype_queue_.push_back({chord, 8});
    autotype_queue_.push_back({modifiers, 4});
    autotype_queue_.push_back({{}, 6});
}

std::pair<std::pair<int, int>, bool> Emulator::key_for_character(char value) const {
    std::vector<std::pair<int, int>> cells;
    for (int row = 0; row < 9; ++row) {
        for (int bit = 0; bit < 5; ++bit) {
            if (row == 0 && (bit == 0 || bit == 1)) {
                continue;
            }
            cells.emplace_back(row, bit);
        }
    }
    constexpr std::size_t normal_offset = 0x1a6c;
    constexpr std::size_t shifted_offset = 0x1a99;
    for (std::size_t index = 0; index < cells.size(); ++index) {
        if (rom_[normal_offset + index] == static_cast<std::uint8_t>(value)) {
            return {cells[index], false};
        }
    }
    for (std::size_t index = 0; index < cells.size(); ++index) {
        if (rom_[shifted_offset + index] == static_cast<std::uint8_t>(value)) {
            return {cells[index], true};
        }
    }
    throw std::invalid_argument("character cannot be typed on JR-100 keyboard");
}

}  // namespace jr100::detail

namespace jr100 {

class Core::Implementation {
public:
    Implementation(std::span<const std::uint8_t> rom, bool extended_ram)
        : emulator(rom, extended_ram) {}

    detail::Emulator emulator;
};

Core::Core(std::span<const std::uint8_t> rom, bool extended_ram)
    : implementation_(new Implementation(rom, extended_ram)) {}

Core::~Core() {
    delete implementation_;
}

Core::Core(Core&& other) noexcept : implementation_(std::exchange(other.implementation_, nullptr)) {}

Core& Core::operator=(Core&& other) noexcept {
    if (this != &other) {
        delete implementation_;
        implementation_ = std::exchange(other.implementation_, nullptr);
    }
    return *this;
}

void Core::reset() {
    implementation_->emulator.reset();
}

void Core::run_frame(int cycles) {
    implementation_->emulator.run_frame(cycles);
}

void Core::set_key(int row, int bit, bool pressed) {
    implementation_->emulator.set_key(row, bit, pressed);
}

void Core::clear_keys() {
    implementation_->emulator.clear_keys();
}

void Core::set_joystick_mask(std::uint8_t mask) {
    implementation_->emulator.set_joystick_mask(mask);
}

std::span<const std::uint8_t> Core::frame_buffer() {
    return implementation_->emulator.frame_buffer();
}

std::span<const std::int16_t> Core::audio_buffer() const {
    return implementation_->emulator.sound().samples();
}

void Core::clear_audio_buffer() {
    implementation_->emulator.sound().clear_samples();
}

std::span<const std::uint8_t> Core::font_data() const {
    return implementation_->emulator.rom_data().first(1024);
}

std::span<const std::uint8_t> Core::normal_key_codes() const {
    return implementation_->emulator.rom_data().subspan(0x1a6c, 43);
}

std::span<const std::uint8_t> Core::shift_key_codes() const {
    return implementation_->emulator.rom_data().subspan(0x1a99, 43);
}

std::vector<std::uint8_t> Core::read_memory(std::uint16_t start, std::size_t length) const {
    return implementation_->emulator.read_memory(start, length);
}

ProgramInfo Core::load_program(std::span<const std::uint8_t> data,
                               const std::string& filename) {
    return implementation_->emulator.load_program(data, filename);
}

std::string Core::run_entry(std::uint16_t address) {
    return implementation_->emulator.run_entry(address);
}

void Core::set_breakpoints(std::span<const std::uint16_t> addresses) {
    implementation_->emulator.set_breakpoints(addresses);
}

void Core::continue_execution() {
    implementation_->emulator.continue_execution();
}

void Core::step_instruction() {
    implementation_->emulator.step_instruction();
}

const RomInfo& Core::rom_info() const {
    return implementation_->emulator.rom_info();
}

MachineState Core::state() const {
    return implementation_->emulator.state();
}

}  // namespace jr100
