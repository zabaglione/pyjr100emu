#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <span>
#include <string>
#include <vector>

namespace jr100 {

struct RomInfo {
    std::string format;
    std::string name;
    std::uint16_t start_address = 0xe000;
    std::size_t size = 0;
};

struct AddressRegion {
    std::uint16_t start = 0;
    std::uint16_t end = 0;
    std::string comment;
};

struct ProgramInfo {
    std::string name;
    std::string comment;
    int version = 0;
    bool basic = false;
    std::optional<std::uint16_t> entry_point;
    std::optional<std::uint16_t> suggested_entry_point;
    std::string entry_source;
    std::string autostart_command;
    std::vector<AddressRegion> regions;
};

struct CpuState {
    std::uint8_t a = 0;
    std::uint8_t b = 0;
    std::uint16_t ix = 0;
    std::uint16_t sp = 0;
    std::uint16_t pc = 0;
    std::uint8_t flags = 0;
};

struct ViaState {
    std::uint8_t ora = 0;
    std::uint8_t orb = 0;
    std::uint8_t ddra = 0;
    std::uint8_t ddrb = 0;
    std::uint8_t ifr = 0;
    std::uint8_t ier = 0;
    std::uint8_t acr = 0;
    std::uint8_t pcr = 0;
    std::uint16_t timer1 = 0;
    std::uint16_t timer2 = 0;
    std::uint16_t latch1 = 0;
    std::uint16_t latch2 = 0;
};

struct MachineState {
    std::uint64_t clock_count = 0;
    int running_status = 0;
    std::uint8_t joystick_mask = 0;
    bool graphics_mode = false;
    bool extended_ram = false;
    bool autotype_active = false;
    std::optional<std::uint16_t> breakpoint_hit;
    CpuState cpu;
    ViaState via;
};

class Core {
public:
    static constexpr int frame_width = 256;
    static constexpr int frame_height = 192;
    static constexpr int sample_rate = 44'100;
    static constexpr int cycles_per_frame = 14'900;

    Core(std::span<const std::uint8_t> rom, bool extended_ram = false);
    ~Core();

    Core(const Core&) = delete;
    Core& operator=(const Core&) = delete;
    Core(Core&&) noexcept;
    Core& operator=(Core&&) noexcept;

    void reset();
    void run_frame(int cycles = cycles_per_frame);
    void set_key(int row, int bit, bool pressed);
    void clear_keys();
    void set_joystick_mask(std::uint8_t mask);

    [[nodiscard]] std::span<const std::uint8_t> frame_buffer();
    [[nodiscard]] std::span<const std::int16_t> audio_buffer() const;
    void clear_audio_buffer();
    [[nodiscard]] std::span<const std::uint8_t> font_data() const;
    [[nodiscard]] std::span<const std::uint8_t> normal_key_codes() const;
    [[nodiscard]] std::span<const std::uint8_t> shift_key_codes() const;
    [[nodiscard]] std::vector<std::uint8_t> read_memory(std::uint16_t start,
                                                        std::size_t length) const;

    ProgramInfo load_program(std::span<const std::uint8_t> data,
                             const std::string& filename);
    std::string run_entry(std::uint16_t address);

    void set_breakpoints(std::span<const std::uint16_t> addresses);
    void continue_execution();
    void step_instruction();

    [[nodiscard]] const RomInfo& rom_info() const;
    [[nodiscard]] MachineState state() const;

private:
    class Implementation;
    Implementation* implementation_ = nullptr;
};

}  // namespace jr100
