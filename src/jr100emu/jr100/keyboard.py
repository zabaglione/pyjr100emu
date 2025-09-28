"""JR-100 keyboard matrix handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

KEY_MATRIX_ROWS = 16
ROW_MASK = 0xFF


@dataclass
class JR100Keyboard:
    """Naive matrix keyboard model.

    JR-100 uses 16 rows with 8 bits each. ビットは 0 が押下状態を表す。
    """

    _matrix: List[int] = field(default_factory=lambda: [ROW_MASK] * KEY_MATRIX_ROWS)

    def set_key_matrix(self, matrix: Iterable[int]) -> None:
        values = list(matrix)
        if len(values) != KEY_MATRIX_ROWS:
            raise ValueError("matrix size must be 16 rows")
        self._matrix = [value & ROW_MASK for value in values]

    def get_key_matrix(self) -> List[int]:
        return list(self._matrix)

    def press(self, row: int, bit: int) -> None:
        if not (0 <= row < KEY_MATRIX_ROWS and 0 <= bit < 8):
            raise ValueError("row/bit out of range")
        self._matrix[row] &= ~(1 << bit)

    def release(self, row: int, bit: int) -> None:
        if not (0 <= row < KEY_MATRIX_ROWS and 0 <= bit < 8):
            raise ValueError("row/bit out of range")
        self._matrix[row] |= 1 << bit

    def clear(self) -> None:
        self._matrix = [ROW_MASK] * KEY_MATRIX_ROWS
