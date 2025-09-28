"""Helpers for mapping pygame joystick events to the JR-100 gamepad port."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, Literal, Mapping, Sequence, Tuple

DirectionName = Literal["left", "right", "up", "down", "switch"]
MappingEntry = Sequence[object]

DEFAULT_JOYSTICK_MAPPING: Dict[DirectionName, MappingEntry] = {
    "left": ("axis", 0, -0.5),
    "right": ("axis", 0, 0.5),
    "up": ("axis", 1, -0.5),
    "down": ("axis", 1, 0.5),
    "switch": ("button", 0, 0.5),
}


@dataclass(frozen=True)
class DirectionMapping:
    """Normalized representation of a joystick mapping entry."""

    kind: Literal["axis", "hat", "button"]
    index: int
    threshold: float
    hat_axis: Literal["x", "y"] | None = None

    @classmethod
    def from_entry(cls, entry: object) -> "DirectionMapping":
        if isinstance(entry, cls):
            return entry
        if isinstance(entry, Mapping):
            kind = str(entry.get("kind", "")).lower()
            index = int(entry.get("index", 0))
            threshold = float(entry.get("threshold", 0.0))
            hat_axis = entry.get("hat_axis")
            if hat_axis is not None:
                hat_axis = cls._normalize_hat_axis(hat_axis)
            return cls(cls._validate_kind(kind), index, threshold, hat_axis)
        if not isinstance(entry, (list, tuple)):
            raise ValueError("mapping entry must be a sequence")
        if len(entry) < 3:
            raise ValueError("mapping entry requires three fields")
        kind = cls._validate_kind(str(entry[0]).lower())
        raw_index = entry[1]
        threshold = float(entry[2])
        if kind == "axis" or kind == "button":
            index = int(raw_index)
            return cls(kind, index, threshold)
        if kind == "hat":
            hat_index, hat_axis = cls._parse_hat_index(raw_index)
            return cls(kind, hat_index, threshold, hat_axis)
        raise ValueError("unsupported mapping kind")

    @staticmethod
    def _validate_kind(kind: str) -> Literal["axis", "hat", "button"]:
        if kind not in {"axis", "hat", "button"}:
            raise ValueError(f"unknown mapping kind: {kind}")
        return kind  # type: ignore[return-value]

    @staticmethod
    def _parse_hat_index(raw: object) -> Tuple[int, Literal["x", "y"]]:
        hat_index = 0
        axis_selector: object
        if isinstance(raw, (list, tuple)):
            if len(raw) != 2:
                raise ValueError("hat mapping expects [hat_index, axis]")
            hat_index = int(raw[0])
            axis_selector = raw[1]
        else:
            axis_selector = raw
        axis = DirectionMapping._normalize_hat_axis(axis_selector)
        return hat_index, axis

    @staticmethod
    def _normalize_hat_axis(token: object) -> Literal["x", "y"]:
        value = str(token).lower()
        if value in {"x", "0"}:
            return "x"
        if value in {"y", "1"}:
            return "y"
        raise ValueError(f"invalid hat axis selector: {token}")


@dataclass(eq=True)
class GamepadState:
    """Boolean representation of the JR-100 gamepad bits."""

    left: bool = False
    right: bool = False
    up: bool = False
    down: bool = False
    switch: bool = False

    def as_kwargs(self) -> Dict[str, bool]:
        return {
            "left": self.left,
            "right": self.right,
            "up": self.up,
            "down": self.down,
            "switch": self.switch,
        }


class JoystickAdapter:
    """Convert joystick events into JR-100 gamepad state."""

    def __init__(
        self,
        mapping: Mapping[DirectionName, object] | None = None,
        *,
        deadzone: float = 0.15,
    ) -> None:
        self._deadzone = max(deadzone, 0.0)
        self._mapping = self._normalize_mapping(mapping or DEFAULT_JOYSTICK_MAPPING)
        self._axes: Dict[int, float] = {}
        self._hats: Dict[int, Tuple[int, int]] = {}
        self._buttons: Dict[int, bool] = {}
        self._state = GamepadState()

    @staticmethod
    def _normalize_mapping(mapping: Mapping[DirectionName, object]) -> Dict[DirectionName, DirectionMapping]:
        normalized: Dict[DirectionName, DirectionMapping] = {}
        for direction in ("left", "right", "up", "down", "switch"):
            entry = mapping.get(direction)
            if entry is None:
                entry = DEFAULT_JOYSTICK_MAPPING[direction]
            normalized[direction] = DirectionMapping.from_entry(entry)
        return normalized

    def reset(self) -> None:
        self._axes.clear()
        self._hats.clear()
        self._buttons.clear()
        self._update_state()

    def update_axis(self, index: int, value: float) -> bool:
        filtered = 0.0 if abs(value) < self._deadzone else float(value)
        if self._axes.get(index) == filtered:
            return False
        self._axes[index] = filtered
        return self._update_state()

    def update_hat(self, hat_index: int, value: Sequence[int]) -> bool:
        x = int(value[0]) if len(value) > 0 else 0
        y = int(value[1]) if len(value) > 1 else 0
        current = self._hats.get(hat_index)
        if current == (x, y):
            return False
        self._hats[hat_index] = (x, y)
        return self._update_state()

    def update_button(self, index: int, pressed: bool) -> bool:
        if self._buttons.get(index) == pressed:
            return False
        self._buttons[index] = bool(pressed)
        return self._update_state()

    def current_state(self) -> GamepadState:
        return self._state

    def apply_to_port(self, port: object) -> None:
        if hasattr(port, "set_gamepad_state"):
            port.set_gamepad_state(**self._state.as_kwargs())

    def _update_state(self) -> bool:
        new_state = self._compute_state()
        if new_state == self._state:
            return False
        self._state = new_state
        return True

    def _compute_state(self) -> GamepadState:
        states: Dict[DirectionName, bool] = {"left": False, "right": False, "up": False, "down": False, "switch": False}
        for direction, mapping in self._mapping.items():
            if mapping.kind == "axis":
                if self._axis_active(mapping.index, mapping.threshold):
                    states[direction] = True
            elif mapping.kind == "hat":
                if self._hat_active(mapping.index, mapping.hat_axis or "x", mapping.threshold):
                    states[direction] = True
            elif mapping.kind == "button":
                if self._button_active(mapping.index):
                    states[direction] = True
        return GamepadState(**states)

    def _axis_active(self, index: int, threshold: float) -> bool:
        value = self._axes.get(index, 0.0)
        if threshold >= 0:
            return value >= max(threshold, self._deadzone)
        return value <= min(threshold, -self._deadzone)

    def _hat_active(self, hat_index: int, axis: Literal["x", "y"], threshold: float) -> bool:
        value = self._hats.get(hat_index)
        if value is None:
            return False
        component = value[0] if axis == "x" else value[1]
        return component == int(threshold)

    def _button_active(self, index: int) -> bool:
        return self._buttons.get(index, False)


def load_mapping_file(
    path: str | Path,
    *,
    fallback: Mapping[DirectionName, object] | None = None,
) -> Dict[DirectionName, DirectionMapping]:
    fallback_mapping = fallback or DEFAULT_JOYSTICK_MAPPING
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, Mapping):
            raise ValueError("mapping file must contain a JSON object")
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return JoystickAdapter._normalize_mapping(fallback_mapping)  # type: ignore[arg-type]

    normalized: Dict[DirectionName, DirectionMapping] = {}
    for direction in ("left", "right", "up", "down", "switch"):
        entry = data.get(direction)
        if entry is None:
            entry = fallback_mapping[direction]
        try:
            normalized[direction] = DirectionMapping.from_entry(entry)
        except ValueError:
            normalized[direction] = DirectionMapping.from_entry(fallback_mapping[direction])
    return normalized


__all__ = [
    "DEFAULT_JOYSTICK_MAPPING",
    "DirectionMapping",
    "GamepadState",
    "JoystickAdapter",
    "load_mapping_file",
]
