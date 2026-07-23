"""Program-mode lockstep convention: reset-exempt VIA storage is normalised.

R6522 RES preserves the T1/T2 counters, latches, and the shift register.
After the program-mode warmup + reset sequence those registers would carry
warmup residue, which a cold-started DUT cannot reproduce. Program-mode
lockstep runs therefore zero them as a comparison convention (parallel to
the boot comparison convention in _normalise_boot_state).
"""

from __future__ import annotations

from jr100emu import debug_runner
from jr100emu.jr100.computer import JR100Computer


def test_normalise_program_via_state_zeroes_reset_exempt_storage() -> None:
    computer = JR100Computer()
    computer.tick(1000)
    state = computer.via._state
    state.timer1 = -1
    state.timer2 = 0x1234
    state.latch1 = 0x5678
    state.latch2 = 0x9ABC
    state.SR = 0xA5

    debug_runner._normalise_program_via_state(computer)

    assert state.timer1 == 0
    assert state.timer2 == 0
    assert state.latch1 == 0
    assert state.latch2 == 0
    assert state.SR == 0
