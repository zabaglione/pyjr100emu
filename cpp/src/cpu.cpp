#include "core_internal.hpp"

#include <cstdint>

namespace jr100::detail {
namespace {

constexpr std::int8_t signed8(std::uint8_t value) {
    return static_cast<std::int8_t>(value);
}

constexpr std::int16_t signed16(std::uint16_t value) {
    return static_cast<std::int16_t>(value);
}

bool is_group_opcode(std::uint8_t opcode) {
    if (opcode < 0x80) {
        return false;
    }
    const auto operation = static_cast<std::uint8_t>(opcode & 0x0f);
    const auto mode = static_cast<std::uint8_t>((opcode >> 4U) & 0x03U);
    const bool accumulator_a_group = opcode < 0xc0;
    if (operation <= 0x02 || (operation >= 0x04 && operation <= 0x06) ||
        (operation >= 0x08 && operation <= 0x0b)) {
        return true;
    }
    if (operation == 0x07) {
        return mode != 0;
    }
    if (operation == 0x0c) {
        return accumulator_a_group;
    }
    if (operation == 0x0e) {
        return true;
    }
    if (operation == 0x0f) {
        return mode != 0;
    }
    return opcode == 0x8d || opcode == 0xad || opcode == 0xbd || opcode == 0xec ||
           opcode == 0xfc;
}

bool is_accumulator_unary(std::uint8_t opcode) {
    if ((opcode & 0xf0) != 0x40 && (opcode & 0xf0) != 0x50) {
        return false;
    }
    switch (opcode & 0x0f) {
    case 0x00:
    case 0x03:
    case 0x04:
    case 0x06:
    case 0x07:
    case 0x08:
    case 0x09:
    case 0x0a:
    case 0x0c:
    case 0x0d:
    case 0x0f:
        return true;
    default:
        return false;
    }
}

bool is_memory_unary(std::uint8_t opcode) {
    if ((opcode & 0xf0) != 0x60 && (opcode & 0xf0) != 0x70) {
        return false;
    }
    if (opcode == 0x71 || opcode == 0x72 || opcode == 0x75 || opcode == 0x7b) {
        return true;
    }
    switch (opcode & 0x0f) {
    case 0x00:
    case 0x03:
    case 0x04:
    case 0x06:
    case 0x07:
    case 0x08:
    case 0x09:
    case 0x0a:
    case 0x0c:
    case 0x0d:
    case 0x0e:
    case 0x0f:
        return true;
    default:
        return false;
    }
}

bool is_branch(std::uint8_t opcode) {
    return opcode == 0x20 || (opcode >= 0x22 && opcode <= 0x2f);
}

}  // namespace

Cpu::Cpu(Emulator& emulator) : emulator_(emulator) {}

void Cpu::reset() {
    reset_requested_ = true;
}

void Cpu::set_irq_line(bool asserted) {
    irq_asserted_ = asserted;
}

void Cpu::nmi() {
    nmi_requested_ = true;
}

void Cpu::execute(int clocks) {
    const auto target = emulator_.clock_count() + clocks;
    while (emulator_.clock_count() < target) {
        if (reset_requested_) {
            handle_reset();
            return;
        }
        if (fetch_wai_) {
            if (!service_interrupts(true)) {
                emulator_.set_clock_count(emulator_.clock_count() + 1);
            }
            continue;
        }
        if (service_interrupts(false)) {
            continue;
        }
        const auto opcode = fetch8();
        execute_opcode(opcode);
        emulator_.set_clock_count(emulator_.clock_count() + opcode_cycles(opcode));
    }
}

void Cpu::step_instruction() {
    const auto before = emulator_.clock_count();
    for (int attempt = 0; attempt < 2 && emulator_.clock_count() == before; ++attempt) {
        execute(1);
    }
}

const CpuRegisters& Cpu::registers() const {
    return registers_;
}

const CpuFlags& Cpu::flags() const {
    return flags_;
}

void Cpu::handle_reset() {
    reset_requested_ = false;
    fetch_wai_ = false;
    flags_.i = true;
    registers_.pc = emulator_.load16(0xfffe);
    emulator_.set_clock_count(0);
}

bool Cpu::service_interrupts(bool in_wai) {
    if (nmi_requested_) {
        nmi_requested_ = false;
        fetch_wai_ = false;
        if (!in_wai) {
            push_all();
        }
        flags_.i = true;
        registers_.pc = emulator_.load16(0xfffc);
        emulator_.set_clock_count(emulator_.clock_count() + (in_wai ? 4 : 12));
        return true;
    }
    if (irq_asserted_ && !flags_.i) {
        fetch_wai_ = false;
        if (!in_wai) {
            push_all();
        }
        flags_.i = true;
        registers_.pc = emulator_.load16(0xfff8);
        emulator_.set_clock_count(emulator_.clock_count() + (in_wai ? 4 : 12));
        return true;
    }
    return false;
}

void Cpu::execute_opcode(std::uint8_t opcode) {
    switch (opcode) {
    case 0x3b:
        pop_all();
        return;
    case 0x39: {
        const auto sp = static_cast<std::uint16_t>(registers_.sp + 2);
        registers_.pc = emulator_.load16(static_cast<std::uint16_t>(sp - 1));
        registers_.sp = sp;
        return;
    }
    case 0x3f:
        push_all();
        flags_.i = true;
        registers_.pc = emulator_.load16(0xfffa);
        return;
    case 0x3e:
        push_all();
        fetch_wai_ = true;
        return;
    case 0xec:
        registers_.ix = add16(registers_.ix, fetch8());
        return;
    case 0xfc: {
        const auto address = fetch16();
        registers_.ix = add16(registers_.ix, emulator_.load16(address));
        return;
    }
    case 0x71:
    case 0x72:
    case 0x75:
    case 0x7b: {
        const auto mask = fetch8();
        const auto address = static_cast<std::uint16_t>(registers_.ix + fetch8());
        const auto current = emulator_.load8(address);
        if (opcode == 0x71) {
            emulator_.store8(address, nim(mask, current));
        } else if (opcode == 0x72) {
            emulator_.store8(address, oim(mask, current));
        } else if (opcode == 0x75) {
            emulator_.store8(address, xim(mask, current));
        } else {
            tmm(mask, current);
        }
        return;
    }
    default:
        break;
    }
    if (is_branch(opcode)) {
        execute_branch(opcode);
    } else if (is_accumulator_unary(opcode)) {
        execute_accumulator_unary(opcode);
    } else if (is_memory_unary(opcode)) {
        execute_memory_unary(opcode);
    } else if (is_group_opcode(opcode)) {
        execute_group(opcode);
    } else {
        execute_implied(opcode);
    }
}

int Cpu::opcode_cycles(std::uint8_t opcode) const {
    switch (opcode) {
    case 0x3b:
        return 10;
    case 0x39:
        return 5;
    case 0x3f:
        return 12;
    case 0x3e:
        return 9;
    case 0x8d:
        return 8;
    case 0xad:
        return 8;
    case 0xbd:
        return 9;
    case 0xec:
        return 4;
    case 0xfc:
        return 7;
    case 0x71:
    case 0x72:
    case 0x75:
        return 8;
    case 0x7b:
        return 7;
    default:
        break;
    }
    if (is_branch(opcode)) {
        return 4;
    }
    if (is_accumulator_unary(opcode)) {
        return 2;
    }
    if (is_memory_unary(opcode)) {
        if ((opcode & 0x0f) == 0x0e) {
            return (opcode & 0xf0) == 0x60 ? 4 : 3;
        }
        return (opcode & 0xf0) == 0x60 ? 7 : 6;
    }
    if (is_group_opcode(opcode)) {
        const auto mode = static_cast<int>((opcode >> 4U) & 0x03U);
        const auto operation = static_cast<std::uint8_t>(opcode & 0x0f);
        if (operation == 0x07) {
            constexpr int cycles[] = {1, 4, 6, 5};
            return cycles[mode];
        }
        if (operation == 0x0c || operation == 0x0e) {
            constexpr int cycles[] = {3, 4, 6, 5};
            return cycles[mode];
        }
        if (operation == 0x0f) {
            constexpr int cycles[] = {1, 5, 7, 6};
            return cycles[mode];
        }
        constexpr int cycles[] = {2, 3, 5, 4};
        return cycles[mode];
    }
    switch (opcode) {
    case 0x01:
    case 0x06:
    case 0x07:
    case 0x0a:
    case 0x0b:
    case 0x0c:
    case 0x0d:
    case 0x0e:
    case 0x0f:
    case 0x10:
    case 0x11:
    case 0x16:
    case 0x17:
    case 0x19:
    case 0x1b:
        return 2;
    case 0x08:
    case 0x09:
    case 0x30:
    case 0x31:
    case 0x32:
    case 0x33:
    case 0x34:
    case 0x35:
    case 0x36:
    case 0x37:
        return 4;
    default:
        return 1;
    }
}

void Cpu::push_all() {
    auto ccr = std::uint8_t{0xc0};
    ccr |= flags_.h ? 0x20 : 0;
    ccr |= flags_.i ? 0x10 : 0;
    ccr |= flags_.n ? 0x08 : 0;
    ccr |= flags_.z ? 0x04 : 0;
    ccr |= flags_.v ? 0x02 : 0;
    ccr |= flags_.c ? 0x01 : 0;
    const auto sp = registers_.sp;
    emulator_.store16(static_cast<std::uint16_t>(sp - 1), registers_.pc);
    emulator_.store16(static_cast<std::uint16_t>(sp - 3), registers_.ix);
    emulator_.store8(static_cast<std::uint16_t>(sp - 4), registers_.a);
    emulator_.store8(static_cast<std::uint16_t>(sp - 5), registers_.b);
    emulator_.store8(static_cast<std::uint16_t>(sp - 6), ccr);
    registers_.sp = static_cast<std::uint16_t>(sp - 7);
}

void Cpu::pop_all() {
    const auto sp = static_cast<std::uint16_t>(registers_.sp + 7);
    const auto ccr = emulator_.load8(static_cast<std::uint16_t>(sp - 6));
    flags_.h = (ccr & 0x20) != 0;
    flags_.i = (ccr & 0x10) != 0;
    flags_.n = (ccr & 0x08) != 0;
    flags_.z = (ccr & 0x04) != 0;
    flags_.v = (ccr & 0x02) != 0;
    flags_.c = (ccr & 0x01) != 0;
    registers_.b = emulator_.load8(static_cast<std::uint16_t>(sp - 5));
    registers_.a = emulator_.load8(static_cast<std::uint16_t>(sp - 4));
    registers_.ix = emulator_.load16(static_cast<std::uint16_t>(sp - 3));
    registers_.pc = emulator_.load16(static_cast<std::uint16_t>(sp - 1));
    registers_.sp = sp;
}

void Cpu::push8(std::uint8_t value) {
    emulator_.store8(registers_.sp, value);
    registers_.sp = static_cast<std::uint16_t>(registers_.sp - 1);
}

std::uint8_t Cpu::pull8() {
    registers_.sp = static_cast<std::uint16_t>(registers_.sp + 1);
    return emulator_.load8(registers_.sp);
}

std::uint8_t Cpu::fetch8() {
    const auto value = emulator_.load8(registers_.pc);
    registers_.pc = static_cast<std::uint16_t>(registers_.pc + 1);
    return value;
}

std::uint16_t Cpu::fetch16() {
    const auto high = static_cast<std::uint16_t>(fetch8());
    return static_cast<std::uint16_t>((high << 8U) | fetch8());
}

std::uint16_t Cpu::operand_address(std::uint8_t opcode) {
    switch ((opcode >> 4U) & 0x03U) {
    case 1:
        return fetch8();
    case 2:
        return static_cast<std::uint16_t>(registers_.ix + fetch8());
    case 3:
        return fetch16();
    default:
        return 0;
    }
}

std::uint8_t Cpu::operand8(std::uint8_t opcode) {
    if (((opcode >> 4U) & 0x03U) == 0) {
        return fetch8();
    }
    return emulator_.load8(operand_address(opcode));
}

std::uint16_t Cpu::operand16(std::uint8_t opcode) {
    if (((opcode >> 4U) & 0x03U) == 0) {
        return fetch16();
    }
    return emulator_.load16(operand_address(opcode));
}

void Cpu::execute_group(std::uint8_t opcode) {
    if (opcode == 0x8d) {
        const auto offset = fetch8();
        registers_.sp = static_cast<std::uint16_t>(registers_.sp - 2);
        emulator_.store16(static_cast<std::uint16_t>(registers_.sp + 1), registers_.pc);
        branch(offset, true);
        return;
    }
    if (opcode == 0xad || opcode == 0xbd) {
        const auto address = operand_address(opcode);
        registers_.sp = static_cast<std::uint16_t>(registers_.sp - 2);
        emulator_.store16(static_cast<std::uint16_t>(registers_.sp + 1), registers_.pc);
        registers_.pc = address;
        return;
    }

    const bool accumulator_b = opcode >= 0xc0;
    auto& accumulator = accumulator_b ? registers_.b : registers_.a;
    switch (opcode & 0x0f) {
    case 0x00:
        accumulator = sub8(accumulator, operand8(opcode));
        break;
    case 0x01:
        cmp8(accumulator, operand8(opcode));
        break;
    case 0x02:
        accumulator = sbc8(accumulator, operand8(opcode));
        break;
    case 0x04:
        accumulator = and8(accumulator, operand8(opcode));
        break;
    case 0x05:
        bit8(accumulator, operand8(opcode));
        break;
    case 0x06:
        accumulator = load_accumulator(operand8(opcode));
        break;
    case 0x07:
        store_accumulator(operand_address(opcode), accumulator);
        break;
    case 0x08:
        accumulator = eor8(accumulator, operand8(opcode));
        break;
    case 0x09:
        accumulator = adc8(accumulator, operand8(opcode));
        break;
    case 0x0a:
        accumulator = ora8(accumulator, operand8(opcode));
        break;
    case 0x0b:
        accumulator = add8(accumulator, operand8(opcode));
        break;
    case 0x0c:
        compare_index(operand16(opcode));
        break;
    case 0x0e:
        if (accumulator_b) {
            load_index(operand16(opcode));
        } else {
            load_stack(operand16(opcode));
        }
        break;
    case 0x0f:
        if (accumulator_b) {
            store_index(operand_address(opcode));
        } else {
            store_stack(operand_address(opcode));
        }
        break;
    default:
        break;
    }
}

void Cpu::execute_accumulator_unary(std::uint8_t opcode) {
    auto& accumulator = (opcode & 0xf0) == 0x40 ? registers_.a : registers_.b;
    switch (opcode & 0x0f) {
    case 0x00:
        accumulator = negate(accumulator);
        break;
    case 0x03:
        accumulator = complement(accumulator);
        break;
    case 0x04:
        accumulator = lsr(accumulator);
        break;
    case 0x06:
        accumulator = ror(accumulator);
        break;
    case 0x07:
        accumulator = asr(accumulator);
        break;
    case 0x08:
        accumulator = asl(accumulator);
        break;
    case 0x09:
        accumulator = rol(accumulator);
        break;
    case 0x0a:
        accumulator = decrement(accumulator);
        break;
    case 0x0c:
        accumulator = increment(accumulator);
        break;
    case 0x0d:
        test_value(accumulator);
        break;
    case 0x0f:
        accumulator = clear_value();
        break;
    default:
        break;
    }
}

void Cpu::execute_memory_unary(std::uint8_t opcode) {
    const auto address = (opcode & 0xf0) == 0x60
                             ? static_cast<std::uint16_t>(registers_.ix + fetch8())
                             : fetch16();
    if ((opcode & 0x0f) == 0x0e) {
        registers_.pc = address;
        return;
    }
    const auto current = emulator_.load8(address);
    std::uint8_t value = current;
    bool write = true;
    switch (opcode & 0x0f) {
    case 0x00:
        value = negate(current);
        break;
    case 0x03:
        value = complement(current);
        break;
    case 0x04:
        value = lsr(current);
        break;
    case 0x06:
        value = ror(current);
        break;
    case 0x07:
        value = asr(current);
        break;
    case 0x08:
        value = asl(current);
        break;
    case 0x09:
        value = rol(current);
        break;
    case 0x0a:
        value = decrement(current);
        break;
    case 0x0c:
        value = increment(current);
        break;
    case 0x0d:
        test_value(current);
        write = false;
        break;
    case 0x0f:
        value = clear_value();
        break;
    default:
        write = false;
        break;
    }
    if (write) {
        emulator_.store8(address, value);
    }
}

void Cpu::execute_branch(std::uint8_t opcode) {
    const auto offset = fetch8();
    bool condition = false;
    switch (opcode) {
    case 0x20:
        condition = true;
        break;
    case 0x22:
        condition = !flags_.c && !flags_.z;
        break;
    case 0x23:
        condition = flags_.c || flags_.z;
        break;
    case 0x24:
        condition = !flags_.c;
        break;
    case 0x25:
        condition = flags_.c;
        break;
    case 0x26:
        condition = !flags_.z;
        break;
    case 0x27:
        condition = flags_.z;
        break;
    case 0x28:
        condition = !flags_.v;
        break;
    case 0x29:
        condition = flags_.v;
        break;
    case 0x2a:
        condition = !flags_.n;
        break;
    case 0x2b:
        condition = flags_.n;
        break;
    case 0x2c:
        condition = !(flags_.n ^ flags_.v);
        break;
    case 0x2d:
        condition = flags_.n ^ flags_.v;
        break;
    case 0x2e:
        condition = !flags_.z && !(flags_.n ^ flags_.v);
        break;
    case 0x2f:
        condition = flags_.z || (flags_.n ^ flags_.v);
        break;
    default:
        break;
    }
    branch(offset, condition);
}

void Cpu::execute_implied(std::uint8_t opcode) {
    switch (opcode) {
    case 0x01:
        break;
    case 0x06: {
        const auto value = registers_.a;
        flags_.h = (value & 0x20) != 0;
        flags_.i = (value & 0x10) != 0;
        flags_.n = (value & 0x08) != 0;
        flags_.z = (value & 0x04) != 0;
        flags_.v = (value & 0x02) != 0;
        flags_.c = (value & 0x01) != 0;
        break;
    }
    case 0x07:
        registers_.a = static_cast<std::uint8_t>(0xc0 | (flags_.h ? 0x20 : 0) |
                                                 (flags_.i ? 0x10 : 0) |
                                                 (flags_.n ? 0x08 : 0) |
                                                 (flags_.z ? 0x04 : 0) |
                                                 (flags_.v ? 0x02 : 0) |
                                                 (flags_.c ? 0x01 : 0));
        break;
    case 0x08:
        registers_.ix = static_cast<std::uint16_t>(registers_.ix + 1);
        flags_.z = registers_.ix == 0;
        break;
    case 0x09:
        registers_.ix = static_cast<std::uint16_t>(registers_.ix - 1);
        flags_.z = registers_.ix == 0;
        break;
    case 0x0a:
        flags_.v = false;
        break;
    case 0x0b:
        flags_.v = true;
        break;
    case 0x0c:
        flags_.c = false;
        break;
    case 0x0d:
        flags_.c = true;
        break;
    case 0x0e:
        flags_.i = false;
        break;
    case 0x0f:
        flags_.i = true;
        break;
    case 0x10:
        registers_.a = sub8(registers_.a, registers_.b);
        break;
    case 0x11:
        cmp8(registers_.a, registers_.b);
        break;
    case 0x16:
        registers_.b = load_accumulator(registers_.a);
        break;
    case 0x17:
        registers_.a = load_accumulator(registers_.b);
        break;
    case 0x19: {
        const auto original = registers_.a;
        auto temporary = static_cast<unsigned>(original);
        if ((temporary & 0x0fU) >= 0x0aU || flags_.h) {
            temporary += 0x06U;
        }
        if ((temporary & 0xf0U) >= 0xa0U) {
            temporary += 0x60U;
        }
        const auto result = static_cast<std::uint8_t>(temporary);
        flags_.n = (result & 0x80) != 0;
        flags_.z = result == 0;
        flags_.v = (signed8(original) > 0 && flags_.n) ||
                   (signed8(original) < 0 && !flags_.n);
        flags_.c = (original & 0xf0) >= 0xa0 || flags_.c;
        registers_.a = result;
        break;
    }
    case 0x1b:
        registers_.a = add8(registers_.a, registers_.b);
        break;
    case 0x30:
        registers_.ix = static_cast<std::uint16_t>(registers_.sp + 1);
        break;
    case 0x31:
        registers_.sp = static_cast<std::uint16_t>(registers_.sp + 1);
        break;
    case 0x32:
        registers_.a = pull8();
        break;
    case 0x33:
        registers_.b = pull8();
        break;
    case 0x34:
        registers_.sp = static_cast<std::uint16_t>(registers_.sp - 1);
        break;
    case 0x35:
        registers_.sp = static_cast<std::uint16_t>(registers_.ix - 1);
        break;
    case 0x36:
        push8(registers_.a);
        break;
    case 0x37:
        push8(registers_.b);
        break;
    default:
        break;
    }
}

std::uint8_t Cpu::add8(std::uint8_t x, std::uint8_t y) {
    const auto result = static_cast<unsigned>(x) + static_cast<unsigned>(y);
    const auto value = static_cast<std::uint8_t>(result);
    flags_.h = ((x & 0x0f) + (y & 0x0f)) > 0x0f;
    flags_.n = (value & 0x80) != 0;
    flags_.z = value == 0;
    flags_.v = (signed8(x) > 0 && signed8(y) > 0 && flags_.n) ||
               (signed8(x) < 0 && signed8(y) < 0 && !flags_.n);
    flags_.c = result > 0xff;
    return value;
}

std::uint8_t Cpu::adc8(std::uint8_t x, std::uint8_t y) {
    const auto carry = flags_.c ? 1U : 0U;
    const auto result = static_cast<unsigned>(x) + static_cast<unsigned>(y) + carry;
    const auto value = static_cast<std::uint8_t>(result);
    flags_.h = static_cast<unsigned>(x & 0x0f) + static_cast<unsigned>(y & 0x0f) + carry >
               0x0f;
    flags_.n = (value & 0x80) != 0;
    flags_.z = value == 0;
    flags_.v = (signed8(x) > 0 && signed8(y) > 0 && flags_.n) ||
               (signed8(x) < 0 && signed8(y) < 0 && !flags_.n);
    flags_.c = result > 0xff;
    return value;
}

std::uint16_t Cpu::add16(std::uint16_t x, std::uint16_t y) {
    const auto result = static_cast<std::uint32_t>(x) + y;
    const auto value = static_cast<std::uint16_t>(result);
    flags_.n = signed16(value) < 0;
    flags_.z = value == 0;
    flags_.v = (signed16(x) > 0 && signed16(y) > 0 && flags_.n) ||
               (signed16(x) < 0 && signed16(y) < 0 && !flags_.n);
    flags_.c = result > 0xffff;
    return value;
}

std::uint8_t Cpu::sub8(std::uint8_t x, std::uint8_t y) {
    const auto result = static_cast<int>(x) - static_cast<int>(y);
    const auto value = static_cast<std::uint8_t>(result);
    flags_.n = (value & 0x80) != 0;
    flags_.z = value == 0;
    flags_.v = (signed8(x) > 0 && signed8(y) < 0 && flags_.n) ||
               (signed8(x) < 0 && signed8(y) > 0 && !flags_.n);
    flags_.c = (result & 0x100) != 0;
    return value;
}

std::uint8_t Cpu::sbc8(std::uint8_t x, std::uint8_t y) {
    const auto result = static_cast<int>(x) - static_cast<int>(y) - (flags_.c ? 1 : 0);
    const auto value = static_cast<std::uint8_t>(result);
    flags_.n = (value & 0x80) != 0;
    flags_.z = value == 0;
    flags_.v = (signed8(x) > 0 && signed8(y) < 0 && flags_.n) ||
               (signed8(x) < 0 && signed8(y) > 0 && !flags_.n);
    flags_.c = (result & 0x100) != 0;
    return value;
}

std::uint8_t Cpu::and8(std::uint8_t x, std::uint8_t y) {
    const auto result = static_cast<std::uint8_t>(x & y);
    flags_.n = (result & 0x80) != 0;
    flags_.z = result == 0;
    flags_.v = false;
    return result;
}

std::uint8_t Cpu::eor8(std::uint8_t x, std::uint8_t y) {
    const auto result = static_cast<std::uint8_t>(x ^ y);
    flags_.n = (result & 0x80) != 0;
    flags_.z = result == 0;
    flags_.v = false;
    return result;
}

std::uint8_t Cpu::ora8(std::uint8_t x, std::uint8_t y) {
    const auto result = static_cast<std::uint8_t>(x | y);
    flags_.n = (result & 0x80) != 0;
    flags_.z = result == 0;
    flags_.v = false;
    return result;
}

void Cpu::bit8(std::uint8_t x, std::uint8_t y) {
    const auto result = static_cast<std::uint8_t>(x & y);
    flags_.n = (result & 0x80) != 0;
    flags_.z = result == 0;
    flags_.v = false;
}

void Cpu::cmp8(std::uint8_t x, std::uint8_t y) {
    const auto result = static_cast<int>(x) - static_cast<int>(y);
    const auto value = static_cast<std::uint8_t>(result);
    flags_.n = (value & 0x80) != 0;
    flags_.z = value == 0;
    flags_.v = (signed8(x) > 0 && signed8(y) < 0 && flags_.n) ||
               (signed8(x) < 0 && signed8(y) > 0 && !flags_.n);
    flags_.c = (result & 0x100) != 0;
}

std::uint8_t Cpu::asl(std::uint8_t value) {
    const auto wide = static_cast<unsigned>(value) << 1U;
    const auto result = static_cast<std::uint8_t>(wide);
    flags_.n = (result & 0x80) != 0;
    flags_.z = result == 0;
    flags_.c = (wide & 0x100) != 0;
    flags_.v = flags_.n != flags_.c;
    return result;
}

std::uint8_t Cpu::asr(std::uint8_t value) {
    const auto result = static_cast<std::uint8_t>((value >> 1U) | (value & 0x80));
    flags_.n = (result & 0x80) != 0;
    flags_.z = result == 0;
    flags_.c = (value & 1) != 0;
    flags_.v = flags_.n != flags_.c;
    return result;
}

std::uint8_t Cpu::clear_value() {
    flags_.n = false;
    flags_.z = true;
    flags_.v = false;
    flags_.c = false;
    return 0;
}

std::uint8_t Cpu::complement(std::uint8_t value) {
    const auto result = static_cast<std::uint8_t>(~value);
    flags_.n = (result & 0x80) != 0;
    flags_.z = result == 0;
    flags_.v = false;
    flags_.c = true;
    return result;
}

std::uint8_t Cpu::decrement(std::uint8_t value) {
    const auto result = static_cast<std::uint8_t>(value - 1);
    flags_.n = (result & 0x80) != 0;
    flags_.z = result == 0;
    flags_.v = value == 0x80;
    return result;
}

std::uint8_t Cpu::increment(std::uint8_t value) {
    const auto result = static_cast<std::uint8_t>(value + 1);
    flags_.n = (result & 0x80) != 0;
    flags_.z = result == 0;
    flags_.v = value == 0x7f;
    return result;
}

std::uint8_t Cpu::load_accumulator(std::uint8_t value) {
    flags_.n = (value & 0x80) != 0;
    flags_.z = value == 0;
    flags_.v = false;
    return value;
}

std::uint8_t Cpu::lsr(std::uint8_t value) {
    const auto result = static_cast<std::uint8_t>(value >> 1U);
    flags_.n = false;
    flags_.z = result == 0;
    flags_.c = (value & 1) != 0;
    flags_.v = flags_.n != flags_.c;
    return result;
}

std::uint8_t Cpu::negate(std::uint8_t value) {
    const auto result = static_cast<std::uint8_t>(-static_cast<int>(value));
    flags_.n = (result & 0x80) != 0;
    flags_.z = result == 0;
    flags_.v = result == 0x80;
    flags_.c = value != 0;
    return result;
}

std::uint8_t Cpu::rol(std::uint8_t value) {
    const auto wide = (static_cast<unsigned>(value) << 1U) | (flags_.c ? 1U : 0U);
    const auto result = static_cast<std::uint8_t>(wide);
    flags_.n = (result & 0x80) != 0;
    flags_.z = result == 0;
    flags_.c = (wide & 0x100) != 0;
    flags_.v = flags_.n != flags_.c;
    return result;
}

std::uint8_t Cpu::ror(std::uint8_t value) {
    const auto result = static_cast<std::uint8_t>((value >> 1U) | (flags_.c ? 0x80 : 0));
    flags_.n = (result & 0x80) != 0;
    flags_.z = result == 0;
    flags_.c = (value & 1) != 0;
    flags_.v = flags_.n != flags_.c;
    return result;
}

void Cpu::store_accumulator(std::uint16_t address, std::uint8_t value) {
    flags_.n = (value & 0x80) != 0;
    flags_.z = value == 0;
    flags_.v = false;
    emulator_.store8(address, value);
}

void Cpu::test_value(std::uint8_t value) {
    flags_.n = (value & 0x80) != 0;
    flags_.z = value == 0;
    flags_.v = false;
    flags_.c = false;
}

void Cpu::compare_index(std::uint16_t value) {
    const auto difference = static_cast<std::uint16_t>(registers_.ix - value);
    flags_.n = signed16(difference) < 0;
    flags_.z = difference == 0;
    flags_.v = (signed16(registers_.ix) > 0 && signed16(value) < 0 && flags_.n) ||
               (signed16(registers_.ix) < 0 && signed16(value) > 0 && !flags_.n);
}

void Cpu::load_index(std::uint16_t value) {
    registers_.ix = value;
    flags_.n = signed16(value) < 0;
    flags_.z = value == 0;
    flags_.v = false;
}

void Cpu::load_stack(std::uint16_t value) {
    registers_.sp = value;
    flags_.n = signed16(value) < 0;
    flags_.z = value == 0;
    flags_.v = false;
}

void Cpu::store_index(std::uint16_t address) {
    emulator_.store16(address, registers_.ix);
    flags_.n = signed16(registers_.ix) < 0;
    flags_.z = registers_.ix == 0;
    flags_.v = false;
}

void Cpu::store_stack(std::uint16_t address) {
    emulator_.store16(address, registers_.sp);
    flags_.n = signed16(registers_.sp) < 0;
    flags_.z = registers_.sp == 0;
    flags_.v = false;
}

void Cpu::branch(std::uint8_t offset, bool condition) {
    if (condition) {
        registers_.pc = static_cast<std::uint16_t>(registers_.pc + signed8(offset));
    }
}

std::uint8_t Cpu::nim(std::uint8_t x, std::uint8_t y) {
    const auto result = static_cast<std::uint8_t>(x & y);
    flags_.z = result == 0;
    flags_.n = !flags_.z;
    flags_.v = false;
    return result;
}

std::uint8_t Cpu::oim(std::uint8_t x, std::uint8_t y) {
    const auto result = static_cast<std::uint8_t>(x | y);
    flags_.z = result == 0;
    flags_.n = !flags_.z;
    flags_.v = false;
    return result;
}

std::uint8_t Cpu::xim(std::uint8_t x, std::uint8_t y) {
    const auto result = static_cast<std::uint8_t>(x ^ y);
    flags_.z = result == 0;
    flags_.n = !flags_.z;
    return result;
}

void Cpu::tmm(std::uint8_t x, std::uint8_t y) {
    if (x == 0 || y == 0) {
        flags_.n = false;
        flags_.z = true;
        flags_.v = false;
    } else if (y == 0xff) {
        flags_.n = false;
        flags_.z = false;
        flags_.v = true;
    } else {
        flags_.n = true;
        flags_.z = false;
        flags_.v = false;
    }
}

}  // namespace jr100::detail
