"""MB8861 CPU 基本テスト。Java版の命令挙動を段階的に検証する。"""

from __future__ import annotations

from dataclasses import dataclass

from jr100emu.cpu.cpu import MB8861


@dataclass
class DummyMemory:
    data: bytearray

    def load8(self, address: int) -> int:
        return self.data[address & 0xFFFF]

    def load16(self, address: int) -> int:
        hi = self.load8(address)
        lo = self.load8(address + 1)
        return ((hi << 8) | lo) & 0xFFFF

    def store8(self, address: int, value: int) -> None:
        self.data[address & 0xFFFF] = value & 0xFF

    def store16(self, address: int, value: int) -> None:
        self.store8(address, (value >> 8) & 0xFF)
        self.store8(address + 1, value & 0xFF)


@dataclass
class DummyHardware:
    memory: DummyMemory


@dataclass
class DummyComputer:
    hardware: DummyHardware
    clock_count: int = 0


def make_cpu() -> MB8861:
    memory = DummyMemory(bytearray(0x10000))
    hardware = DummyHardware(memory)
    computer = DummyComputer(hardware)
    cpu = MB8861(computer)
    cpu.registers.stack_pointer = 0x01FF
    return cpu


def test_adda_immediate_updates_flags_and_register() -> None:
    cpu = make_cpu()
    cpu.registers.acc_a = 0x14
    cpu.memory.store8(0x0000, MB8861.OP_ADDA_IMM)
    cpu.memory.store8(0x0001, 0x22)
    cpu.registers.program_counter = 0x0000

    cpu.execute(2)

    assert cpu.registers.acc_a == 0x36
    assert cpu.flags.carry_c is False
    assert cpu.flags.carry_z is False
    assert cpu.flags.carry_n is False


def test_aba_sets_half_carry_and_carry() -> None:
    cpu = make_cpu()
    cpu.registers.acc_a = 0x8F
    cpu.registers.acc_b = 0x81
    cpu.memory.store8(0x0000, MB8861.OP_ABA_IMP)
    cpu.registers.program_counter = 0x0000

    cpu.execute(2)

    assert cpu.registers.acc_a == 0x10
    assert cpu.flags.carry_h is True
    assert cpu.flags.carry_c is True
    assert cpu.flags.carry_z is False


def test_rti_pops_state_from_stack() -> None:
    cpu = make_cpu()
    cpu.registers.stack_pointer = 0x01E9
    cpu.memory.store8(0x0000, MB8861.OP_RTI_IMP)
    cpu.memory.store8(0x01EA, 0x3F)  # CCR flags
    cpu.memory.store8(0x01EB, 0xAD)  # B
    cpu.memory.store8(0x01EC, 0xEF)  # A
    cpu.memory.store8(0x01ED, 0xBE)  # IX high
    cpu.memory.store8(0x01EE, 0xEF)  # IX low
    cpu.memory.store8(0x01EF, 0xDE)  # PC high
    cpu.memory.store8(0x01F0, 0xAD)  # PC low
    cpu.registers.program_counter = 0x0000

    cpu.execute(10)

    assert cpu.registers.program_counter == 0xDEAD
    assert cpu.registers.index == 0xBEEF
    assert cpu.registers.acc_a == 0xEF
    assert cpu.registers.acc_b == 0xAD
    assert cpu.flags.carry_c is True


def test_adcb_uses_existing_carry_flag() -> None:
    cpu = make_cpu()
    cpu.registers.acc_b = 0x10
    cpu.flags.carry_c = True
    cpu.memory.store8(0x0000, MB8861.OP_ADCB_IMM)
    cpu.memory.store8(0x0001, 0x01)
    cpu.registers.program_counter = 0x0000

    cpu.execute(2)

    assert cpu.registers.acc_b == 0x12
    assert cpu.flags.carry_c is False


def test_sbca_sets_borrow_flag() -> None:
    cpu = make_cpu()
    cpu.registers.acc_a = 0x10
    cpu.flags.carry_c = False
    cpu.memory.store8(0x0000, MB8861.OP_SBCA_IMM)
    cpu.memory.store8(0x0001, 0x11)
    cpu.registers.program_counter = 0x0000

    cpu.execute(2)

    assert cpu.registers.acc_a == 0xFF
    assert cpu.flags.carry_c is True
    assert cpu.flags.carry_n is True


def test_anda_clears_v_and_preserves_carry() -> None:
    cpu = make_cpu()
    cpu.registers.acc_a = 0xF0
    cpu.flags.carry_c = True
    cpu.memory.store8(0x0000, MB8861.OP_ANDA_IMM)
    cpu.memory.store8(0x0001, 0x0F)
    cpu.registers.program_counter = 0x0000

    cpu.execute(2)

    assert cpu.registers.acc_a == 0x00
    assert cpu.flags.carry_z is True
    assert cpu.flags.carry_v is False
    assert cpu.flags.carry_c is True


def test_clrb_sets_zero_and_clears_carry() -> None:
    cpu = make_cpu()
    cpu.registers.acc_b = 0x33
    cpu.memory.store8(0x0000, MB8861.OP_CLRB_IMP)
    cpu.registers.program_counter = 0x0000

    cpu.execute(2)

    assert cpu.registers.acc_b == 0
    assert cpu.flags.carry_z is True
    assert cpu.flags.carry_c is False


def test_daa_matches_java_logic() -> None:
    cpu = make_cpu()
    cpu.registers.acc_a = 0xA5
    cpu.flags.carry_h = False
    cpu.memory.store8(0x0000, MB8861.OP_DAA_IMP)
    cpu.registers.program_counter = 0x0000

    cpu.execute(2)

    assert cpu.registers.acc_a == 0x05
    assert cpu.flags.carry_c is True


def test_orab_ext_preserves_java_bug_behavior() -> None:
    cpu = make_cpu()
    cpu.registers.acc_b = 0x10
    cpu.memory.store8(0x0000, MB8861.OP_ORAB_EXT)
    cpu.memory.store8(0x0001, 0x12)
    cpu.memory.store8(0x0002, 0x34)
    cpu.memory.store8(0x1234, 0x20)
    cpu.registers.program_counter = 0x0000

    cpu.execute(4)

    assert cpu.registers.acc_b == 0x30
    assert cpu.flags.carry_c is False


def test_staa_direct_updates_memory_and_flags() -> None:
    cpu = make_cpu()
    cpu.registers.acc_a = 0x80
    cpu.memory.store8(0x0000, MB8861.OP_STAA_DIR)
    cpu.memory.store8(0x0001, 0x40)
    cpu.registers.program_counter = 0x0000

    cpu.execute(4)

    assert cpu.memory.load8(0x0040) == 0x80
    assert cpu.flags.carry_n is True
    assert cpu.flags.carry_z is False
    assert cpu.flags.carry_v is False


def test_ldx_immediate_sets_sign_flag() -> None:
    cpu = make_cpu()
    cpu.memory.store8(0x0000, MB8861.OP_LDX_IMM)
    cpu.memory.store8(0x0001, 0x80)
    cpu.memory.store8(0x0002, 0x00)
    cpu.registers.program_counter = 0x0000

    cpu.execute(3)

    assert cpu.registers.index == 0x8000
    assert cpu.flags.carry_n is True
    assert cpu.flags.carry_z is False


def test_cpx_direct_sets_negative_flag() -> None:
    cpu = make_cpu()
    cpu.registers.index = 0x1200
    cpu.memory.store8(0x0010, 0x12)
    cpu.memory.store8(0x0011, 0x10)
    cpu.memory.store8(0x0000, MB8861.OP_CPX_DIR)
    cpu.memory.store8(0x0001, 0x10)
    cpu.registers.program_counter = 0x0000

    cpu.execute(4)

    assert cpu.flags.carry_n is True
    assert cpu.flags.carry_z is False


def test_stx_ext_writes_word() -> None:
    cpu = make_cpu()
    cpu.registers.index = 0x7FFF
    cpu.memory.store8(0x0000, MB8861.OP_STX_EXT)
    cpu.memory.store8(0x0001, 0x20)
    cpu.memory.store8(0x0002, 0x00)
    cpu.registers.program_counter = 0x0000

    cpu.execute(6)

    assert cpu.memory.load16(0x2000) == 0x7FFF
    assert cpu.flags.carry_n is False
    assert cpu.flags.carry_z is False


def test_sts_ext_uses_ix_for_flags() -> None:
    cpu = make_cpu()
    cpu.registers.index = 0xFFFF
    cpu.registers.stack_pointer = 0x2000
    cpu.memory.store8(0x0000, MB8861.OP_STS_EXT)
    cpu.memory.store8(0x0001, 0x20)
    cpu.memory.store8(0x0002, 0x10)
    cpu.registers.program_counter = 0x0000

    cpu.execute(6)

    assert cpu.memory.load16(0x2010) == 0x2000
    assert cpu.flags.carry_n is True
    assert cpu.flags.carry_z is False


def test_txs_tsx_roundtrip() -> None:
    cpu = make_cpu()
    cpu.registers.index = 0x1234
    cpu.memory.store8(0x0000, MB8861.OP_TXS_IMP)
    cpu.memory.store8(0x0001, MB8861.OP_TSX_IMP)
    cpu.registers.program_counter = 0x0000

    cpu.execute(8)

    assert cpu.registers.stack_pointer == 0x1233
    assert cpu.registers.index == 0x1234


def test_beq_branches_when_zero_set() -> None:
    cpu = make_cpu()
    cpu.flags.carry_z = True
    cpu.memory.store8(0x0000, MB8861.OP_BEQ_REL)
    cpu.memory.store8(0x0001, 0x02)
    cpu.registers.program_counter = 0x0000

    cpu.execute(4)

    assert cpu.registers.program_counter == 0x0004


def test_bne_skips_when_zero_set() -> None:
    cpu = make_cpu()
    cpu.flags.carry_z = True
    cpu.memory.store8(0x0000, MB8861.OP_BNE_REL)
    cpu.memory.store8(0x0001, 0x02)
    cpu.registers.program_counter = 0x0000

    cpu.execute(4)

    assert cpu.registers.program_counter == 0x0002


def test_bsr_pushes_return_address() -> None:
    cpu = make_cpu()
    cpu.registers.stack_pointer = 0x0200
    cpu.memory.store8(0x0000, MB8861.OP_BSR_REL)
    cpu.memory.store8(0x0001, 0x02)
    cpu.registers.program_counter = 0x0000

    cpu.execute(8)

    assert cpu.registers.program_counter == 0x0004
    return_addr = cpu.memory.load16(0x01FF)
    assert return_addr == 0x0002


def test_jsr_ext_pushes_and_jumps() -> None:
    cpu = make_cpu()
    cpu.registers.stack_pointer = 0x0200
    cpu.memory.store8(0x0000, MB8861.OP_JSR_EXT)
    cpu.memory.store8(0x0001, 0x12)
    cpu.memory.store8(0x0002, 0x34)
    cpu.registers.program_counter = 0x0000

    cpu.execute(9)

    assert cpu.registers.program_counter == 0x1234
    assert cpu.memory.load16(0x01FF) == 0x0003


def test_jmp_indirect_uses_index() -> None:
    cpu = make_cpu()
    cpu.registers.index = 0x0100
    cpu.memory.store8(0x0105, 0x56)
    cpu.memory.store8(0x0106, 0x78)
    cpu.memory.store8(0x0000, MB8861.OP_JMP_IND)
    cpu.memory.store8(0x0001, 0x05)
    cpu.registers.program_counter = 0x0000

    cpu.execute(4)

    assert cpu.registers.program_counter == 0x5678


def test_adx_immediate_updates_ix_and_flags() -> None:
    cpu = make_cpu()
    cpu.registers.index = 0x7FFF
    cpu.memory.store8(0x0000, MB8861.OP_ADX_IMM)
    cpu.memory.store8(0x0001, 0x01)
    cpu.registers.program_counter = 0x0000

    cpu.execute(3)

    assert cpu.registers.index == 0x8000
    assert cpu.flags.carry_n is True
    assert cpu.flags.carry_z is False
    assert cpu.flags.carry_v is True
    assert cpu.flags.carry_c is False


def test_adx_immediate_sets_carry_and_zero() -> None:
    cpu = make_cpu()
    cpu.registers.index = 0xFFFF
    cpu.memory.store8(0x0000, MB8861.OP_ADX_IMM)
    cpu.memory.store8(0x0001, 0x01)
    cpu.registers.program_counter = 0x0000

    cpu.execute(3)

    assert cpu.registers.index == 0x0000
    assert cpu.flags.carry_c is True
    assert cpu.flags.carry_z is True
    assert cpu.flags.carry_n is False


def test_adx_ext_adds_16bit_value() -> None:
    cpu = make_cpu()
    cpu.registers.index = 0x1000
    cpu.memory.store8(0x0000, MB8861.OP_ADX_EXT)
    cpu.memory.store8(0x0001, 0x20)
    cpu.memory.store8(0x0002, 0x00)
    cpu.memory.store8(0x2000, 0x10)
    cpu.memory.store8(0x2001, 0x10)
    cpu.registers.program_counter = 0x0000

    cpu.execute(7)

    assert cpu.registers.index == 0x2010
    assert cpu.flags.carry_n is False
    assert cpu.flags.carry_z is False


def test_nim_ind_clears_bits() -> None:
    cpu = make_cpu()
    cpu.registers.index = 0x0300
    cpu.memory.store8(0x0305, 0xF0)
    cpu.memory.store8(0x0000, MB8861.OP_NIM_IND)
    cpu.memory.store8(0x0001, 0x0F)
    cpu.memory.store8(0x0002, 0x05)
    cpu.registers.program_counter = 0x0000

    cpu.execute(8)

    assert cpu.memory.load8(0x0305) == 0x00
    assert cpu.flags.carry_z is True
    assert cpu.flags.carry_n is False
    assert cpu.flags.carry_v is False


def test_oim_ind_sets_bits() -> None:
    cpu = make_cpu()
    cpu.registers.index = 0x0400
    cpu.memory.store8(0x0403, 0x0F)
    cpu.memory.store8(0x0000, MB8861.OP_OIM_IND)
    cpu.memory.store8(0x0001, 0xF0)
    cpu.memory.store8(0x0002, 0x03)
    cpu.registers.program_counter = 0x0000

    cpu.execute(8)

    assert cpu.memory.load8(0x0403) == 0xFF
    assert cpu.flags.carry_z is False
    assert cpu.flags.carry_n is True
    assert cpu.flags.carry_v is False


def test_xim_ind_toggles_bits_and_keeps_cv() -> None:
    cpu = make_cpu()
    cpu.registers.index = 0x0500
    cpu.flags.carry_v = True
    cpu.memory.store8(0x0501, 0xAA)
    cpu.memory.store8(0x0000, MB8861.OP_XIM_IND)
    cpu.memory.store8(0x0001, 0xFF)
    cpu.memory.store8(0x0002, 0x01)
    cpu.registers.program_counter = 0x0000

    cpu.execute(8)

    assert cpu.memory.load8(0x0501) == 0x55
    assert cpu.flags.carry_z is False
    assert cpu.flags.carry_n is True
    assert cpu.flags.carry_v is True


def test_tmm_sets_flags_per_case() -> None:
    cpu = make_cpu()
    cpu.registers.index = 0x0600
    cpu.memory.store8(0x0000, MB8861.OP_TMM_IND)
    cpu.memory.store8(0x0001, 0x00)
    cpu.memory.store8(0x0002, 0x02)
    cpu.memory.store8(0x0602, 0x55)
    cpu.registers.program_counter = 0x0000

    cpu.execute(7)

    assert cpu.flags.carry_z is True
    assert cpu.flags.carry_n is False
    assert cpu.flags.carry_v is False

    # y == 0xFF case
    cpu.memory.store8(0x0000, MB8861.OP_TMM_IND)
    cpu.memory.store8(0x0001, 0x01)
    cpu.memory.store8(0x0002, 0x03)
    cpu.memory.store8(0x0603, 0xFF)
    cpu.registers.program_counter = 0x0000

    cpu.execute(7)

    assert cpu.flags.carry_z is False
    assert cpu.flags.carry_n is False
    assert cpu.flags.carry_v is True

    # default branch
    cpu.memory.store8(0x0000, MB8861.OP_TMM_IND)
    cpu.memory.store8(0x0001, 0x01)
    cpu.memory.store8(0x0002, 0x04)
    cpu.memory.store8(0x0604, 0x01)
    cpu.registers.program_counter = 0x0000

    cpu.execute(7)

    assert cpu.flags.carry_n is True
    assert cpu.flags.carry_z is False
    assert cpu.flags.carry_v is False
