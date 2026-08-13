#include "core_internal.hpp"

#include <algorithm>
#include <cmath>
#include <numbers>

namespace jr100::detail {

Via::Via(Emulator& emulator) : emulator_(emulator) {
    reset();
}

void Via::reset() {
    const auto latch1 = registers_.latch1;
    const auto latch2 = registers_.latch2;
    const auto timer1 = registers_.timer1;
    const auto timer2 = registers_.timer2;
    const auto shift = registers_.sr;
    registers_ = ViaRegisters{};
    registers_.latch1 = latch1;
    registers_.latch2 = latch2;
    registers_.timer1 = timer1;
    registers_.timer2 = timer2;
    registers_.sr = shift;
    previous_frequency_ = 0.0;
    emulator_.cpu().set_irq_line(false);
}

void Via::execute(std::int64_t target_clock) {
    execute_to(target_clock);
}

std::uint8_t Via::load8(std::uint16_t address) {
    execute_to(emulator_.clock_count() - 1);
    const auto offset = static_cast<std::uint8_t>(address - Emulator::via_start);
    std::uint8_t result = 0;
    switch (offset) {
    case 0x00:
        result = (registers_.acr & 0x02) == 0 ? input_port_b() : registers_.irb;
        clear_interrupt(static_cast<std::uint8_t>(
            irq_cb1 | (((registers_.pcr & 0xa0) == 0x20) ? 0 : irq_cb2)));
        break;
    case 0x01:
        result = (registers_.acr & 0x01) == 0 ? input_port_a() : registers_.ira;
        clear_interrupt(static_cast<std::uint8_t>(
            irq_ca1 | (((registers_.pcr & 0x0a) == 0x02) ? 0 : irq_ca2)));
        if (registers_.ca2_out == 1 &&
            ((registers_.pcr & 0x0e) == 0x0a || (registers_.pcr & 0x0e) == 0x08)) {
            registers_.ca2_out = 0;
            if ((registers_.pcr & 0x0e) == 0x08) {
                registers_.ca2_timer = 1;
            }
        }
        break;
    case 0x02:
        result = registers_.ddrb;
        break;
    case 0x03:
        result = registers_.ddra;
        break;
    case 0x04:
        clear_interrupt(irq_t1);
        result = static_cast<std::uint8_t>(registers_.timer1);
        break;
    case 0x05:
        result = static_cast<std::uint8_t>(registers_.timer1 >> 8);
        break;
    case 0x06:
        result = static_cast<std::uint8_t>(registers_.latch1);
        break;
    case 0x07:
        result = static_cast<std::uint8_t>(registers_.latch1 >> 8);
        break;
    case 0x08:
        clear_interrupt(irq_t2);
        result = static_cast<std::uint8_t>(registers_.timer2);
        break;
    case 0x09:
        result = static_cast<std::uint8_t>(registers_.timer2 >> 8);
        break;
    case 0x0a:
        clear_interrupt(irq_sr);
        switch (registers_.acr & 0x1c) {
        case 0x04:
        case 0x08:
        case 0x0c:
            initialize_shift_in();
            break;
        case 0x10:
        case 0x14:
        case 0x18:
        case 0x1c:
            initialize_shift_out();
            break;
        default:
            break;
        }
        result = registers_.sr;
        break;
    case 0x0b:
        result = registers_.acr;
        break;
    case 0x0c:
        result = registers_.pcr;
        break;
    case 0x0d:
        result = registers_.ifr;
        break;
    case 0x0e:
        result = registers_.ier | 0x80;
        break;
    case 0x0f:
        result = (registers_.acr & 0x01) == 0 ? input_port_a() : registers_.ira;
        break;
    default:
        break;
    }
    execute_to(emulator_.clock_count());
    return result;
}

void Via::store8(std::uint16_t address, std::uint8_t value) {
    execute_to(emulator_.clock_count() - 1);
    const auto offset = static_cast<std::uint8_t>(address - Emulator::via_start);
    switch (offset) {
    case 0x00:
        registers_.orb = value;
        output_port_b();
        clear_interrupt(static_cast<std::uint8_t>(
            irq_cb1 | (((registers_.pcr & 0xa0) == 0x20) ? 0 : irq_cb2)));
        if (registers_.cb2_out == 1 && (registers_.pcr & 0xc0) == 0x80) {
            registers_.cb2_out = 0;
        }
        store_orb_option();
        break;
    case 0x01:
        registers_.ora = value;
        if (registers_.ddra != 0) {
            output_port_a();
        }
        clear_interrupt(static_cast<std::uint8_t>(
            irq_ca1 | (((registers_.pcr & 0x0a) == 0x02) ? 0 : irq_ca2)));
        if (registers_.ca2_out == 1 &&
            ((registers_.pcr & 0x0e) == 0x0a || (registers_.pcr & 0x0c) == 0x08)) {
            registers_.ca2_out = 0;
        }
        if ((registers_.pcr & 0x0e) == 0x0a) {
            registers_.ca2_timer = 1;
        }
        store_iora_option();
        break;
    case 0x02:
        registers_.ddrb = value;
        break;
    case 0x03:
        registers_.ddra = value;
        break;
    case 0x04:
    case 0x06:
        registers_.latch1 = static_cast<std::uint16_t>((registers_.latch1 & 0xff00) | value);
        break;
    case 0x05:
        registers_.latch1 = static_cast<std::uint16_t>((registers_.latch1 & 0x00ff) |
                                                       (static_cast<std::uint16_t>(value) << 8U));
        registers_.timer1 = registers_.latch1;
        registers_.timer1_initialized = true;
        registers_.timer1_enable = true;
        clear_interrupt(irq_t1);
        set_port_b(7, 0);
        store_t1ch_option();
        break;
    case 0x07:
        registers_.latch1 = static_cast<std::uint16_t>((registers_.latch1 & 0x00ff) |
                                                       (static_cast<std::uint16_t>(value) << 8U));
        break;
    case 0x08:
        registers_.latch2 = static_cast<std::uint16_t>((registers_.latch2 & 0xff00) | value);
        break;
    case 0x09:
        registers_.latch2 = static_cast<std::uint16_t>((registers_.latch2 & 0x00ff) |
                                                       (static_cast<std::uint16_t>(value) << 8U));
        registers_.timer2 = registers_.latch2;
        registers_.timer2_initialized = true;
        registers_.timer2_enable = true;
        clear_interrupt(irq_t2);
        break;
    case 0x0a:
        clear_interrupt(irq_sr);
        switch (registers_.acr & 0x1c) {
        case 0x04:
        case 0x08:
        case 0x0c:
            initialize_shift_in();
            break;
        case 0x10:
        case 0x14:
        case 0x18:
        case 0x1c:
            initialize_shift_out();
            break;
        default:
            break;
        }
        registers_.sr = value;
        break;
    case 0x0b:
        registers_.acr = value;
        if ((value & 0x1c) == 0) {
            registers_.shift_started = false;
            clear_interrupt(irq_sr);
        }
        break;
    case 0x0c:
        registers_.pcr = value;
        break;
    case 0x0d:
        clear_interrupt(value & 0x7f);
        break;
    case 0x0e:
        if ((value & 0x80) != 0) {
            registers_.ier |= value & 0x7f;
        } else {
            registers_.ier &= static_cast<std::uint8_t>(~value);
        }
        registers_.ier &= 0x7f;
        process_irq();
        break;
    case 0x0f:
        registers_.ora = value;
        if (registers_.ddra != 0) {
            output_port_a();
        }
        break;
    default:
        break;
    }
    execute_to(emulator_.clock_count());
}

const ViaRegisters& Via::registers() const {
    return registers_;
}

void Via::execute_to(std::int64_t target_clock) {
    while (registers_.current_clock <= target_clock) {
        if (registers_.ca2_timer >= 0) {
            --registers_.ca2_timer;
            if (registers_.ca2_timer < 0) {
                registers_.ca2_out = 1;
            }
        }

        if (registers_.timer1_initialized) {
            registers_.timer1_initialized = false;
        } else if (registers_.timer1 >= 0) {
            --registers_.timer1;
        } else {
            if (registers_.timer1_enable) {
                set_interrupt(irq_t1);
                switch (registers_.acr & 0xc0) {
                case 0x00:
                    registers_.timer1_enable = false;
                    timer1_timeout_mode0_option();
                    break;
                case 0x40:
                    invert_port_b(7);
                    break;
                case 0x80:
                    registers_.timer1_enable = false;
                    set_port_b(7, 1);
                    timer1_timeout_mode2_option();
                    break;
                case 0xc0:
                    invert_port_b(7);
                    timer1_timeout_mode3_option();
                    break;
                default:
                    break;
                }
            }
            registers_.timer1 = registers_.latch1;
            store_t1ch_option();
        }

        const auto current_pb6 = static_cast<std::uint8_t>(input_port_b() & 0x40);
        const bool pb6_negative = registers_.previous_pb6 != 0 && current_pb6 == 0;
        registers_.previous_pb6 = current_pb6;
        if (registers_.timer2 >= 0) {
            if (registers_.timer2_initialized) {
                registers_.timer2_initialized = false;
            } else if ((registers_.acr & 0x20) == 0 || pb6_negative) {
                --registers_.timer2;
            }
        } else {
            if (registers_.timer2_enable) {
                set_interrupt(irq_t2);
                registers_.timer2_enable = false;
            }
            if (registers_.shift_started && (registers_.timer2 & 0xff) == 0xff) {
                const auto mode = static_cast<std::uint8_t>(registers_.acr & 0x1c);
                if (mode == 0x04) {
                    process_shift_in();
                } else if (mode == 0x10 || mode == 0x14) {
                    process_shift_out();
                }
            }
            registers_.timer2 = registers_.latch2;
        }

        const auto shift_mode = static_cast<std::uint8_t>(registers_.acr & 0x1c);
        if (shift_mode == 0x08) {
            process_shift_in();
        } else if (shift_mode == 0x18) {
            process_shift_out();
        }
        ++registers_.current_clock;
    }
}

void Via::process_irq(bool force) {
    const bool asserted = (registers_.ier & registers_.ifr & 0x7f) != 0;
    const bool previous = (registers_.ifr & irq_any) != 0;
    if (asserted) {
        registers_.ifr |= irq_any;
    } else {
        registers_.ifr &= static_cast<std::uint8_t>(~irq_any);
    }
    if (force || asserted != previous) {
        emulator_.cpu().set_irq_line(asserted);
    }
}

void Via::set_interrupt(std::uint8_t bits) {
    if ((registers_.ifr & bits) == 0) {
        registers_.ifr |= bits;
        process_irq();
    }
}

void Via::clear_interrupt(std::uint8_t bits) {
    if ((registers_.ifr & bits) != 0) {
        registers_.ifr &= static_cast<std::uint8_t>(~bits);
        process_irq();
    }
}

void Via::set_port_b(int bit, int state) {
    const auto mask = static_cast<std::uint8_t>(1U << static_cast<unsigned>(bit));
    if ((registers_.ddrb & mask) != 0) {
        return;
    }
    if (state != 0) {
        registers_.port_b |= mask;
    } else {
        registers_.port_b &= static_cast<std::uint8_t>(~mask);
    }
    if ((registers_.acr & 0x02) == 0) {
        registers_.irb = registers_.port_b;
    }
}

void Via::set_port_b_value(std::uint8_t value) {
    registers_.port_b = static_cast<std::uint8_t>((registers_.port_b & registers_.ddrb) |
                                                  (value & ~registers_.ddrb));
    if ((registers_.acr & 0x02) == 0) {
        registers_.irb = registers_.port_b;
    }
}

void Via::invert_port_b(int bit) {
    set_port_b(bit, input_port_b_bit(bit) == 0 ? 1 : 0);
}

std::uint8_t Via::input_port_a() const {
    return static_cast<std::uint8_t>((registers_.ira & ~registers_.ddra) |
                                     (registers_.port_a & registers_.ddra));
}

std::uint8_t Via::input_port_b() const {
    return static_cast<std::uint8_t>((registers_.irb & ~registers_.ddrb) |
                                     (registers_.orb & registers_.ddrb));
}

int Via::input_port_b_bit(int bit) const {
    return (input_port_b() >> bit) & 1;
}

void Via::output_port_a() {}
void Via::output_port_b() {}
void Via::jumper_pb7_pb6() { set_port_b(6, input_port_b_bit(7)); }
void Via::store_orb_option() {
    emulator_.set_font_plane((input_port_b() & 0x20) != 0);
    jumper_pb7_pb6();
}

void Via::store_iora_option() {
    auto value = static_cast<std::uint8_t>(input_port_b() & 0xe0);
    const auto row = static_cast<std::size_t>(registers_.ora & 0x0f);
    if (row < emulator_.keyboard().size()) {
        value |= static_cast<std::uint8_t>(~emulator_.keyboard()[row]) & 0x1f;
    }
    set_port_b_value(value);
}

void Via::store_t1ch_option() {
    if ((registers_.acr & 0xc0) == 0xc0) {
        const auto divisor = registers_.timer1 + 2;
        if (divisor <= 0) {
            return;
        }
        const auto frequency = 894'886.25 / static_cast<double>(divisor) / 2.0;
        if (std::abs(frequency - previous_frequency_) >= 1e-6) {
            previous_frequency_ = frequency;
            emulator_.sound().set_frequency(registers_.current_clock, frequency);
        }
        emulator_.sound().set_line_on(registers_.current_clock);
    } else {
        emulator_.sound().set_line_off(registers_.current_clock);
    }
}

void Via::timer1_timeout_mode0_option() {
    emulator_.sound().set_line_off(registers_.current_clock);
}
void Via::timer1_timeout_mode2_option() { jumper_pb7_pb6(); }
void Via::timer1_timeout_mode3_option() { jumper_pb7_pb6(); }
void Via::initialize_shift_in() {
    registers_.shift_tick = false;
    registers_.shift_counter = 0;
    if ((registers_.ifr & irq_sr) != 0) {
        clear_interrupt(irq_sr);
        process_shift_in();
    }
    registers_.shift_started = true;
}

void Via::initialize_shift_out() {
    registers_.shift_tick = false;
    registers_.shift_counter = 0;
    if ((registers_.ifr & irq_sr) != 0) {
        clear_interrupt(irq_sr);
        process_shift_out();
    }
    registers_.shift_started = true;
}

void Via::process_shift_in() {
    if (!registers_.shift_started) {
        return;
    }
    if (registers_.shift_tick) {
        registers_.cb1_out = 1;
        registers_.sr = static_cast<std::uint8_t>((registers_.sr << 1U) |
                                                  (registers_.cb2_in & 1));
        registers_.shift_counter = (registers_.shift_counter + 1) % 8;
        if (registers_.shift_counter == 0) {
            set_interrupt(irq_sr);
            registers_.shift_started = false;
        }
    } else {
        registers_.cb1_out = 0;
    }
    registers_.shift_tick = !registers_.shift_tick;
}

void Via::process_shift_out() {
    if (!registers_.shift_started) {
        return;
    }
    if (registers_.shift_tick) {
        registers_.cb1_out = 1;
        registers_.cb2_out = (registers_.sr >> 7U) & 1;
        registers_.sr = static_cast<std::uint8_t>((registers_.sr << 1U) |
                                                  (registers_.cb2_out & 1));
        if ((registers_.acr & 0x1c) != 0x10) {
            registers_.shift_counter = (registers_.shift_counter + 1) % 8;
            if (registers_.shift_counter == 0) {
                set_interrupt(irq_sr);
                registers_.shift_started = false;
            }
        }
    } else {
        registers_.cb1_out = 0;
    }
    registers_.shift_tick = !registers_.shift_tick;
}

Sound::Sound() {
    const auto coefficient = 19.36708871;
    const auto decibels = coefficient * (std::log10(30.0) - 2.0);
    amplitude_ = std::pow(10.0, (std::log10(2.0) / 3.0) * decibels) * 0.8;
    for (int rank = 1; rank <= max_rank; ++rank) {
        for (int index = 0; index < table_length; ++index) {
            const auto phase = static_cast<double>(index) / table_length;
            const auto x = 2.0 * std::numbers::pi * phase;
            double value = 0.0;
            for (int harmonic = 1; harmonic <= rank; ++harmonic) {
                const auto odd = 2 * harmonic - 1;
                value += std::sin(odd * x) / odd;
            }
            tables_[rank][index] = static_cast<float>((4.0 * value) / std::numbers::pi);
        }
    }
}

void Sound::reset() {
    samples_.clear();
    current_rank_ = 0;
    current_frequency_ = 0.0;
    phase_ = 0.0L;
    phase_delta_ = 0.0L;
    next_sample_clock_ = 0.0L;
    timeline_started_ = false;
    line_on_ = false;
}

void Sound::set_frequency(std::int64_t clock, double frequency) {
    render_until(clock);
    if (!timeline_started_) {
        timeline_started_ = true;
        next_sample_clock_ = static_cast<long double>(clock);
    }
    apply_frequency(frequency);
}

void Sound::set_line_on(std::int64_t clock) {
    if (line_on_) {
        return;
    }
    render_until(clock);
    if (!timeline_started_) {
        timeline_started_ = true;
        next_sample_clock_ = static_cast<long double>(clock);
    }
    line_on_ = true;
}

void Sound::set_line_off(std::int64_t clock) {
    if (!line_on_) {
        return;
    }
    render_until(clock);
    if (!timeline_started_) {
        timeline_started_ = true;
        next_sample_clock_ = static_cast<long double>(clock);
    }
    line_on_ = false;
}

void Sound::execute(std::int64_t clock) {
    render_until(clock);
}

std::span<const std::int16_t> Sound::samples() const { return samples_; }
void Sound::clear_samples() { samples_.clear(); }
void Sound::render_until(std::int64_t clock) {
    if (!timeline_started_) {
        return;
    }
    const auto target = static_cast<long double>(clock);
    const auto period = cpu_frequency / output_sample_rate;
    const auto gain = amplitude_ * static_cast<double>((1U << 15U) - 1U);
    while (next_sample_clock_ < target) {
        double sample = 0.0;
        if (line_on_ && current_rank_ > 0) {
            const auto index = static_cast<std::size_t>(phase_) % table_length;
            sample = static_cast<double>(tables_[current_rank_][index]) * gain;
        }
        const auto clipped = std::clamp(sample, -32768.0, 32767.0);
        samples_.push_back(static_cast<std::int16_t>(clipped));
        phase_ += phase_delta_;
        if (phase_ >= table_length) {
            phase_ = std::fmod(phase_, static_cast<long double>(table_length));
        }
        next_sample_clock_ += period;
    }
}

void Sound::apply_frequency(double frequency) {
    current_frequency_ = frequency;
    if (frequency <= 0.0 || frequency >= static_cast<double>(output_sample_rate / 2.0L)) {
        current_rank_ = 0;
        phase_delta_ = 0.0L;
        return;
    }
    current_rank_ = rank_for_frequency(frequency);
    phase_delta_ = (static_cast<long double>(table_length) * frequency) / output_sample_rate;
}

int Sound::rank_for_frequency(double frequency) const {
    if (frequency <= 0.0) {
        return 0;
    }
    const auto value = (static_cast<double>(output_sample_rate) / (2.0 * frequency) + 1.0) /
                       2.0;
    if (value < 1.0) {
        return 1;
    }
    return std::min(max_rank, static_cast<int>(std::floor(value)));
}

}  // namespace jr100::detail
