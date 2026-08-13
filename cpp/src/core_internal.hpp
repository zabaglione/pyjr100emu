#pragma once

#include "jr100/core.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <optional>
#include <span>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

namespace jr100::detail {

class Emulator;

struct CpuRegisters {
    std::uint8_t a = 0;
    std::uint8_t b = 0;
    std::uint16_t ix = 0;
    std::uint16_t sp = 0;
    std::uint16_t pc = 0;
};

struct CpuFlags {
    bool h = false;
    bool i = false;
    bool n = false;
    bool z = false;
    bool v = false;
    bool c = false;
};

class Cpu {
public:
    explicit Cpu(Emulator& emulator);

    void reset();
    void set_irq_line(bool asserted);
    void nmi();
    void execute(int clocks);
    void step_instruction();

    [[nodiscard]] const CpuRegisters& registers() const;
    [[nodiscard]] const CpuFlags& flags() const;

private:
    Emulator& emulator_;
    CpuRegisters registers_;
    CpuFlags flags_;
    bool reset_requested_ = false;
    bool nmi_requested_ = false;
    bool irq_asserted_ = false;
    bool fetch_wai_ = false;

    void execute_opcode(std::uint8_t opcode);
    [[nodiscard]] int opcode_cycles(std::uint8_t opcode) const;
    [[nodiscard]] bool service_interrupts(bool in_wai);
    void handle_reset();
    void push_all();
    void pop_all();
    void push8(std::uint8_t value);
    [[nodiscard]] std::uint8_t pull8();
    [[nodiscard]] std::uint8_t fetch8();
    [[nodiscard]] std::uint16_t fetch16();
    [[nodiscard]] std::uint16_t operand_address(std::uint8_t opcode);
    [[nodiscard]] std::uint8_t operand8(std::uint8_t opcode);
    [[nodiscard]] std::uint16_t operand16(std::uint8_t opcode);
    void execute_group(std::uint8_t opcode);
    void execute_accumulator_unary(std::uint8_t opcode);
    void execute_memory_unary(std::uint8_t opcode);
    void execute_branch(std::uint8_t opcode);
    void execute_implied(std::uint8_t opcode);

    [[nodiscard]] std::uint8_t add8(std::uint8_t x, std::uint8_t y);
    [[nodiscard]] std::uint8_t adc8(std::uint8_t x, std::uint8_t y);
    [[nodiscard]] std::uint16_t add16(std::uint16_t x, std::uint16_t y);
    [[nodiscard]] std::uint8_t sub8(std::uint8_t x, std::uint8_t y);
    [[nodiscard]] std::uint8_t sbc8(std::uint8_t x, std::uint8_t y);
    [[nodiscard]] std::uint8_t and8(std::uint8_t x, std::uint8_t y);
    [[nodiscard]] std::uint8_t eor8(std::uint8_t x, std::uint8_t y);
    [[nodiscard]] std::uint8_t ora8(std::uint8_t x, std::uint8_t y);
    void bit8(std::uint8_t x, std::uint8_t y);
    void cmp8(std::uint8_t x, std::uint8_t y);
    [[nodiscard]] std::uint8_t asl(std::uint8_t value);
    [[nodiscard]] std::uint8_t asr(std::uint8_t value);
    [[nodiscard]] std::uint8_t clear_value();
    [[nodiscard]] std::uint8_t complement(std::uint8_t value);
    [[nodiscard]] std::uint8_t decrement(std::uint8_t value);
    [[nodiscard]] std::uint8_t increment(std::uint8_t value);
    [[nodiscard]] std::uint8_t load_accumulator(std::uint8_t value);
    [[nodiscard]] std::uint8_t lsr(std::uint8_t value);
    [[nodiscard]] std::uint8_t negate(std::uint8_t value);
    [[nodiscard]] std::uint8_t rol(std::uint8_t value);
    [[nodiscard]] std::uint8_t ror(std::uint8_t value);
    void store_accumulator(std::uint16_t address, std::uint8_t value);
    void test_value(std::uint8_t value);
    void compare_index(std::uint16_t value);
    void load_index(std::uint16_t value);
    void load_stack(std::uint16_t value);
    void store_index(std::uint16_t address);
    void store_stack(std::uint16_t address);
    void branch(std::uint8_t offset, bool condition);
    [[nodiscard]] std::uint8_t nim(std::uint8_t x, std::uint8_t y);
    [[nodiscard]] std::uint8_t oim(std::uint8_t x, std::uint8_t y);
    [[nodiscard]] std::uint8_t xim(std::uint8_t x, std::uint8_t y);
    void tmm(std::uint8_t x, std::uint8_t y);
};

struct ViaRegisters {
    std::uint8_t ifr = 0;
    std::uint8_t ier = 0;
    std::uint8_t pcr = 0;
    std::uint8_t acr = 0;
    std::uint8_t ira = 0;
    std::uint8_t ora = 0;
    std::uint8_t ddra = 0;
    std::uint8_t irb = 0;
    std::uint8_t orb = 0;
    std::uint8_t ddrb = 0;
    std::uint8_t sr = 0;
    std::uint8_t port_a = 0;
    std::uint8_t port_b = 0;
    int ca1_in = 0;
    int ca2_in = 0;
    int ca2_out = 0;
    int ca2_timer = -1;
    int cb1_in = 0;
    int cb1_out = 0;
    int cb2_in = 0;
    int cb2_out = 0;
    std::uint8_t previous_pb6 = 0;
    std::uint16_t latch1 = 0;
    std::uint16_t latch2 = 0;
    std::int32_t timer1 = 0;
    std::int32_t timer2 = 0;
    bool shift_tick = false;
    int shift_counter = 0;
    bool shift_started = false;
    bool timer1_initialized = false;
    bool timer1_enable = false;
    bool timer2_initialized = false;
    bool timer2_enable = false;
    bool timer2_low_byte_timeout = false;
    std::int64_t current_clock = 0;
};

class Via {
public:
    explicit Via(Emulator& emulator);

    void reset();
    void execute(std::int64_t target_clock);
    [[nodiscard]] std::uint8_t load8(std::uint16_t address);
    void store8(std::uint16_t address, std::uint8_t value);
    [[nodiscard]] const ViaRegisters& registers() const;

private:
    static constexpr std::uint8_t irq_ca2 = 0x01;
    static constexpr std::uint8_t irq_ca1 = 0x02;
    static constexpr std::uint8_t irq_sr = 0x04;
    static constexpr std::uint8_t irq_cb2 = 0x08;
    static constexpr std::uint8_t irq_cb1 = 0x10;
    static constexpr std::uint8_t irq_t2 = 0x20;
    static constexpr std::uint8_t irq_t1 = 0x40;
    static constexpr std::uint8_t irq_any = 0x80;

    Emulator& emulator_;
    ViaRegisters registers_;
    double previous_frequency_ = 0.0;

    void execute_to(std::int64_t target_clock);
    void process_irq(bool force = false);
    void set_interrupt(std::uint8_t bits);
    void clear_interrupt(std::uint8_t bits);
    void set_port_b(int bit, int state);
    void set_port_b_value(std::uint8_t value);
    void invert_port_b(int bit);
    [[nodiscard]] std::uint8_t input_port_a() const;
    [[nodiscard]] std::uint8_t input_port_b() const;
    [[nodiscard]] int input_port_b_bit(int bit) const;
    void output_port_a();
    void output_port_b();
    void jumper_pb7_pb6();
    void store_orb_option();
    void store_iora_option();
    void store_t1ch_option();
    void timer1_timeout_mode0_option();
    void timer1_timeout_mode2_option();
    void timer1_timeout_mode3_option();
    void initialize_shift_in();
    void initialize_shift_out();
    void process_shift_in();
    void process_shift_out();
};

class Sound {
public:
    Sound();

    void reset();
    void set_frequency(std::int64_t clock, double frequency);
    void set_line_on(std::int64_t clock);
    void set_line_off(std::int64_t clock);
    void execute(std::int64_t clock);
    [[nodiscard]] std::span<const std::int16_t> samples() const;
    void clear_samples();

private:
    static constexpr int table_length = 8192;
    static constexpr int max_rank = 30;
    static constexpr long double cpu_frequency = 894'000.0L;
    static constexpr long double output_sample_rate = 44'100.0L;

    std::array<std::array<float, table_length>, max_rank + 1> tables_{};
    std::vector<std::int16_t> samples_;
    int current_rank_ = 0;
    double current_frequency_ = 0.0;
    long double phase_ = 0.0L;
    long double phase_delta_ = 0.0L;
    long double next_sample_clock_ = 0.0L;
    bool timeline_started_ = false;
    bool line_on_ = false;
    double amplitude_ = 0.0;

    void render_until(std::int64_t clock);
    void apply_frequency(double frequency);
    [[nodiscard]] int rank_for_frequency(double frequency) const;
};

struct AutotypeStage {
    std::vector<std::pair<int, int>> cells;
    int frames = 0;
};

class Emulator {
public:
    static constexpr std::uint16_t basic_rom_start = 0xe000;
    static constexpr std::size_t basic_rom_length = 0x2000;
    static constexpr std::uint16_t via_start = 0xc800;

    Emulator(std::span<const std::uint8_t> rom, bool extended_ram);

    [[nodiscard]] std::uint8_t load8(std::uint16_t address) const;
    [[nodiscard]] std::uint16_t load16(std::uint16_t address) const;
    void store8(std::uint16_t address, std::uint8_t value);
    void store16(std::uint16_t address, std::uint16_t value);

    void reset();
    void tick(int cycles);
    void run_frame(int cycles);
    void set_key(int row, int bit, bool pressed);
    void clear_keys();
    void set_joystick_mask(std::uint8_t mask);
    [[nodiscard]] std::span<const std::uint8_t> frame_buffer();
    [[nodiscard]] std::vector<std::uint8_t> read_memory(std::uint16_t start,
                                                        std::size_t length) const;
    ProgramInfo load_program(std::span<const std::uint8_t> data,
                             const std::string& filename);
    std::string run_entry(std::uint16_t address);
    void set_breakpoints(std::span<const std::uint16_t> addresses);
    void continue_execution();
    void step_instruction();
    [[nodiscard]] MachineState state() const;

    [[nodiscard]] std::int64_t clock_count() const;
    void set_clock_count(std::int64_t value);
    [[nodiscard]] Cpu& cpu();
    [[nodiscard]] const Cpu& cpu() const;
    [[nodiscard]] Via& via();
    [[nodiscard]] const Via& via() const;
    [[nodiscard]] Sound& sound();
    [[nodiscard]] const Sound& sound() const;
    [[nodiscard]] const std::array<std::uint8_t, 9>& keyboard() const;
    void set_font_plane(bool user_defined);

    [[nodiscard]] const RomInfo& rom_info() const;
    [[nodiscard]] std::span<const std::uint8_t> rom_data() const;
    [[nodiscard]] bool extended_ram() const;
    [[nodiscard]] std::uint8_t joystick_mask() const;

private:
    RomInfo rom_info_;
    std::array<std::uint8_t, basic_rom_length> rom_{};
    std::array<std::uint8_t, 0x10000> memory_{};
    std::array<std::uint8_t, 9> keyboard_{};
    std::array<std::uint8_t, Core::frame_width * Core::frame_height> frame_{};
    bool extended_ram_ = false;
    bool user_font_ = false;
    std::uint8_t joystick_mask_ = 0;
    std::int64_t clock_count_ = 0;
    Cpu cpu_;
    Via via_;
    Sound sound_;
    std::deque<AutotypeStage> autotype_queue_;
    std::vector<std::pair<int, int>> autotype_cells_;
    int autotype_frames_remaining_ = 0;
    std::unordered_set<std::uint16_t> breakpoints_;
    std::optional<std::uint16_t> breakpoint_hit_;
    std::optional<std::uint16_t> skip_breakpoint_once_;

    void decode_rom(std::span<const std::uint8_t> rom);
    void render_frame();
    void advance_autotype();
    void release_autotype_cells();
    void set_autotype_cells(const std::vector<std::pair<int, int>>& cells);
    void queue_autotype(const std::string& text);
    void queue_chord(const std::vector<std::pair<int, int>>& modifiers,
                     const std::vector<std::pair<int, int>>& keys);
    [[nodiscard]] std::pair<std::pair<int, int>, bool> key_for_character(char value) const;
};

}  // namespace jr100::detail
