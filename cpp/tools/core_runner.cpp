#include "jr100/core.hpp"

#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

std::vector<std::uint8_t> read_file(const std::string& path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("cannot open input file: " + path);
    }
    return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}

void write_audio(const std::string& path, std::span<const std::int16_t> samples) {
    std::ofstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("cannot open audio output: " + path);
    }
    for (const auto sample : samples) {
        const auto value = static_cast<std::uint16_t>(sample);
        const char bytes[] = {
            static_cast<char>(value & 0xff),
            static_cast<char>(value >> 8U),
        };
        stream.write(bytes, 2);
    }
}

std::vector<std::pair<std::size_t, std::size_t>> active_segments(
    std::span<const std::int16_t> samples) {
    constexpr std::size_t window = 32;
    std::vector<std::pair<std::size_t, std::size_t>> segments;
    std::size_t start = samples.size();
    for (std::size_t offset = 0; offset < samples.size(); offset += window) {
        const auto end = std::min(offset + window, samples.size());
        const bool active = std::any_of(
            samples.begin() + static_cast<std::ptrdiff_t>(offset),
            samples.begin() + static_cast<std::ptrdiff_t>(end),
            [](std::int16_t sample) { return sample != 0; });
        if (active && start == samples.size()) {
            start = offset;
        } else if (!active && start != samples.size()) {
            segments.emplace_back(start, offset);
            start = samples.size();
        }
    }
    if (start != samples.size()) {
        segments.emplace_back(start, samples.size());
    }
    return segments;
}

double frequency(std::span<const std::int16_t> samples) {
    bool have_previous = false;
    bool previous = false;
    std::size_t crossings = 0;
    for (const auto sample : samples) {
        if (sample == 0) {
            continue;
        }
        const bool sign = sample > 0;
        if (have_previous && sign != previous) {
            ++crossings;
        }
        previous = sign;
        have_previous = true;
    }
    if (samples.empty()) {
        return 0.0;
    }
    return static_cast<double>(crossings) * jr100::Core::sample_rate /
           (2.0 * static_cast<double>(samples.size()));
}

}  // namespace

int main(int argc, char** argv) {
    try {
        std::string rom_path;
        std::string program_path;
        std::string audio_path;
        std::string scenario;
        int frames = 1'200;
        int boot_frames = 0;
        bool extended_ram = false;
        for (int index = 1; index < argc; ++index) {
            const std::string argument = argv[index];
            if (argument == "--rom" && index + 1 < argc) {
                rom_path = argv[++index];
            } else if (argument == "--program" && index + 1 < argc) {
                program_path = argv[++index];
            } else if (argument == "--audio" && index + 1 < argc) {
                audio_path = argv[++index];
            } else if (argument == "--frames" && index + 1 < argc) {
                frames = std::stoi(argv[++index]);
            } else if (argument == "--boot-frames" && index + 1 < argc) {
                boot_frames = std::stoi(argv[++index]);
            } else if (argument == "--scenario" && index + 1 < argc) {
                scenario = argv[++index];
            } else if (argument == "--extended-ram") {
                extended_ram = true;
            } else {
                throw std::runtime_error("invalid command-line argument: " + argument);
            }
        }
        if (rom_path.empty() || frames <= 0 || boot_frames < 0) {
            throw std::runtime_error("--rom and valid frame counts are required");
        }

        const auto rom = read_file(rom_path);
        jr100::Core core(rom, extended_ram);
        for (int frame = 0; frame < boot_frames; ++frame) {
            core.run_frame();
        }
        core.clear_audio_buffer();
        jr100::ProgramInfo program_info;
        if (!program_path.empty()) {
            const auto program = read_file(program_path);
            const auto slash = program_path.find_last_of("/\\");
            const auto filename = slash == std::string::npos
                                      ? program_path
                                      : program_path.substr(slash + 1);
            program_info = core.load_program(program, filename);
        }
        if (scenario == "basic-beep") {
            const auto advance = [&core](std::uint64_t cycles) {
                const auto target = core.state().clock_count + cycles;
                while (core.state().clock_count < target) {
                    core.run_frame(512);
                }
            };
            if (boot_frames == 0) {
                advance(2'048'000);
            }
            core.clear_audio_buffer();
            const auto press = [&core, &advance](int row, int bit) {
                core.set_key(row, bit, true);
                advance(50'000);
                core.set_key(row, bit, false);
                advance(100'000);
            };
            press(1, 0);
            press(8, 3);
            advance(200'000);
        } else {
            if (!scenario.empty()) {
                throw std::runtime_error("unknown scenario: " + scenario);
            }
            for (int frame = 0; frame < frames; ++frame) {
                core.run_frame();
            }
        }
        const auto audio = core.audio_buffer();
        if (!audio_path.empty()) {
            write_audio(audio_path, audio);
        }
        const auto segments = active_segments(audio);
        const auto state = core.state();
        std::cout << "{\"frames\":" << frames << ",\"samples\":" << audio.size()
                  << ",\"scenario\":" << (scenario.empty() ? "null" : "\"basic-beep\"")
                  << ",\"segments\":" << segments.size() << ",\"durationsMs\":[";
        for (std::size_t index = 0; index < segments.size(); ++index) {
            if (index != 0) {
                std::cout << ',';
            }
            const auto [start, end] = segments[index];
            std::cout << std::fixed << std::setprecision(3)
                      << static_cast<double>(end - start) * 1'000.0 / jr100::Core::sample_rate;
        }
        std::cout << "],\"frequencies\":[";
        for (std::size_t index = 0; index < segments.size(); ++index) {
            if (index != 0) {
                std::cout << ',';
            }
            const auto [start, end] = segments[index];
            std::cout << std::fixed << std::setprecision(1)
                      << frequency(audio.subspan(start, end - start));
        }
        std::cout << "],\"clockCount\":" << state.clock_count << ",\"pc\":"
                  << state.cpu.pc << ",\"a\":" << static_cast<int>(state.cpu.a)
                  << ",\"b\":" << static_cast<int>(state.cpu.b)
                  << ",\"ix\":" << state.cpu.ix << ",\"sp\":" << state.cpu.sp
                  << ",\"flags\":" << static_cast<int>(state.cpu.flags)
                  << ",\"ifr\":" << static_cast<int>(state.via.ifr)
                  << ",\"ier\":" << static_cast<int>(state.via.ier)
                  << ",\"acr\":" << static_cast<int>(state.via.acr)
                  << ",\"timer1\":" << state.via.timer1
                  << ",\"timer2\":" << state.via.timer2
                  << ",\"graphicsMode\":" << (state.graphics_mode ? "true" : "false")
                  << ",\"programBasic\":" << (program_info.basic ? "true" : "false")
                  << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
