"""デバイス抽象レイヤーとゲームパッド管理クラス。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Set, Tuple

from jr100emu.io.joystick import (
    DEFAULT_JOYSTICK_MAPPING,
    JoystickAdapter,
    load_mapping_file,
)


class GamepadBackend(Protocol):
    """ゲームパッド入力を `JoystickAdapter` に反映させるバックエンド。"""

    def initialize(self) -> bool:
        """バックエンドを初期化し、使用可能かどうかを返す。"""

    def poll(self, adapter: JoystickAdapter) -> bool:
        """現在入力を取得し、状態が変化したかどうかを返す。"""

    def reset(self) -> None:
        """バックエンド内部状態をリセットする。"""

    def close(self) -> None:
        """リソースを解放する。"""


class PygameGamepadBackend:
    """pygame を利用したゲームパッドポーリング実装。"""

    def __init__(
        self,
        *,
        device_index: int | None = None,
        name_filter: str | None = None,
        allow_background: bool = True,
    ) -> None:
        self._device_index = device_index
        self._name_filter = name_filter.lower() if name_filter else None
        self._allow_background = allow_background
        self._pygame = None
        self._initialized: bool = False
        self._joysticks: Dict[int, object] = {}
        self._event_types: list[int] = []
        self._registered_indices: set[int] = set()
        self._instance_to_index: Dict[int, int] = {}

    # ------------------------------------------------------------------
    # pygame 連携
    # ------------------------------------------------------------------
    def initialize(self) -> bool:
        if self._initialized:
            return True
        try:
            import pygame  # type: ignore
        except Exception:
            return False

        self._pygame = pygame
        if self._allow_background:
            os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")

        try:
            if not pygame.get_init():
                pygame.init()
        except Exception:
            # pygame.init() が失敗してもジョイスティック単体で初期化を試みる
            pass

        try:
            pygame.joystick.init()
        except Exception:
            return False

        self._event_types = []
        for event_name in ("JOYDEVICEADDED", "JOYDEVICEREMOVED"):
            event_type = getattr(pygame, event_name, None)
            if isinstance(event_type, int):
                self._event_types.append(event_type)

        self._register_existing()
        self._initialized = True
        return True

    def poll(self, adapter: JoystickAdapter) -> bool:
        if not self._initialized:
            if not self.initialize():
                return False

        assert self._pygame is not None

        try:
            self._pygame.event.pump()
        except Exception:
            return False

        # 定期的にフルスキャンして新規接続を検出する
        self._register_existing()

        if self._event_types:
            for event in self._pygame.event.get(self._event_types):
                if event.type == getattr(self._pygame, "JOYDEVICEADDED", None):
                    self._register_device_event(event)
                elif event.type == getattr(self._pygame, "JOYDEVICEREMOVED", None):
                    self._remove_device_event(event)

        if not self._joysticks:
            return False

        changed = False
        for instance_id, joystick in list(self._joysticks.items()):
            try:
                num_axes = joystick.get_numaxes()
                for axis in range(num_axes):
                    value = float(joystick.get_axis(axis))
                    changed |= adapter.update_axis(axis, value)

                num_hats = joystick.get_numhats()
                for hat in range(num_hats):
                    value = joystick.get_hat(hat)
                    if isinstance(value, Iterable):
                        changed |= adapter.update_hat(hat, tuple(value))
                    else:
                        changed |= adapter.update_hat(hat, (0, 0))

                num_buttons = joystick.get_numbuttons()
                for button in range(num_buttons):
                    pressed = bool(joystick.get_button(button))
                    changed |= adapter.update_button(button, pressed)
            except Exception:
                self._remove_instance(instance_id)

        return changed

    def reset(self) -> None:
        self._dispose_joysticks()
        self._initialized = False

    def close(self) -> None:
        self._dispose_joysticks()
        if self._pygame is not None:
            try:
                self._pygame.joystick.quit()
            except Exception:
                pass
        self._initialized = False

    # ------------------------------------------------------------------
    # 内部ヘルパ
    # ------------------------------------------------------------------
    def _register_existing(self) -> None:
        if self._pygame is None:
            return
        joystick_mod = self._pygame.joystick
        count = joystick_mod.get_count()
        for index in range(count):
            self._register_index(index)

    def _register_device_event(self, event: object) -> None:
        index = int(getattr(event, "device_index", -1))
        if index >= 0:
            self._register_index(index)

    def _remove_device_event(self, event: object) -> None:
        instance_id = int(getattr(event, "instance_id", getattr(event, "which", -1)))
        if instance_id >= 0:
            self._remove_instance(instance_id)

    def _register_index(self, index: int) -> None:
        if self._pygame is None:
            return
        if self._device_index is not None and index != self._device_index:
            return
        if index in self._registered_indices:
            return
        try:
            joystick = self._pygame.joystick.Joystick(index)
            joystick.init()
        except Exception:
            return

        if not self._should_use_name(joystick):
            try:
                joystick.quit()
            except Exception:
                pass
            return

        instance_id = self._instance_id(joystick)
        if instance_id in self._joysticks:
            try:
                joystick.quit()
            except Exception:
                pass
            return
        self._joysticks[instance_id] = joystick
        self._registered_indices.add(index)
        self._instance_to_index[instance_id] = index

    def _remove_instance(self, instance_id: int) -> None:
        joystick = self._joysticks.pop(instance_id, None)
        if joystick is not None:
            try:
                joystick.quit()
            except Exception:
                pass
        index = self._instance_to_index.pop(instance_id, None)
        if index is not None:
            self._registered_indices.discard(index)

    def _dispose_joysticks(self) -> None:
        for joystick in list(self._joysticks.values()):
            try:
                joystick.quit()
            except Exception:
                pass
        self._joysticks.clear()
        self._registered_indices.clear()
        self._instance_to_index.clear()

    def _should_use_name(self, joystick: object) -> bool:
        if self._name_filter is None:
            return True
        try:
            name = joystick.get_name().lower()
        except Exception:
            return False
        return self._name_filter in name

    @staticmethod
    def _instance_id(joystick: object) -> int:
        getter = getattr(joystick, "get_instance_id", None)
        if callable(getter):
            try:
                return int(getter())
            except Exception:
                pass
        alt = getattr(joystick, "get_id", None)
        if callable(alt):
            try:
                return int(alt())
            except Exception:
                pass
        return id(joystick)


DEFAULT_DIRECTION_KEY_MATRIX: Dict[str, Optional[Sequence[int]]] = {
    "left": (6, 1),   # J
    "right": (6, 3),  # L
    "up": (5, 2),     # I
    "down": (6, 2),   # K
    "switch": (8, 1),  # SPACE
}


@dataclass
class GamepadDevice:
    """JR-100 の拡張 I/O ポートへゲームパッド状態を書き込むデバイス。"""

    port: Optional[object] = None
    mapping: Mapping[str, object] = field(default_factory=lambda: DEFAULT_JOYSTICK_MAPPING)
    deadzone: float = 0.15
    backend: Optional[GamepadBackend] = None
    keyboard: Optional[object] = None
    keyboard_mapping: Optional[Mapping[str, Optional[Sequence[int]]]] = None

    def __post_init__(self) -> None:
        self._deadzone = max(self.deadzone, 0.0)
        self._adapter = JoystickAdapter(self.mapping, deadzone=self._deadzone)
        self._backend_ready = False
        self._poll_count = 0
        self._pressed_keys: Dict[Tuple[int, int], str] = {}
        mapping = self.keyboard_mapping or DEFAULT_DIRECTION_KEY_MATRIX
        self.keyboard_mapping = mapping
        self._keyboard_mapping = self._normalize_keyboard_mapping(mapping)
        if self.port is not None:
            self._adapter.apply_to_port(self.port)

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------
    def attach_port(self, port: object) -> None:
        self.port = port
        self._adapter.apply_to_port(port)

    def attach_keyboard(self, keyboard: object) -> None:
        self.keyboard = keyboard
        self._pressed_keys.clear()
        self._sync_keyboard_state(self._adapter.current_state())

    def set_keyboard_mapping(self, mapping: Mapping[str, Optional[Sequence[int]]]) -> None:
        self.keyboard_mapping = mapping
        self._keyboard_mapping = self._normalize_keyboard_mapping(mapping)
        self._pressed_keys.clear()
        self._sync_keyboard_state(self._adapter.current_state())

    def set_backend(self, backend: Optional[GamepadBackend]) -> None:
        if self.backend is backend:
            return
        if self.backend is not None:
            try:
                self.backend.close()
            except Exception:
                pass
        self.backend = backend
        self._backend_ready = False

    def enable_pygame_backend(
        self,
        *,
        device_index: int | None = None,
        name_filter: str | None = None,
        allow_background: bool = True,
    ) -> None:
        self.set_backend(
            PygameGamepadBackend(
                device_index=device_index,
                name_filter=name_filter,
                allow_background=allow_background,
            )
        )

    def disable(self) -> None:
        self.set_backend(None)

    def set_deadzone(self, deadzone: float) -> None:
        self._deadzone = max(deadzone, 0.0)
        self._adapter = JoystickAdapter(self.mapping, deadzone=self._deadzone)
        if self.port is not None:
            self._adapter.apply_to_port(self.port)
        self._backend_ready = False
        self._sync_keyboard_state(self._adapter.current_state())

    def set_mapping(self, mapping: Mapping[str, object]) -> None:
        self.mapping = mapping
        self._adapter = JoystickAdapter(mapping, deadzone=self._deadzone)
        if self.port is not None:
            self._adapter.apply_to_port(self.port)
        self._sync_keyboard_state(self._adapter.current_state())

    def load_mapping(self, path: str) -> None:
        mapping = load_mapping_file(path, fallback=DEFAULT_JOYSTICK_MAPPING)
        self.set_mapping(mapping)

    def load_keyboard_mapping(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except OSError as exc:
            raise RuntimeError(f"ジョイスティックキーマップの読み込みに失敗しました: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"ジョイスティックキーマップが不正な JSON です: {exc}") from exc

        if not isinstance(data, dict):
            raise RuntimeError("ジョイスティックキーマップは JSON オブジェクトで指定してください")
        normalized: Dict[str, Optional[Sequence[int]]] = {}
        for label, value in data.items():
            normalized[label] = value
        self.set_keyboard_mapping(normalized)

    def current_state(self):
        return self._adapter.current_state()

    def poll(self) -> bool:
        self._poll_count += 1
        if self.backend is None:
            return False
        if not self._backend_ready:
            self._backend_ready = self.backend.initialize()
            if not self._backend_ready:
                return False
        changed = self.backend.poll(self._adapter)
        if changed and self.port is not None:
            self._adapter.apply_to_port(self.port)
        if changed:
            self._sync_keyboard_state(self._adapter.current_state())
        return changed

    def reset(self) -> None:
        self._adapter.reset()
        if self.port is not None:
            self._adapter.apply_to_port(self.port)
        if self.backend is not None:
            try:
                self.backend.reset()
            except Exception:
                pass
        self._backend_ready = False
        if self.keyboard is not None:
            self._release_all_keyboard()

    @property
    def poll_count(self) -> int:
        return self._poll_count

    # ------------------------------------------------------------------
    # Keyboard mirroring helpers
    # ------------------------------------------------------------------
    def _sync_keyboard_state(self, state) -> None:
        if self.keyboard is None or not self._keyboard_mapping:
            return

        desired_keys: Dict[Tuple[int, int], str] = {}
        for label in self._active_labels(state):
            entries = self._keyboard_mapping.get(label)
            if not entries:
                continue
            for row, bit in entries:
                desired_keys[(row, bit)] = label

        # Press new keys
        for key, label in desired_keys.items():
            if key not in self._pressed_keys:
                row, bit = key
                self.keyboard.press(row, bit)
                self._pressed_keys[key] = label

        # Release keys no longer required
        for key in list(self._pressed_keys.keys()):
            if key not in desired_keys:
                row, bit = key
                self.keyboard.release(row, bit)
                self._pressed_keys.pop(key, None)

    def _release_all_keyboard(self) -> None:
        if self.keyboard is None:
            self._pressed_keys.clear()
            return
        for row, bit in list(self._pressed_keys.keys()):
            self.keyboard.release(row, bit)
        self._pressed_keys.clear()

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------
    def _normalize_keyboard_mapping(
        self, mapping: Mapping[str, Optional[Sequence[int]]]
    ) -> Dict[str, Optional[List[Tuple[int, int]]]]:
        normalized: Dict[str, Optional[List[Tuple[int, int]]]] = {}
        for label, value in mapping.items():
            if value is None:
                normalized[label] = None
                continue
            entries: List[Tuple[int, int]] = []
            if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
                iterable = value
            else:
                iterable = [value]
            for entry in iterable:  # type: ignore[assignment]
                row, bit = self._coerce_row_bit(entry)
                entries.append((row, bit))
            normalized[label] = entries if entries else None
        return normalized

    @staticmethod
    def _coerce_row_bit(value: Sequence[int]) -> Tuple[int, int]:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise RuntimeError(f"row/bit ペアは 2 要素の配列で指定してください: {value}")
        row = int(value[0])
        bit = int(value[1])
        if not (0 <= row <= 8 and 0 <= bit <= 4):
            raise RuntimeError(f"row/bit の値が不正です: {value}")
        return row, bit

    def _active_labels(self, state) -> List[str]:
        labels: List[str] = []
        mapping = self._keyboard_mapping
        if not mapping:
            return labels

        suppressed: Set[str] = set()
        diagonal_specs = [
            ("up_left", state.up and state.left, ("up", "left")),
            ("up_right", state.up and state.right, ("up", "right")),
            ("down_left", state.down and state.left, ("down", "left")),
            ("down_right", state.down and state.right, ("down", "right")),
        ]
        for label, condition, components in diagonal_specs:
            if condition and mapping.get(label):
                labels.append(label)
                suppressed.update(components)

        cardinal_specs = [
            ("up", state.up),
            ("down", state.down),
            ("left", state.left),
            ("right", state.right),
        ]
        for label, condition in cardinal_specs:
            if condition and label not in suppressed and mapping.get(label):
                labels.append(label)

        if getattr(state, "switch", False) and mapping.get("switch"):
            labels.append("switch")

        return labels


__all__ = [
    "GamepadBackend",
    "GamepadDevice",
    "PygameGamepadBackend",
]
