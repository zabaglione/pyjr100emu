"""CPU abstractions and MB8861 implementation port scaffolding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Callable


@dataclass
class CPURegisters:
    """Register file matching MB8861 layout."""

    acc_a: int = 0
    acc_b: int = 0
    index: int = 0
    stack_pointer: int = 0
    program_counter: int = 0


@dataclass
class CPUFlags:
    carry_h: bool = False
    carry_i: bool = False
    carry_n: bool = False
    carry_z: bool = False
    carry_v: bool = False
    carry_c: bool = False


@dataclass
class CPUStatus:
    reset_requested: bool = False
    nmi_requested: bool = False
    irq_requested: bool = False
    halt_requested: bool = False
    halt_processed: bool = False
    fetch_wai: bool = False


class CPU:
    """Abstract CPU base class mirroring jp.asamomiji.emulator.CPU."""

    def __init__(self, computer: object) -> None:
        self.computer = computer

    def reset(self) -> None:
        raise NotImplementedError

    def halt(self) -> None:
        raise NotImplementedError

    def nmi(self) -> None:
        raise NotImplementedError

    def irq(self) -> None:
        raise NotImplementedError

    def execute(self, clocks: int) -> int:
        raise NotImplementedError


class MB8861(CPU):
    """MB8861 CPU core ported from the Java implementation."""

    VECTOR_IRQ = 0xFFF8
    VECTOR_SWI = 0xFFFA
    VECTOR_NMI = 0xFFFC
    VECTOR_RESTART = 0xFFFE

    OP_RTI_IMP = 0x3B
    OP_RTS_IMP = 0x39
    OP_SWI_IMP = 0x3F
    OP_WAI_IMP = 0x3E
    OP_ABA_IMP = 0x1B
    OP_ADDA_IMM = 0x8B
    OP_ADDA_DIR = 0x9B
    OP_ADDA_IND = 0xAB
    OP_ADDA_EXT = 0xBB
    OP_ADDB_IMM = 0xCB
    OP_ADDB_DIR = 0xDB
    OP_ADDB_IND = 0xEB
    OP_ADDB_EXT = 0xFB
    OP_ADCA_IMM = 0x89
    OP_ADCA_DIR = 0x99
    OP_ADCA_IND = 0xA9
    OP_ADCA_EXT = 0xB9
    OP_ADCB_IMM = 0xC9
    OP_ADCB_DIR = 0xD9
    OP_ADCB_IND = 0xE9
    OP_ADCB_EXT = 0xF9
    OP_ANDA_IMM = 0x84
    OP_ANDA_DIR = 0x94
    OP_ANDA_IND = 0xA4
    OP_ANDA_EXT = 0xB4
    OP_ANDB_IMM = 0xC4
    OP_ANDB_DIR = 0xD4
    OP_ANDB_IND = 0xE4
    OP_ANDB_EXT = 0xF4
    OP_BITA_IMM = 0x85
    OP_BITA_DIR = 0x95
    OP_BITA_IND = 0xA5
    OP_BITA_EXT = 0xB5
    OP_BITB_IMM = 0xC5
    OP_BITB_DIR = 0xD5
    OP_BITB_IND = 0xE5
    OP_BITB_EXT = 0xF5
    OP_CBA_IMP = 0x11
    OP_CLRA_IMP = 0x4F
    OP_CLRB_IMP = 0x5F
    OP_CMPA_IMM = 0x81
    OP_CMPA_DIR = 0x91
    OP_CMPA_IND = 0xA1
    OP_CMPA_EXT = 0xB1
    OP_CMPB_IMM = 0xC1
    OP_CMPB_DIR = 0xD1
    OP_CMPB_IND = 0xE1
    OP_CMPB_EXT = 0xF1
    OP_COMA_IMP = 0x43
    OP_COMB_IMP = 0x53
    OP_DAA_IMP = 0x19
    OP_DECA_IMP = 0x4A
    OP_DECB_IMP = 0x5A
    OP_EORA_IMM = 0x88
    OP_EORA_DIR = 0x98
    OP_EORA_IND = 0xA8
    OP_EORA_EXT = 0xB8
    OP_EORB_IMM = 0xC8
    OP_EORB_DIR = 0xD8
    OP_EORB_IND = 0xE8
    OP_EORB_EXT = 0xF8
    OP_INCA_IMP = 0x4C
    OP_INCB_IMP = 0x5C
    OP_LDAA_IMM = 0x86
    OP_LDAA_DIR = 0x96
    OP_LDAA_IND = 0xA6
    OP_LDAA_EXT = 0xB6
    OP_LDAB_IMM = 0xC6
    OP_LDAB_DIR = 0xD6
    OP_LDAB_IND = 0xE6
    OP_LDAB_EXT = 0xF6
    OP_LSRA_IMP = 0x44
    OP_LSRB_IMP = 0x54
    OP_NEGA_IMP = 0x40
    OP_NEGB_IMP = 0x50
    OP_ORAA_IMM = 0x8A
    OP_ORAA_DIR = 0x9A
    OP_ORAA_IND = 0xAA
    OP_ORAA_EXT = 0xBA
    OP_ORAB_IMM = 0xCA
    OP_ORAB_DIR = 0xDA
    OP_ORAB_IND = 0xEA
    OP_ORAB_EXT = 0xFA
    OP_STAA_DIR = 0x97
    OP_STAA_IND = 0xA7
    OP_STAA_EXT = 0xB7
    OP_STAB_DIR = 0xD7
    OP_STAB_IND = 0xE7
    OP_STAB_EXT = 0xF7
    OP_SBA_IMP = 0x10
    OP_SUBA_IMM = 0x80
    OP_SUBA_DIR = 0x90
    OP_SUBA_IND = 0xA0
    OP_SUBA_EXT = 0xB0
    OP_SUBB_IMM = 0xC0
    OP_SUBB_DIR = 0xD0
    OP_SUBB_IND = 0xE0
    OP_SUBB_EXT = 0xF0
    OP_SBCA_IMM = 0x82
    OP_SBCA_DIR = 0x92
    OP_SBCA_IND = 0xA2
    OP_SBCA_EXT = 0xB2
    OP_SBCB_IMM = 0xC2
    OP_SBCB_DIR = 0xD2
    OP_SBCB_IND = 0xE2
    OP_SBCB_EXT = 0xF2
    OP_TAB_IMP = 0x16
    OP_TBA_IMP = 0x17
    OP_TSTA_IMP = 0x4D
    OP_TSTB_IMP = 0x5D
    OP_CPX_IMM = 0x8C
    OP_CPX_DIR = 0x9C
    OP_CPX_IND = 0xAC
    OP_CPX_EXT = 0xBC
    OP_DEX_IMP = 0x09
    OP_DES_IMP = 0x34
    OP_INX_IMP = 0x08
    OP_INS_IMP = 0x31
    OP_LDX_IMM = 0xCE
    OP_LDX_DIR = 0xDE
    OP_LDX_IND = 0xEE
    OP_LDX_EXT = 0xFE
    OP_LDS_IMM = 0x8E
    OP_LDS_DIR = 0x9E
    OP_LDS_IND = 0xAE
    OP_LDS_EXT = 0xBE
    OP_STX_DIR = 0xDF
    OP_STX_IND = 0xEF
    OP_STX_EXT = 0xFF
    OP_STS_DIR = 0x9F
    OP_STS_IND = 0xAF
    OP_STS_EXT = 0xBF
    OP_TXS_IMP = 0x35
    OP_TSX_IMP = 0x30
    OP_NOP_IMP = 0x01
    OP_ADX_IMM = 0xEC
    OP_ADX_EXT = 0xFC
    OP_BRA_REL = 0x20
    OP_BCC_REL = 0x24
    OP_BCS_REL = 0x25
    OP_BEQ_REL = 0x27
    OP_BGE_REL = 0x2C
    OP_BGT_REL = 0x2E
    OP_BHI_REL = 0x22
    OP_BLE_REL = 0x2F
    OP_BLS_REL = 0x23
    OP_BLT_REL = 0x2D
    OP_BMI_REL = 0x2B
    OP_BNE_REL = 0x26
    OP_BVC_REL = 0x28
    OP_BVS_REL = 0x29
    OP_BPL_REL = 0x2A
    OP_BSR_REL = 0x8D
    OP_JMP_IND = 0x6E
    OP_JMP_EXT = 0x7E
    OP_JSR_IND = 0xAD
    OP_JSR_EXT = 0xBD
    OP_NIM_IND = 0x71
    OP_OIM_IND = 0x72
    OP_XIM_IND = 0x75
    OP_TMM_IND = 0x7B

    def __init__(self, computer: object) -> None:
        super().__init__(computer)
        self.registers = CPURegisters()
        self.flags = CPUFlags()
        self.status = CPUStatus()
        self.memory = self._resolve_memory()
        self._opcode_table: Dict[int, Tuple[Callable[[], None], int]] = {}
        self._init_opcode_table()

    def _resolve_memory(self) -> Optional[object]:
        hardware = getattr(self.computer, "hardware", None)
        if hardware is None:
            return None
        return getattr(hardware, "memory", None)

    def reset(self) -> None:
        self.status.reset_requested = True

    def halt(self) -> None:
        self.status.halt_requested = True

    def nmi(self) -> None:
        self.status.nmi_requested = True

    def irq(self) -> None:
        self.status.irq_requested = True

    def execute(self, clocks: int) -> int:
        if self.memory is None:
            raise RuntimeError("Memory system is not attached to MB8861")

        clock_attr = "clock_count"
        if not hasattr(self.computer, clock_attr):
            raise AttributeError("Computer object must provide clock_count attribute")

        target_clock = self._get_clock_count() + clocks
        while self._get_clock_count() < target_clock:
            if self.status.reset_requested:
                self._handle_reset()
                return 0

            if self.status.halt_requested:
                self.status.halt_processed = True
                continue

            if self.status.halt_processed:
                self.status.halt_processed = False

            if self.status.fetch_wai:
                handled_interrupt = self._service_pending_interrupts(in_wai=True)
                if handled_interrupt:
                    continue
                self._increment_clock(1)
                continue

            if self._service_pending_interrupts(in_wai=False):
                continue

            opcode = self._fetch_op()
            if opcode == self.OP_RTI_IMP:
                self._rti()
                self._increment_clock(10)
                continue

            if opcode == self.OP_RTS_IMP:
                self._rts()
                self._increment_clock(5)
                continue

            if opcode == self.OP_SWI_IMP:
                self._swi()
                self._increment_clock(12)
                continue

            if opcode == self.OP_WAI_IMP:
                self._wai()
                self._increment_clock(9)
                continue

            if opcode in self._opcode_table:
                handler, cycles = self._opcode_table[opcode]
                handler()
                self._increment_clock(cycles)
                continue

            raise NotImplementedError("Opcode execution dispatch is not ported yet: 0x%02X" % opcode)

        return self._get_clock_count() - target_clock

    def _handle_reset(self) -> None:
        self.status.reset_requested = False
        self.status.fetch_wai = False
        self.registers.program_counter = self._load16(self.VECTOR_RESTART)
        self._set_clock_count(0)

    def _service_pending_interrupts(self, *, in_wai: bool) -> bool:
        if self.status.nmi_requested:
            self.status.nmi_requested = False
            self.status.fetch_wai = False
            self._push_all_registers()
            self.registers.program_counter = self._load16(self.VECTOR_NMI)
            self._increment_clock(12)
            return True

        if self.status.irq_requested and not self.flags.carry_i:
            self.status.irq_requested = False
            if in_wai:
                self.status.fetch_wai = False
            self._push_all_registers()
            self.registers.program_counter = self._load16(self.VECTOR_IRQ)
            self._increment_clock(12)
            return True

        return False

    def _push_all_registers(self) -> None:
        sp = self.registers.stack_pointer & 0xFFFF
        ccr = 0xC0
        if self.flags.carry_h:
            ccr |= 0x20
        if self.flags.carry_i:
            ccr |= 0x10
        if self.flags.carry_n:
            ccr |= 0x08
        if self.flags.carry_z:
            ccr |= 0x04
        if self.flags.carry_v:
            ccr |= 0x02
        if self.flags.carry_c:
            ccr |= 0x01

        self._store16((sp - 1) & 0xFFFF, self.registers.program_counter)
        self._store16((sp - 3) & 0xFFFF, self.registers.index)
        self._store8((sp - 4) & 0xFFFF, self.registers.acc_a)
        self._store8((sp - 5) & 0xFFFF, self.registers.acc_b)
        self._store8((sp - 6) & 0xFFFF, ccr)
        self.registers.stack_pointer = (sp - 7) & 0xFFFF

    def _pop_all_registers(self) -> None:
        sp = (self.registers.stack_pointer + 7) & 0xFFFF
        ccr = self._load8((sp - 6) & 0xFFFF)
        self.flags.carry_h = bool(ccr & 0x20)
        self.flags.carry_i = bool(ccr & 0x10)
        self.flags.carry_n = bool(ccr & 0x08)
        self.flags.carry_z = bool(ccr & 0x04)
        self.flags.carry_v = bool(ccr & 0x02)
        self.flags.carry_c = bool(ccr & 0x01)
        self.registers.acc_b = self._load8((sp - 5) & 0xFFFF)
        self.registers.acc_a = self._load8((sp - 4) & 0xFFFF)
        self.registers.index = self._load16((sp - 3) & 0xFFFF)
        self.registers.program_counter = self._load16((sp - 1) & 0xFFFF)
        self.registers.stack_pointer = sp

    def _load16(self, address: int) -> int:
        if not hasattr(self.memory, "load16"):
            raise AttributeError("Memory system must provide load16")
        return getattr(self.memory, "load16")(address & 0xFFFF) & 0xFFFF

    def _load8(self, address: int) -> int:
        if not hasattr(self.memory, "load8"):
            raise AttributeError("Memory system must provide load8")
        return getattr(self.memory, "load8")(address & 0xFFFF) & 0xFF

    def _store16(self, address: int, value: int) -> None:
        if not hasattr(self.memory, "store16"):
            raise AttributeError("Memory system must provide store16")
        getattr(self.memory, "store16")(address & 0xFFFF, value & 0xFFFF)

    def _store8(self, address: int, value: int) -> None:
        if not hasattr(self.memory, "store8"):
            raise AttributeError("Memory system must provide store8")
        getattr(self.memory, "store8")(address & 0xFFFF, value & 0xFF)

    def _get_clock_count(self) -> int:
        return getattr(self.computer, "clock_count")

    def _set_clock_count(self, value: int) -> None:
        setattr(self.computer, "clock_count", value)

    def _increment_clock(self, ticks: int) -> None:
        self._set_clock_count(self._get_clock_count() + ticks)

    def _fetch_op(self) -> int:
        op = self._load8(self.registers.program_counter)
        self.registers.program_counter = (self.registers.program_counter + 1) & 0xFFFF
        return op

    def _fetch_operand8(self) -> int:
        value = self._load8(self.registers.program_counter)
        self.registers.program_counter = (self.registers.program_counter + 1) & 0xFFFF
        return value

    def _fetch_operand16(self) -> int:
        high = self._fetch_operand8()
        low = self._fetch_operand8()
        return ((high << 8) | low) & 0xFFFF

    def _rti(self) -> None:
        self._pop_all_registers()

    def _rts(self) -> None:
        sp = (self.registers.stack_pointer + 2) & 0xFFFF
        self.registers.program_counter = self._load16((sp - 1) & 0xFFFF)
        self.registers.stack_pointer = sp

    def _swi(self) -> None:
        self.registers.program_counter = (self.registers.program_counter + 1) & 0xFFFF
        self._push_all_registers()
        self.flags.carry_i = True
        self.registers.program_counter = self._load16(self.VECTOR_SWI)

    def _wai(self) -> None:
        self.status.fetch_wai = True

    def _init_opcode_table(self) -> None:
        self._opcode_table.clear()
        self._register_opcode(self.OP_ABA_IMP, self._opcode_aba, 2)
        self._register_opcode(self.OP_ADDA_IMM, self._opcode_adda_imm, 2)
        self._register_opcode(self.OP_ADDA_DIR, self._opcode_adda_dir, 3)
        self._register_opcode(self.OP_ADDA_IND, self._opcode_adda_ind, 5)
        self._register_opcode(self.OP_ADDA_EXT, self._opcode_adda_ext, 4)
        self._register_opcode(self.OP_ADDB_IMM, self._opcode_addb_imm, 2)
        self._register_opcode(self.OP_ADDB_DIR, self._opcode_addb_dir, 3)
        self._register_opcode(self.OP_ADDB_IND, self._opcode_addb_ind, 5)
        self._register_opcode(self.OP_ADDB_EXT, self._opcode_addb_ext, 4)
        self._register_opcode(self.OP_ADCA_IMM, self._opcode_adca_imm, 2)
        self._register_opcode(self.OP_ADCA_DIR, self._opcode_adca_dir, 3)
        self._register_opcode(self.OP_ADCA_IND, self._opcode_adca_ind, 5)
        self._register_opcode(self.OP_ADCA_EXT, self._opcode_adca_ext, 4)
        self._register_opcode(self.OP_ADCB_IMM, self._opcode_adcb_imm, 2)
        self._register_opcode(self.OP_ADCB_DIR, self._opcode_adcb_dir, 3)
        self._register_opcode(self.OP_ADCB_IND, self._opcode_adcb_ind, 5)
        self._register_opcode(self.OP_ADCB_EXT, self._opcode_adcb_ext, 4)
        self._register_opcode(self.OP_ANDA_IMM, self._opcode_anda_imm, 2)
        self._register_opcode(self.OP_ANDA_DIR, self._opcode_anda_dir, 3)
        self._register_opcode(self.OP_ANDA_IND, self._opcode_anda_ind, 5)
        self._register_opcode(self.OP_ANDA_EXT, self._opcode_anda_ext, 4)
        self._register_opcode(self.OP_ANDB_IMM, self._opcode_andb_imm, 2)
        self._register_opcode(self.OP_ANDB_DIR, self._opcode_andb_dir, 3)
        self._register_opcode(self.OP_ANDB_IND, self._opcode_andb_ind, 5)
        self._register_opcode(self.OP_ANDB_EXT, self._opcode_andb_ext, 4)
        self._register_opcode(self.OP_BITA_IMM, self._opcode_bita_imm, 2)
        self._register_opcode(self.OP_BITA_DIR, self._opcode_bita_dir, 3)
        self._register_opcode(self.OP_BITA_IND, self._opcode_bita_ind, 5)
        self._register_opcode(self.OP_BITA_EXT, self._opcode_bita_ext, 4)
        self._register_opcode(self.OP_BITB_IMM, self._opcode_bitb_imm, 2)
        self._register_opcode(self.OP_BITB_DIR, self._opcode_bitb_dir, 3)
        self._register_opcode(self.OP_BITB_IND, self._opcode_bitb_ind, 5)
        self._register_opcode(self.OP_BITB_EXT, self._opcode_bitb_ext, 4)
        self._register_opcode(self.OP_CBA_IMP, self._opcode_cba, 2)
        self._register_opcode(self.OP_CLRA_IMP, self._opcode_clra, 2)
        self._register_opcode(self.OP_CLRB_IMP, self._opcode_clrb, 2)
        self._register_opcode(self.OP_CMPA_IMM, self._opcode_cmpa_imm, 2)
        self._register_opcode(self.OP_CMPA_DIR, self._opcode_cmpa_dir, 3)
        self._register_opcode(self.OP_CMPA_IND, self._opcode_cmpa_ind, 5)
        self._register_opcode(self.OP_CMPA_EXT, self._opcode_cmpa_ext, 4)
        self._register_opcode(self.OP_CMPB_IMM, self._opcode_cmpb_imm, 2)
        self._register_opcode(self.OP_CMPB_DIR, self._opcode_cmpb_dir, 3)
        self._register_opcode(self.OP_CMPB_IND, self._opcode_cmpb_ind, 5)
        self._register_opcode(self.OP_CMPB_EXT, self._opcode_cmpb_ext, 4)
        self._register_opcode(self.OP_COMA_IMP, self._opcode_coma, 2)
        self._register_opcode(self.OP_COMB_IMP, self._opcode_comb, 2)
        self._register_opcode(self.OP_DAA_IMP, self._opcode_daa, 2)
        self._register_opcode(self.OP_DECA_IMP, self._opcode_deca, 2)
        self._register_opcode(self.OP_DECB_IMP, self._opcode_decb, 2)
        self._register_opcode(self.OP_EORA_IMM, self._opcode_eora_imm, 2)
        self._register_opcode(self.OP_EORA_DIR, self._opcode_eora_dir, 3)
        self._register_opcode(self.OP_EORA_IND, self._opcode_eora_ind, 5)
        self._register_opcode(self.OP_EORA_EXT, self._opcode_eora_ext, 4)
        self._register_opcode(self.OP_EORB_IMM, self._opcode_eorb_imm, 2)
        self._register_opcode(self.OP_EORB_DIR, self._opcode_eorb_dir, 3)
        self._register_opcode(self.OP_EORB_IND, self._opcode_eorb_ind, 5)
        self._register_opcode(self.OP_EORB_EXT, self._opcode_eorb_ext, 4)
        self._register_opcode(self.OP_INCA_IMP, self._opcode_inca, 2)
        self._register_opcode(self.OP_INCB_IMP, self._opcode_incb, 2)
        self._register_opcode(self.OP_LDAA_IMM, self._opcode_ldaa_imm, 2)
        self._register_opcode(self.OP_LDAA_DIR, self._opcode_ldaa_dir, 3)
        self._register_opcode(self.OP_LDAA_IND, self._opcode_ldaa_ind, 5)
        self._register_opcode(self.OP_LDAA_EXT, self._opcode_ldaa_ext, 4)
        self._register_opcode(self.OP_LDAB_IMM, self._opcode_ldab_imm, 2)
        self._register_opcode(self.OP_LDAB_DIR, self._opcode_ldab_dir, 3)
        self._register_opcode(self.OP_LDAB_IND, self._opcode_ldab_ind, 5)
        self._register_opcode(self.OP_LDAB_EXT, self._opcode_ldab_ext, 4)
        self._register_opcode(self.OP_LSRA_IMP, self._opcode_lsra, 2)
        self._register_opcode(self.OP_LSRB_IMP, self._opcode_lsrb, 2)
        self._register_opcode(self.OP_NEGA_IMP, self._opcode_nega, 2)
        self._register_opcode(self.OP_NEGB_IMP, self._opcode_negb, 2)
        self._register_opcode(self.OP_ORAA_IMM, self._opcode_oraa_imm, 2)
        self._register_opcode(self.OP_ORAA_DIR, self._opcode_oraa_dir, 3)
        self._register_opcode(self.OP_ORAA_IND, self._opcode_oraa_ind, 5)
        self._register_opcode(self.OP_ORAA_EXT, self._opcode_oraa_ext, 4)
        self._register_opcode(self.OP_ORAB_IMM, self._opcode_orab_imm, 2)
        self._register_opcode(self.OP_ORAB_DIR, self._opcode_orab_dir, 3)
        self._register_opcode(self.OP_ORAB_IND, self._opcode_orab_ind, 5)
        self._register_opcode(self.OP_ORAB_EXT, self._opcode_orab_ext_buggy, 4)
        self._register_opcode(self.OP_SBA_IMP, self._opcode_sba, 2)
        self._register_opcode(self.OP_SUBA_IMM, self._opcode_suba_imm, 2)
        self._register_opcode(self.OP_SUBA_DIR, self._opcode_suba_dir, 3)
        self._register_opcode(self.OP_SUBA_IND, self._opcode_suba_ind, 5)
        self._register_opcode(self.OP_SUBA_EXT, self._opcode_suba_ext, 4)
        self._register_opcode(self.OP_SUBB_IMM, self._opcode_subb_imm, 2)
        self._register_opcode(self.OP_SUBB_DIR, self._opcode_subb_dir, 3)
        self._register_opcode(self.OP_SUBB_IND, self._opcode_subb_ind, 5)
        self._register_opcode(self.OP_SUBB_EXT, self._opcode_subb_ext, 4)
        self._register_opcode(self.OP_SBCA_IMM, self._opcode_sbca_imm, 2)
        self._register_opcode(self.OP_SBCA_DIR, self._opcode_sbca_dir, 3)
        self._register_opcode(self.OP_SBCA_IND, self._opcode_sbca_ind, 5)
        self._register_opcode(self.OP_SBCA_EXT, self._opcode_sbca_ext, 4)
        self._register_opcode(self.OP_SBCB_IMM, self._opcode_sbcb_imm, 2)
        self._register_opcode(self.OP_SBCB_DIR, self._opcode_sbcb_dir, 3)
        self._register_opcode(self.OP_SBCB_IND, self._opcode_sbcb_ind, 5)
        self._register_opcode(self.OP_SBCB_EXT, self._opcode_sbcb_ext, 4)
        self._register_opcode(self.OP_TAB_IMP, self._opcode_tab, 2)
        self._register_opcode(self.OP_TBA_IMP, self._opcode_tba, 2)
        self._register_opcode(self.OP_TSTA_IMP, self._opcode_tsta, 2)
        self._register_opcode(self.OP_TSTB_IMP, self._opcode_tstb, 2)
        self._register_opcode(self.OP_STAA_DIR, self._opcode_staa_dir, 4)
        self._register_opcode(self.OP_STAA_IND, self._opcode_staa_ind, 6)
        self._register_opcode(self.OP_STAA_EXT, self._opcode_staa_ext, 5)
        self._register_opcode(self.OP_STAB_DIR, self._opcode_stab_dir, 4)
        self._register_opcode(self.OP_STAB_IND, self._opcode_stab_ind, 6)
        self._register_opcode(self.OP_STAB_EXT, self._opcode_stab_ext, 5)
        self._register_opcode(self.OP_CPX_IMM, self._opcode_cpx_imm, 3)
        self._register_opcode(self.OP_CPX_DIR, self._opcode_cpx_dir, 4)
        self._register_opcode(self.OP_CPX_IND, self._opcode_cpx_ind, 6)
        self._register_opcode(self.OP_CPX_EXT, self._opcode_cpx_ext, 5)
        self._register_opcode(self.OP_DEX_IMP, self._opcode_dex, 4)
        self._register_opcode(self.OP_DES_IMP, self._opcode_des, 4)
        self._register_opcode(self.OP_INX_IMP, self._opcode_inx, 4)
        self._register_opcode(self.OP_INS_IMP, self._opcode_ins, 4)
        self._register_opcode(self.OP_LDX_IMM, self._opcode_ldx_imm, 3)
        self._register_opcode(self.OP_LDX_DIR, self._opcode_ldx_dir, 4)
        self._register_opcode(self.OP_LDX_IND, self._opcode_ldx_ind, 6)
        self._register_opcode(self.OP_LDX_EXT, self._opcode_ldx_ext, 5)
        self._register_opcode(self.OP_LDS_IMM, self._opcode_lds_imm, 3)
        self._register_opcode(self.OP_LDS_DIR, self._opcode_lds_dir, 4)
        self._register_opcode(self.OP_LDS_IND, self._opcode_lds_ind, 6)
        self._register_opcode(self.OP_LDS_EXT, self._opcode_lds_ext, 5)
        self._register_opcode(self.OP_STX_DIR, self._opcode_stx_dir, 5)
        self._register_opcode(self.OP_STX_IND, self._opcode_stx_ind, 7)
        self._register_opcode(self.OP_STX_EXT, self._opcode_stx_ext, 6)
        self._register_opcode(self.OP_STS_DIR, self._opcode_sts_dir, 5)
        self._register_opcode(self.OP_STS_IND, self._opcode_sts_ind, 7)
        self._register_opcode(self.OP_STS_EXT, self._opcode_sts_ext, 6)
        self._register_opcode(self.OP_TXS_IMP, self._opcode_txs, 4)
        self._register_opcode(self.OP_TSX_IMP, self._opcode_tsx, 4)
        self._register_opcode(self.OP_NOP_IMP, self._opcode_nop, 2)
        self._register_opcode(self.OP_BRA_REL, self._opcode_bra, 4)
        self._register_opcode(self.OP_BCC_REL, self._opcode_bcc, 4)
        self._register_opcode(self.OP_BCS_REL, self._opcode_bcs, 4)
        self._register_opcode(self.OP_BEQ_REL, self._opcode_beq, 4)
        self._register_opcode(self.OP_BGE_REL, self._opcode_bge, 4)
        self._register_opcode(self.OP_BGT_REL, self._opcode_bgt, 4)
        self._register_opcode(self.OP_BHI_REL, self._opcode_bhi, 4)
        self._register_opcode(self.OP_BLE_REL, self._opcode_ble, 4)
        self._register_opcode(self.OP_BLS_REL, self._opcode_bls, 4)
        self._register_opcode(self.OP_BLT_REL, self._opcode_blt, 4)
        self._register_opcode(self.OP_BMI_REL, self._opcode_bmi, 4)
        self._register_opcode(self.OP_BNE_REL, self._opcode_bne, 4)
        self._register_opcode(self.OP_BVC_REL, self._opcode_bvc, 4)
        self._register_opcode(self.OP_BVS_REL, self._opcode_bvs, 4)
        self._register_opcode(self.OP_BPL_REL, self._opcode_bpl, 4)
        self._register_opcode(self.OP_BSR_REL, self._opcode_bsr, 8)
        self._register_opcode(self.OP_JMP_IND, self._opcode_jmp_ind, 4)
        self._register_opcode(self.OP_JMP_EXT, self._opcode_jmp_ext, 3)
        self._register_opcode(self.OP_JSR_IND, self._opcode_jsr_ind, 8)
        self._register_opcode(self.OP_JSR_EXT, self._opcode_jsr_ext, 9)
        self._register_opcode(self.OP_ADX_IMM, self._opcode_adx_imm, 3)
        self._register_opcode(self.OP_ADX_EXT, self._opcode_adx_ext, 7)
        self._register_opcode(self.OP_NIM_IND, self._opcode_nim_ind, 8)
        self._register_opcode(self.OP_OIM_IND, self._opcode_oim_ind, 8)
        self._register_opcode(self.OP_XIM_IND, self._opcode_xim_ind, 8)
        self._register_opcode(self.OP_TMM_IND, self._opcode_tmm_ind, 7)

    def _register_opcode(self, opcode: int, handler: Callable[[], None], cycles: int) -> None:
        self._opcode_table[opcode & 0xFF] = (handler, cycles)

    def _opcode_aba(self) -> None:
        self.registers.acc_a = self._add8(self.registers.acc_a, self.registers.acc_b)

    def _opcode_adda_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_a = self._add8(self.registers.acc_a, operand)

    def _opcode_adda_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_a = self._add8(self.registers.acc_a, value)

    def _opcode_adda_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_a = self._add8(self.registers.acc_a, value)

    def _opcode_adda_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_a = self._add8(self.registers.acc_a, value)

    def _opcode_addb_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_b = self._add8(self.registers.acc_b, operand)

    def _opcode_addb_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_b = self._add8(self.registers.acc_b, value)

    def _opcode_addb_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_b = self._add8(self.registers.acc_b, value)

    def _opcode_addb_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_b = self._add8(self.registers.acc_b, value)

    def _opcode_adca_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_a = self._adc8(self.registers.acc_a, operand)

    def _opcode_adca_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_a = self._adc8(self.registers.acc_a, value)

    def _opcode_adca_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_a = self._adc8(self.registers.acc_a, value)

    def _opcode_adca_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_a = self._adc8(self.registers.acc_a, value)

    def _opcode_adcb_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_b = self._adc8(self.registers.acc_b, operand)

    def _opcode_adcb_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_b = self._adc8(self.registers.acc_b, value)

    def _opcode_adcb_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_b = self._adc8(self.registers.acc_b, value)

    def _opcode_adcb_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_b = self._adc8(self.registers.acc_b, value)

    def _opcode_anda_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_a = self._and8(self.registers.acc_a, operand)

    def _opcode_anda_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_a = self._and8(self.registers.acc_a, value)

    def _opcode_anda_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_a = self._and8(self.registers.acc_a, value)

    def _opcode_anda_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_a = self._and8(self.registers.acc_a, value)

    def _opcode_andb_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_b = self._and8(self.registers.acc_b, operand)

    def _opcode_andb_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_b = self._and8(self.registers.acc_b, value)

    def _opcode_andb_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_b = self._and8(self.registers.acc_b, value)

    def _opcode_andb_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_b = self._and8(self.registers.acc_b, value)

    def _opcode_bita_imm(self) -> None:
        operand = self._fetch_operand8()
        self._bit8(self.registers.acc_a, operand)

    def _opcode_bita_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self._bit8(self.registers.acc_a, value)

    def _opcode_bita_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self._bit8(self.registers.acc_a, value)

    def _opcode_bita_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self._bit8(self.registers.acc_a, value)

    def _opcode_bitb_imm(self) -> None:
        operand = self._fetch_operand8()
        self._bit8(self.registers.acc_b, operand)

    def _opcode_bitb_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self._bit8(self.registers.acc_b, value)

    def _opcode_bitb_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self._bit8(self.registers.acc_b, value)

    def _opcode_bitb_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self._bit8(self.registers.acc_b, value)

    def _opcode_cba(self) -> None:
        self._cmp8(self.registers.acc_a, self.registers.acc_b)

    def _opcode_clra(self) -> None:
        self.registers.acc_a = self._clr()

    def _opcode_clrb(self) -> None:
        self.registers.acc_b = self._clr()

    def _opcode_cmpa_imm(self) -> None:
        operand = self._fetch_operand8()
        self._cmp8(self.registers.acc_a, operand)

    def _opcode_cmpa_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self._cmp8(self.registers.acc_a, value)

    def _opcode_cmpa_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self._cmp8(self.registers.acc_a, value)

    def _opcode_cmpa_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self._cmp8(self.registers.acc_a, value)

    def _opcode_cmpb_imm(self) -> None:
        operand = self._fetch_operand8()
        self._cmp8(self.registers.acc_b, operand)

    def _opcode_cmpb_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self._cmp8(self.registers.acc_b, value)

    def _opcode_cmpb_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self._cmp8(self.registers.acc_b, value)

    def _opcode_cmpb_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self._cmp8(self.registers.acc_b, value)

    def _opcode_coma(self) -> None:
        self.registers.acc_a = self._com(self.registers.acc_a)

    def _opcode_comb(self) -> None:
        self.registers.acc_b = self._com(self.registers.acc_b)

    def _opcode_daa(self) -> None:
        original = self.registers.acc_a & 0xFF
        temp = original
        if (temp & 0x0F) >= 0x0A or self.flags.carry_h:
            temp += 0x06
        if (temp & 0xF0) >= 0xA0:
            temp += 0x60
        result = temp & 0xFF
        cn = result & 0x80 != 0
        self.flags.carry_n = cn
        self.flags.carry_z = result == 0
        signed_original = self._to_signed8(original)
        self.flags.carry_v = (signed_original > 0 and cn) or (signed_original < 0 and not cn)
        self.flags.carry_c = ((original & 0xF0) >= 0xA0) or self.flags.carry_c
        self.registers.acc_a = result

    def _opcode_deca(self) -> None:
        self.registers.acc_a = self._dec(self.registers.acc_a)

    def _opcode_decb(self) -> None:
        self.registers.acc_b = self._dec(self.registers.acc_b)

    def _opcode_eora_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_a = self._eor8(self.registers.acc_a, operand)

    def _opcode_eora_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_a = self._eor8(self.registers.acc_a, value)

    def _opcode_eora_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_a = self._eor8(self.registers.acc_a, value)

    def _opcode_eora_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_a = self._eor8(self.registers.acc_a, value)

    def _opcode_eorb_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_b = self._eor8(self.registers.acc_b, operand)

    def _opcode_eorb_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_b = self._eor8(self.registers.acc_b, value)

    def _opcode_eorb_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_b = self._eor8(self.registers.acc_b, value)

    def _opcode_eorb_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_b = self._eor8(self.registers.acc_b, value)

    def _opcode_inca(self) -> None:
        self.registers.acc_a = self._inc(self.registers.acc_a)

    def _opcode_incb(self) -> None:
        self.registers.acc_b = self._inc(self.registers.acc_b)

    def _opcode_ldaa_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_a = self._lda(operand)

    def _opcode_ldaa_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_a = self._lda(value)

    def _opcode_ldaa_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_a = self._lda(value)

    def _opcode_ldaa_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_a = self._lda(value)

    def _opcode_ldab_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_b = self._lda(operand)

    def _opcode_ldab_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_b = self._lda(value)

    def _opcode_ldab_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_b = self._lda(value)

    def _opcode_ldab_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_b = self._lda(value)

    def _opcode_lsra(self) -> None:
        self.registers.acc_a = self._lsr(self.registers.acc_a)

    def _opcode_lsrb(self) -> None:
        self.registers.acc_b = self._lsr(self.registers.acc_b)

    def _opcode_nega(self) -> None:
        self.registers.acc_a = self._neg(self.registers.acc_a)

    def _opcode_negb(self) -> None:
        self.registers.acc_b = self._neg(self.registers.acc_b)

    def _opcode_oraa_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_a = self._ora(self.registers.acc_a, operand)

    def _opcode_oraa_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_a = self._ora(self.registers.acc_a, value)

    def _opcode_oraa_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_a = self._ora(self.registers.acc_a, value)

    def _opcode_oraa_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_a = self._ora(self.registers.acc_a, value)

    def _opcode_orab_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_b = self._ora(self.registers.acc_b, operand)

    def _opcode_orab_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_b = self._ora(self.registers.acc_b, value)

    def _opcode_orab_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_b = self._ora(self.registers.acc_b, value)

    def _opcode_orab_ext_buggy(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_b = self._add8(self.registers.acc_b, value)

    def _opcode_sba(self) -> None:
        self.registers.acc_a = self._sub8(self.registers.acc_a, self.registers.acc_b)

    def _opcode_suba_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_a = self._sub8(self.registers.acc_a, operand)

    def _opcode_suba_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_a = self._sub8(self.registers.acc_a, value)

    def _opcode_suba_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_a = self._sub8(self.registers.acc_a, value)

    def _opcode_suba_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_a = self._sub8(self.registers.acc_a, value)

    def _opcode_subb_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_b = self._sub8(self.registers.acc_b, operand)

    def _opcode_subb_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_b = self._sub8(self.registers.acc_b, value)

    def _opcode_subb_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_b = self._sub8(self.registers.acc_b, value)

    def _opcode_subb_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_b = self._sub8(self.registers.acc_b, value)

    def _opcode_sbca_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_a = self._sbc8(self.registers.acc_a, operand)

    def _opcode_sbca_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_a = self._sbc8(self.registers.acc_a, value)

    def _opcode_sbca_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_a = self._sbc8(self.registers.acc_a, value)

    def _opcode_sbca_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_a = self._sbc8(self.registers.acc_a, value)

    def _opcode_sbcb_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.acc_b = self._sbc8(self.registers.acc_b, operand)

    def _opcode_sbcb_dir(self) -> None:
        address = self._fetch_operand8()
        value = self._load8(address)
        self.registers.acc_b = self._sbc8(self.registers.acc_b, value)

    def _opcode_sbcb_ind(self) -> None:
        offset = self._fetch_operand8()
        address = (self.registers.index + offset) & 0xFFFF
        value = self._load8(address)
        self.registers.acc_b = self._sbc8(self.registers.acc_b, value)

    def _opcode_sbcb_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load8(address)
        self.registers.acc_b = self._sbc8(self.registers.acc_b, value)

    def _opcode_tab(self) -> None:
        self.registers.acc_b = self.registers.acc_a & 0xFF
        self.flags.carry_n = self.registers.acc_b & 0x80 != 0
        self.flags.carry_z = self.registers.acc_b == 0
        self.flags.carry_v = False

    def _opcode_tba(self) -> None:
        self.registers.acc_a = self.registers.acc_b & 0xFF
        self.flags.carry_n = self.registers.acc_a & 0x80 != 0
        self.flags.carry_z = self.registers.acc_a == 0
        self.flags.carry_v = False

    def _opcode_tsta(self) -> None:
        self._tst(self.registers.acc_a)

    def _opcode_tstb(self) -> None:
        self._tst(self.registers.acc_b)

    def _opcode_staa_dir(self) -> None:
        address = self._calc_direct_address(self._fetch_operand8())
        self._sta(address, self.registers.acc_a)

    def _opcode_staa_ind(self) -> None:
        offset = self._fetch_operand8()
        address = self._calc_indexed_address(offset)
        self._sta(address, self.registers.acc_a)

    def _opcode_staa_ext(self) -> None:
        address = self._fetch_operand16()
        self._sta(address, self.registers.acc_a)

    def _opcode_stab_dir(self) -> None:
        address = self._calc_direct_address(self._fetch_operand8())
        self._sta(address, self.registers.acc_b)

    def _opcode_stab_ind(self) -> None:
        offset = self._fetch_operand8()
        address = self._calc_indexed_address(offset)
        self._sta(address, self.registers.acc_b)

    def _opcode_stab_ext(self) -> None:
        address = self._fetch_operand16()
        self._sta(address, self.registers.acc_b)

    def _opcode_cpx_imm(self) -> None:
        operand = self._fetch_operand16()
        self._cpx(operand)

    def _opcode_cpx_dir(self) -> None:
        address = self._calc_direct_address(self._fetch_operand8())
        value = self._load16(address)
        self._cpx(value)

    def _opcode_cpx_ind(self) -> None:
        offset = self._fetch_operand8()
        address = self._calc_indexed_address(offset)
        value = self._load16(address)
        self._cpx(value)

    def _opcode_cpx_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load16(address)
        self._cpx(value)

    def _opcode_dex(self) -> None:
        self._dex()

    def _opcode_des(self) -> None:
        self._des()

    def _opcode_inx(self) -> None:
        self._inx()

    def _opcode_ins(self) -> None:
        self._ins()

    def _opcode_ldx_imm(self) -> None:
        operand = self._fetch_operand16()
        self._ldx(operand)

    def _opcode_ldx_dir(self) -> None:
        address = self._calc_direct_address(self._fetch_operand8())
        value = self._load16(address)
        self._ldx(value)

    def _opcode_ldx_ind(self) -> None:
        offset = self._fetch_operand8()
        address = self._calc_indexed_address(offset)
        value = self._load16(address)
        self._ldx(value)

    def _opcode_ldx_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load16(address)
        self._ldx(value)

    def _opcode_lds_imm(self) -> None:
        operand = self._fetch_operand16()
        self._lds(operand)

    def _opcode_lds_dir(self) -> None:
        address = self._calc_direct_address(self._fetch_operand8())
        value = self._load16(address)
        self._lds(value)

    def _opcode_lds_ind(self) -> None:
        offset = self._fetch_operand8()
        address = self._calc_indexed_address(offset)
        value = self._load16(address)
        self._lds(value)

    def _opcode_lds_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load16(address)
        self._lds(value)

    def _opcode_stx_dir(self) -> None:
        address = self._calc_direct_address(self._fetch_operand8())
        self._stx(address)

    def _opcode_stx_ind(self) -> None:
        offset = self._fetch_operand8()
        address = self._calc_indexed_address(offset)
        self._stx(address)

    def _opcode_stx_ext(self) -> None:
        address = self._fetch_operand16()
        self._stx(address)

    def _opcode_sts_dir(self) -> None:
        address = self._calc_direct_address(self._fetch_operand8())
        self._sts(address)

    def _opcode_sts_ind(self) -> None:
        offset = self._fetch_operand8()
        address = self._calc_indexed_address(offset)
        self._sts(address)

    def _opcode_sts_ext(self) -> None:
        address = self._fetch_operand16()
        self._sts(address)

    def _opcode_txs(self) -> None:
        self.registers.stack_pointer = (self.registers.index - 1) & 0xFFFF

    def _opcode_tsx(self) -> None:
        self.registers.index = (self.registers.stack_pointer + 1) & 0xFFFF

    def _opcode_nop(self) -> None:
        pass

    def _opcode_bra(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, True)

    def _opcode_bcc(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, not self.flags.carry_c)

    def _opcode_bcs(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, self.flags.carry_c)

    def _opcode_beq(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, self.flags.carry_z)

    def _opcode_bge(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, not (self.flags.carry_n ^ self.flags.carry_v))

    def _opcode_bgt(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, not (self.flags.carry_z or (self.flags.carry_n ^ self.flags.carry_v)))

    def _opcode_bhi(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, not (self.flags.carry_c or self.flags.carry_z))

    def _opcode_ble(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, self.flags.carry_z or (self.flags.carry_n ^ self.flags.carry_v))

    def _opcode_bls(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, self.flags.carry_c or self.flags.carry_z)

    def _opcode_blt(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, self.flags.carry_n ^ self.flags.carry_v)

    def _opcode_bmi(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, self.flags.carry_n)

    def _opcode_bne(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, not self.flags.carry_z)

    def _opcode_bvc(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, not self.flags.carry_v)

    def _opcode_bvs(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, self.flags.carry_v)

    def _opcode_bpl(self) -> None:
        offset = self._fetch_operand8()
        self._branch(offset, not self.flags.carry_n)

    def _opcode_bsr(self) -> None:
        offset = self._fetch_operand8()
        self.registers.stack_pointer = (self.registers.stack_pointer - 2) & 0xFFFF
        self._store16((self.registers.stack_pointer + 1) & 0xFFFF, self.registers.program_counter)
        self._branch(offset, True)

    def _opcode_jmp_ind(self) -> None:
        offset = self._fetch_operand8()
        address = self._calc_indexed_address(offset)
        self.registers.program_counter = self._load16(address)

    def _opcode_jmp_ext(self) -> None:
        address = self._fetch_operand16()
        self.registers.program_counter = address & 0xFFFF

    def _opcode_jsr_ind(self) -> None:
        offset = self._fetch_operand8()
        address = self._calc_indexed_address(offset)
        self.registers.stack_pointer = (self.registers.stack_pointer - 2) & 0xFFFF
        self._store16((self.registers.stack_pointer + 1) & 0xFFFF, self.registers.program_counter)
        self.registers.program_counter = self._load16(address)

    def _opcode_jsr_ext(self) -> None:
        address = self._fetch_operand16()
        self.registers.stack_pointer = (self.registers.stack_pointer - 2) & 0xFFFF
        self._store16((self.registers.stack_pointer + 1) & 0xFFFF, self.registers.program_counter)
        self.registers.program_counter = address & 0xFFFF

    def _opcode_adx_imm(self) -> None:
        operand = self._fetch_operand8()
        self.registers.index = self._add16(self.registers.index, operand & 0xFF)

    def _opcode_adx_ext(self) -> None:
        address = self._fetch_operand16()
        value = self._load16(address)
        self.registers.index = self._add16(self.registers.index, value)

    def _opcode_nim_ind(self) -> None:
        value = self._fetch_operand8()
        offset = self._fetch_operand8()
        address = self._calc_indexed_address(offset)
        current = self._load8(address)
        result = self._nim(value, current)
        self._store8(address, result)

    def _opcode_oim_ind(self) -> None:
        value = self._fetch_operand8()
        offset = self._fetch_operand8()
        address = self._calc_indexed_address(offset)
        current = self._load8(address)
        result = self._oim(value, current)
        self._store8(address, result)

    def _opcode_xim_ind(self) -> None:
        value = self._fetch_operand8()
        offset = self._fetch_operand8()
        address = self._calc_indexed_address(offset)
        current = self._load8(address)
        result = self._xim(value, current)
        self._store8(address, result)

    def _opcode_tmm_ind(self) -> None:
        value = self._fetch_operand8()
        offset = self._fetch_operand8()
        address = self._calc_indexed_address(offset)
        current = self._load8(address)
        self._tmm(value, current)
    @staticmethod
    def _to_signed8(value: int) -> int:
        value &= 0xFF
        return value - 0x100 if value & 0x80 else value

    def _add8(self, x: int, y: int) -> int:
        a = x & 0xFF
        b = y & 0xFF
        result = (a + b) & 0x1FF
        value = result & 0xFF
        cn = value & 0x80 != 0
        self.flags.carry_h = ((a & 0x0F) + (b & 0x0F)) > 0x0F
        self.flags.carry_n = cn
        self.flags.carry_z = value == 0
        sa = self._to_signed8(a)
        sb = self._to_signed8(b)
        self.flags.carry_v = (sa > 0 and sb > 0 and cn) or (sa < 0 and sb < 0 and not cn)
        self.flags.carry_c = result > 0xFF
        return value

    def _adc8(self, x: int, y: int) -> int:
        carry_in = 1 if self.flags.carry_c else 0
        a = x & 0xFF
        b = y & 0xFF
        result = (a + b + carry_in) & 0x1FF
        value = result & 0xFF
        cn = value & 0x80 != 0
        self.flags.carry_h = ((a & 0x0F) + (b & 0x0F)) > 0x0F
        self.flags.carry_n = cn
        self.flags.carry_z = value == 0
        sa = self._to_signed8(a)
        sb = self._to_signed8(b)
        self.flags.carry_v = (sa > 0 and sb > 0 and cn) or (sa < 0 and sb < 0 and not cn)
        self.flags.carry_c = result > 0xFF
        return value

    def _add16(self, x: int, y: int) -> int:
        a = x & 0xFFFF
        b = y & 0xFFFF
        result = (a + b) & 0x1FFFF
        value = result & 0xFFFF
        signed_value = self._to_signed16(value)
        self.flags.carry_n = signed_value < 0
        self.flags.carry_z = value == 0
        sa = self._to_signed16(a)
        sb = self._to_signed16(b)
        cn = self.flags.carry_n
        self.flags.carry_v = (sa > 0 and sb > 0 and cn) or (sa < 0 and sb < 0 and not cn)
        self.flags.carry_c = result > 0xFFFF
        return value

    def _nim(self, x: int, y: int) -> int:
        result = (x & 0xFF) & (y & 0xFF)
        self.flags.carry_z = result == 0
        self.flags.carry_n = not self.flags.carry_z
        self.flags.carry_v = False
        return result & 0xFF

    def _oim(self, x: int, y: int) -> int:
        result = (x | y) & 0xFF
        self.flags.carry_z = result == 0
        self.flags.carry_n = not self.flags.carry_z
        self.flags.carry_v = False
        return result

    def _xim(self, x: int, y: int) -> int:
        result = (x ^ y) & 0xFF
        self.flags.carry_z = result == 0
        self.flags.carry_n = not self.flags.carry_z
        return result

    def _tmm(self, x: int, y: int) -> None:
        x &= 0xFF
        y &= 0xFF
        if x == 0 or y == 0:
            self.flags.carry_n = False
            self.flags.carry_z = True
            self.flags.carry_v = False
        elif y == 0xFF:
            self.flags.carry_n = False
            self.flags.carry_z = False
            self.flags.carry_v = True
        else:
            self.flags.carry_n = True
            self.flags.carry_z = False
            self.flags.carry_v = False

    def _and8(self, x: int, y: int) -> int:
        result = x & y & 0xFF
        self.flags.carry_n = result & 0x80 != 0
        self.flags.carry_z = result == 0
        self.flags.carry_v = False
        return result

    def _bit8(self, x: int, y: int) -> None:
        result = (x & y) & 0xFF
        self.flags.carry_n = result & 0x80 != 0
        self.flags.carry_z = result == 0
        self.flags.carry_v = False

    def _cmp8(self, x: int, y: int) -> None:
        result = (x & 0xFF) - (y & 0xFF)
        value = result & 0xFF
        self.flags.carry_n = value & 0x80 != 0
        self.flags.carry_z = value == 0
        sx = self._to_signed8(x)
        sy = self._to_signed8(y)
        cn = self.flags.carry_n
        self.flags.carry_v = (sx > 0 and sy < 0 and cn) or (sx < 0 and sy > 0 and not cn)
        self.flags.carry_c = result & 0x100 != 0

    def _clr(self) -> int:
        self.flags.carry_n = False
        self.flags.carry_z = True
        self.flags.carry_v = False
        self.flags.carry_c = False
        return 0

    def _com(self, x: int) -> int:
        result = (~x) & 0xFF
        self.flags.carry_n = result & 0x80 != 0
        self.flags.carry_z = result == 0
        self.flags.carry_v = False
        self.flags.carry_c = True
        return result

    def _dec(self, x: int) -> int:
        result = (x - 1) & 0xFF
        self.flags.carry_n = result & 0x80 != 0
        self.flags.carry_z = result == 0
        self.flags.carry_v = x & 0xFF == 0x80
        return result

    def _eor8(self, x: int, y: int) -> int:
        result = (x ^ y) & 0xFF
        self.flags.carry_n = result & 0x80 != 0
        self.flags.carry_z = result == 0
        self.flags.carry_v = False
        return result

    def _inc(self, x: int) -> int:
        result = (x + 1) & 0xFF
        self.flags.carry_n = result & 0x80 != 0
        self.flags.carry_z = result == 0
        self.flags.carry_v = x & 0xFF == 0x7F
        return result

    def _lda(self, value: int) -> int:
        value &= 0xFF
        self.flags.carry_n = value & 0x80 != 0
        self.flags.carry_z = value == 0
        self.flags.carry_v = False
        return value

    def _lsr(self, x: int) -> int:
        result = (x & 0xFF) >> 1
        self.flags.carry_n = False
        self.flags.carry_z = result == 0
        self.flags.carry_c = (x & 0x01) != 0
        self.flags.carry_v = self.flags.carry_n != self.flags.carry_c
        return result & 0xFF

    def _neg(self, x: int) -> int:
        result = (- (x & 0xFF)) & 0x1FF
        value = result & 0xFF
        self.flags.carry_n = value & 0x80 != 0
        self.flags.carry_z = value == 0
        self.flags.carry_v = value == 0x80
        self.flags.carry_c = value == 0x00
        return value

    def _ora(self, x: int, y: int) -> int:
        result = (x | y) & 0xFF
        self.flags.carry_n = result & 0x80 != 0
        self.flags.carry_z = result == 0
        self.flags.carry_v = False
        return result

    def _sub8(self, x: int, y: int) -> int:
        result = (x & 0xFF) - (y & 0xFF)
        out = result & 0xFF
        cn = out & 0x80 != 0
        self.flags.carry_n = cn
        self.flags.carry_z = out == 0
        sx = self._to_signed8(x)
        sy = self._to_signed8(y)
        self.flags.carry_v = (sx > 0 and sy < 0 and cn) or (sx < 0 and sy > 0 and not cn)
        self.flags.carry_c = result & 0x100 != 0
        return out

    def _sbc8(self, x: int, y: int) -> int:
        borrow = 1 if self.flags.carry_c else 0
        result = (x & 0xFF) - (y & 0xFF) - borrow
        out = result & 0xFF
        cn = out & 0x80 != 0
        self.flags.carry_n = cn
        self.flags.carry_z = out == 0
        sx = self._to_signed8(x)
        sy = self._to_signed8(y)
        self.flags.carry_v = (sx > 0 and sy < 0 and cn) or (sx < 0 and sy > 0 and not cn)
        self.flags.carry_c = result & 0x100 != 0
        return out

    def _sta(self, address: int, value: int) -> None:
        value &= 0xFF
        self.flags.carry_n = value & 0x80 != 0
        self.flags.carry_z = value == 0
        self.flags.carry_v = False
        self._store8(address & 0xFFFF, value)

    def _tst(self, value: int) -> None:
        value &= 0xFF
        self.flags.carry_n = value & 0x80 != 0
        self.flags.carry_z = value == 0
        self.flags.carry_v = False
        self.flags.carry_c = False

    def _calc_direct_address(self, operand: int) -> int:
        return operand & 0xFF

    def _calc_indexed_address(self, offset: int) -> int:
        return (self.registers.index + (offset & 0xFF)) & 0xFFFF

    @staticmethod
    def _to_signed16(value: int) -> int:
        value &= 0xFFFF
        return value - 0x10000 if value & 0x8000 else value

    def _cpx(self, value: int) -> None:
        ix = self.registers.index & 0xFFFF
        operand = value & 0xFFFF
        diff = (ix - operand) & 0xFFFF
        signed_diff = self._to_signed16(diff)
        self.flags.carry_n = signed_diff < 0
        self.flags.carry_z = diff == 0
        ix_signed = self._to_signed16(self.registers.index)
        op_signed = self._to_signed16(value)
        cn = self.flags.carry_n
        self.flags.carry_v = (ix_signed > 0 and op_signed < 0 and cn) or (
            ix_signed < 0 and op_signed > 0 and not cn
        )

    def _dex(self) -> None:
        self.registers.index = (self.registers.index - 1) & 0xFFFF
        self.flags.carry_z = self.registers.index == 0

    def _des(self) -> None:
        self.registers.stack_pointer = (self.registers.stack_pointer - 1) & 0xFFFF

    def _inx(self) -> None:
        self.registers.index = (self.registers.index + 1) & 0xFFFF
        self.flags.carry_z = self.registers.index == 0

    def _ins(self) -> None:
        self.registers.stack_pointer = (self.registers.stack_pointer + 1) & 0xFFFF

    def _ldx(self, value: int) -> None:
        self.registers.index = value & 0xFFFF
        ix_signed = self._to_signed16(self.registers.index)
        self.flags.carry_n = ix_signed < 0
        self.flags.carry_z = self.registers.index == 0
        self.flags.carry_v = False

    def _lds(self, value: int) -> None:
        self.registers.stack_pointer = value & 0xFFFF
        sp_signed = self._to_signed16(self.registers.stack_pointer)
        self.flags.carry_n = sp_signed < 0
        self.flags.carry_z = self.registers.stack_pointer == 0
        self.flags.carry_v = False

    def _stx(self, address: int) -> None:
        addr = address & 0xFFFF
        self._store16(addr, self.registers.index)
        ix_signed = self._to_signed16(self.registers.index)
        self.flags.carry_n = ix_signed < 0
        self.flags.carry_z = self.registers.index == 0
        self.flags.carry_v = False

    def _sts(self, address: int) -> None:
        addr = address & 0xFFFF
        self._store16(addr, self.registers.stack_pointer)
        ix_signed = self._to_signed16(self.registers.index)
        self.flags.carry_n = ix_signed < 0
        self.flags.carry_z = self.registers.index == 0
        self.flags.carry_v = False

    def _branch(self, offset: int, condition: bool) -> None:
        if condition:
            signed_offset = self._to_signed8(offset)
            self.registers.program_counter = (self.registers.program_counter + signed_offset) & 0xFFFF
