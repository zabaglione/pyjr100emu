"""JR-100 keyboard matrix handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

KEY_MATRIX_ROWS = 9
ROW_MASK = 0x1F


@dataclass
class JR100Keyboard:
    """Naive matrix keyboard model.

    JR-100 uses a 9×5 matrix whereビット1が押下状態を表し、VIA 側で反転される。
    """

    _matrix: List[int] = field(default_factory=lambda: [0x00] * KEY_MATRIX_ROWS)

    def set_key_matrix(self, matrix: Iterable[int]) -> None:
        values = list(matrix)
        if len(values) != KEY_MATRIX_ROWS:
            raise ValueError("matrix size must be 9 rows")
        self._matrix = [value & ROW_MASK for value in values]

    def get_key_matrix(self) -> List[int]:
        return list(self._matrix)

    def press(self, row: int, bit: int) -> None:
        if not (0 <= row < KEY_MATRIX_ROWS and 0 <= bit < 5):
            raise ValueError("row/bit out of range")
        mask = 1 << bit
        self._matrix[row] = (self._matrix[row] | mask) & ROW_MASK

    def release(self, row: int, bit: int) -> None:
        if not (0 <= row < KEY_MATRIX_ROWS and 0 <= bit < 5):
            raise ValueError("row/bit out of range")
        mask = ~(1 << bit)
        self._matrix[row] = (self._matrix[row] & mask) & ROW_MASK

    def clear(self) -> None:
        self._matrix = [0x00] * KEY_MATRIX_ROWS
