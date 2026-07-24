"""M6800 Programming Reference Manual (M68PRM(D), Nov 1976) 準拠の修正検証。

一次資料で確認した3点:
- SWI は「SWI命令のアドレス + 1」（次命令アドレス）をスタックする（§3.3.3）
- ADC の H はキャリー入力を含む桁上がりで決まる（H = X3・M3 + M3・~R3 + ~R3・X3、
  R はキャリー入力込みの結果）
- STS の N/Z はストアした「スタックポインタ」から設定する（N = SPH7）
"""

from __future__ import annotations

from jr100emu.cpu.cpu import MB8861

from tests.unit.test_mb8861_basic import make_cpu


def test_swi_stacks_address_of_next_instruction() -> None:
    cpu = make_cpu()
    sp0 = cpu.registers.stack_pointer
    cpu.registers.program_counter = 0x2000
    cpu.memory.store8(0x2000, MB8861.OP_SWI_IMP)
    cpu.memory.store16(MB8861.VECTOR_SWI, 0x3000)

    cpu.execute(1)

    assert cpu.registers.program_counter == 0x3000
    assert cpu.memory.load16((sp0 - 1) & 0xFFFF) == 0x2001


def test_adc_half_carry_includes_carry_input() -> None:
    cpu = make_cpu()
    cpu.registers.program_counter = 0x2000
    cpu.registers.acc_a = 0x0F
    cpu.flags.carry_c = True
    cpu.memory.store8(0x2000, MB8861.OP_ADCA_IMM)
    cpu.memory.store8(0x2001, 0x00)

    cpu.execute(1)

    assert cpu.registers.acc_a == 0x10
    assert cpu.flags.carry_h is True


def test_adc_half_carry_clear_without_carry_input() -> None:
    cpu = make_cpu()
    cpu.registers.program_counter = 0x2000
    cpu.registers.acc_a = 0x0F
    cpu.flags.carry_c = False
    cpu.memory.store8(0x2000, MB8861.OP_ADCA_IMM)
    cpu.memory.store8(0x2001, 0x00)

    cpu.execute(1)

    assert cpu.registers.acc_a == 0x0F
    assert cpu.flags.carry_h is False


def test_sts_sets_negative_from_stack_pointer() -> None:
    cpu = make_cpu()
    cpu.registers.program_counter = 0x2000
    cpu.registers.stack_pointer = 0x8000
    cpu.registers.index = 0x0001
    cpu.memory.store8(0x2000, MB8861.OP_STS_EXT)
    cpu.memory.store16(0x2001, 0x0100)

    cpu.execute(1)

    assert cpu.memory.load16(0x0100) == 0x8000
    assert cpu.flags.carry_n is True
    assert cpu.flags.carry_z is False
    assert cpu.flags.carry_v is False


def test_sts_sets_zero_from_stack_pointer() -> None:
    cpu = make_cpu()
    cpu.registers.program_counter = 0x2000
    cpu.registers.stack_pointer = 0x0000
    cpu.registers.index = 0x1234
    cpu.memory.store8(0x2000, MB8861.OP_STS_EXT)
    cpu.memory.store16(0x2001, 0x0100)

    cpu.execute(1)

    assert cpu.flags.carry_z is True
    assert cpu.flags.carry_n is False
