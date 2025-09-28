from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

import pytest

from jr100emu.cpu.cpu import MB8861
from jr100emu.memory import MemorySystem, RAM

PROGRAM_START = 0x0200
STACK_START = 0x01FF

Instruction = Tuple[int, Sequence[int]]


def _make_cpu() -> Tuple[MB8861, MemorySystem]:
    memory = MemorySystem()
    memory.allocate_space(0x10000)
    memory.register_memory(RAM(0x0000, 0x10000))

    class DummyComputer:
        def __init__(self, mem: MemorySystem) -> None:
            self.hardware = type("Hardware", (), {"memory": mem})()
            self.clock_count = 0

    cpu = MB8861(DummyComputer(memory))
    cpu.registers.program_counter = PROGRAM_START
    cpu.registers.stack_pointer = STACK_START
    return cpu, memory


def _assemble(program: Iterable[Instruction]) -> List[int]:
    bytes_out: List[int] = []
    for opcode, operands in program:
        bytes_out.append(opcode)
        bytes_out.extend(int(value) & 0xFF for value in operands)
    return bytes_out


def _write_bytes(memory: MemorySystem, address: int, data: Iterable[int]) -> None:
    for offset, byte in enumerate(data):
        memory.store8(address + offset, int(byte) & 0xFF)


def _run_program(cpu: MB8861, memory: MemorySystem, program: Sequence[Instruction]) -> None:
    cpu.registers.program_counter = PROGRAM_START
    assembled = _assemble(program)
    _write_bytes(memory, PROGRAM_START, assembled)
    total_cycles = sum(cpu._opcode_table[opcode][1] for opcode, _ in program)  # type: ignore[attr-defined]
    cpu.execute(total_cycles)


def test_push_pull_roundtrip() -> None:
    cpu, memory = _make_cpu()
    cpu.registers.acc_a = 0x12
    cpu.registers.acc_b = 0x34
    program: Sequence[Instruction] = (
        (MB8861.OP_PSHA_IMP, ()),
        (MB8861.OP_PSHB_IMP, ()),
        (MB8861.OP_PULA_IMP, ()),
        (MB8861.OP_PULB_IMP, ()),
    )
    _run_program(cpu, memory, program)
    assert cpu.registers.stack_pointer == STACK_START
    assert cpu.registers.acc_a == 0x34
    assert cpu.registers.acc_b == 0x12
    assert memory.load8(STACK_START) == 0x12
    assert memory.load8(STACK_START - 1) == 0x34


@pytest.mark.parametrize(
    "opcode,value,carry_in,expected,carry_out,overflow",
    [
        (MB8861.OP_ASLA_IMP, 0x81, False, 0x02, True, True),
        (MB8861.OP_ASRA_IMP, 0x81, False, 0xC0, True, False),
        (MB8861.OP_ROLA_IMP, 0x10, True, 0x21, False, False),
        (MB8861.OP_RORA_IMP, 0x02, True, 0x81, False, True),
    ],
)
def test_shift_rotate_accumulator_flags(
    opcode: int, value: int, carry_in: bool, expected: int, carry_out: bool, overflow: bool
) -> None:
    cpu, memory = _make_cpu()
    cpu.registers.acc_a = value & 0xFF
    cpu.flags.carry_c = carry_in
    program: Sequence[Instruction] = ((opcode, ()),)
    _run_program(cpu, memory, program)
    assert cpu.registers.acc_a == expected
    assert cpu.flags.carry_c is carry_out
    assert cpu.flags.carry_v is overflow


def test_shift_rotate_register_b() -> None:
    cpu, memory = _make_cpu()
    cpu.registers.acc_b = 0x40
    cpu.flags.carry_c = True
    program: Sequence[Instruction] = (
        (MB8861.OP_ROLB_IMP, ()),
        (MB8861.OP_RORB_IMP, ()),
        (MB8861.OP_ASLB_IMP, ()),
        (MB8861.OP_ASRB_IMP, ()),
    )
    _run_program(cpu, memory, program)
    assert cpu.registers.acc_b == 0xC0
    assert cpu.flags.carry_c is False
    assert cpu.flags.carry_n is True
    assert cpu.flags.carry_v is True


def test_memory_shift_ext() -> None:
    cpu, memory = _make_cpu()
    data_address = 0x4000
    memory.store8(data_address, 0x81)
    program: Sequence[Instruction] = ((MB8861.OP_ASL_EXT, (data_address >> 8, data_address & 0xFF)),)
    _run_program(cpu, memory, program)
    assert memory.load8(data_address) == 0x02
    assert cpu.flags.carry_c is True
    assert cpu.flags.carry_v is True


def test_memory_negate_indexed() -> None:
    cpu, memory = _make_cpu()
    cpu.registers.index = 0x5000
    offset = 0x10
    target = (cpu.registers.index + offset) & 0xFFFF
    memory.store8(target, 0x55)
    program: Sequence[Instruction] = ((MB8861.OP_NEG_IND, (offset,)),)
    _run_program(cpu, memory, program)
    assert memory.load8(target) == 0xAB
    assert cpu.flags.carry_c is False
    assert cpu.flags.carry_n is True


def test_flag_control_instructions() -> None:
    cpu, memory = _make_cpu()
    cpu.flags.carry_c = False
    cpu.flags.carry_i = False
    cpu.flags.carry_v = False
    program: Sequence[Instruction] = (
        (MB8861.OP_SEC_IMP, ()),
        (MB8861.OP_SEI_IMP, ()),
        (MB8861.OP_SEV_IMP, ()),
        (MB8861.OP_CLC_IMP, ()),
        (MB8861.OP_CLI_IMP, ()),
        (MB8861.OP_CLV_IMP, ()),
    )
    _run_program(cpu, memory, program)
    assert cpu.flags.carry_c is False
    assert cpu.flags.carry_i is False
    assert cpu.flags.carry_v is False


def test_tap_tpa_roundtrip() -> None:
    cpu, memory = _make_cpu()
    cpu.flags.carry_h = True
    cpu.flags.carry_i = False
    cpu.flags.carry_n = True
    cpu.flags.carry_z = False
    cpu.flags.carry_v = True
    cpu.flags.carry_c = False
    _run_program(cpu, memory, ((MB8861.OP_TPA_IMP, ()),))
    captured = cpu.registers.acc_a & 0xFF

    cpu.flags.carry_h = False
    cpu.flags.carry_i = True
    cpu.flags.carry_n = False
    cpu.flags.carry_z = True
    cpu.flags.carry_v = False
    cpu.flags.carry_c = True
    cpu.registers.acc_a = captured

    _run_program(cpu, memory, ((MB8861.OP_TAP_IMP, ()),))
    assert cpu.flags.carry_h is True
    assert cpu.flags.carry_i is False
    assert cpu.flags.carry_n is True
    assert cpu.flags.carry_z is False
    assert cpu.flags.carry_v is True
    assert cpu.flags.carry_c is False


def test_tst_ext_clears_carry() -> None:
    cpu, memory = _make_cpu()
    data_address = 0x6000
    memory.store8(data_address, 0x7F)
    cpu.flags.carry_c = True
    program: Sequence[Instruction] = ((MB8861.OP_TST_EXT, (data_address >> 8, data_address & 0xFF)),)
    _run_program(cpu, memory, program)
    assert cpu.flags.carry_c is False
    assert cpu.flags.carry_z is False
    assert cpu.flags.carry_n is False


def test_clr_ext_sets_zero_and_flags() -> None:
    cpu, memory = _make_cpu()
    data_address = 0x7000
    memory.store8(data_address, 0xFF)
    program: Sequence[Instruction] = ((MB8861.OP_CLR_EXT, (data_address >> 8, data_address & 0xFF)),)
    _run_program(cpu, memory, program)
    assert memory.load8(data_address) == 0x00
    assert cpu.flags.carry_z is True
    assert cpu.flags.carry_n is False
    assert cpu.flags.carry_c is False


def test_save_load_state_round_trip() -> None:
    cpu, memory = _make_cpu()
    cpu.registers.acc_a = 0xAA
    cpu.registers.acc_b = 0x55
    cpu.registers.index = 0x2345
    cpu.registers.stack_pointer = 0x01F0
    cpu.registers.program_counter = 0x4000
    cpu.flags.carry_h = True
    cpu.flags.carry_i = True
    cpu.flags.carry_n = False
    cpu.flags.carry_z = True
    cpu.flags.carry_v = False
    cpu.flags.carry_c = True
    cpu.status.reset_requested = True
    cpu.status.nmi_requested = True
    cpu.status.irq_requested = False
    cpu.status.halt_requested = True
    cpu.status.halt_processed = True
    cpu.status.fetch_wai = True

    snapshot: dict[str, object] = {}
    cpu.save_state(snapshot)

    # mutate CPU to ensure load restores values
    cpu.registers.acc_a = 0
    cpu.registers.acc_b = 0
    cpu.registers.index = 0
    cpu.registers.stack_pointer = STACK_START
    cpu.registers.program_counter = PROGRAM_START
    cpu.flags.carry_h = False
    cpu.flags.carry_i = False
    cpu.flags.carry_n = True
    cpu.flags.carry_z = False
    cpu.flags.carry_v = True
    cpu.flags.carry_c = False
    cpu.status.reset_requested = False
    cpu.status.nmi_requested = False
    cpu.status.irq_requested = True
    cpu.status.halt_requested = False
    cpu.status.halt_processed = False
    cpu.status.fetch_wai = False

    cpu.load_state(snapshot)

    assert cpu.registers.acc_a == 0xAA
    assert cpu.registers.acc_b == 0x55
    assert cpu.registers.index == 0x2345
    assert cpu.registers.stack_pointer == 0x01F0
    assert cpu.registers.program_counter == 0x4000
    assert cpu.flags.carry_h is True
    assert cpu.flags.carry_i is True
    assert cpu.flags.carry_n is False
    assert cpu.flags.carry_z is True
    assert cpu.flags.carry_v is False
    assert cpu.flags.carry_c is True
    assert cpu.status.reset_requested is True
    assert cpu.status.nmi_requested is True
    assert cpu.status.irq_requested is False
    assert cpu.status.halt_requested is True
    assert cpu.status.halt_processed is True
    assert cpu.status.fetch_wai is True
