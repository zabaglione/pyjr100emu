"""JR-100 keyboard matrix handling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

KEY_MATRIX_ROWS = 9
ROW_MASK = 0x1F


def _default_matrix() -> List[int]:
    """Return the idle keyboard matrix (all keys released)."""

    return [ROW_MASK] * KEY_MATRIX_ROWS


@dataclass
class JR100Keyboard:
    """JR-100 の 9×5 キーマトリクスをアクティブローで表現する。"""

    _matrix: List[int] = field(default_factory=_default_matrix)

    def set_key_matrix(self, matrix: Iterable[int]) -> None:
        values = [value & ROW_MASK for value in matrix]
        if len(values) < KEY_MATRIX_ROWS:
            raise ValueError("matrix size must be at least 9 rows")
        self._matrix = values[:KEY_MATRIX_ROWS]

    def get_key_matrix(self) -> List[int]:
        return list(self._matrix)

    def press(self, row: int, bit: int) -> None:
        if not (0 <= row < KEY_MATRIX_ROWS and 0 <= bit < 5):
            raise ValueError("row/bit out of range")
        mask = 1 << bit
        self._matrix[row] &= ~mask & ROW_MASK

    def release(self, row: int, bit: int) -> None:
        if not (0 <= row < KEY_MATRIX_ROWS and 0 <= bit < 5):
            raise ValueError("row/bit out of range")
        mask = 1 << bit
        self._matrix[row] |= mask
        self._matrix[row] &= ROW_MASK

    def clear(self) -> None:
        self._matrix = _default_matrix()
