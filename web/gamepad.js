export const DEFAULT_GAMEPAD_SETTINGS = Object.freeze({
  gamepadIndex: 0,
  switchButton: 0,
  vkbToggleButton: 8,
  vkbAButton: 0,
  vkbBButton: 1,
  vkbXButton: 2,
  vkbShiftButton: 4,
  vkbCtrlButton: 5,
});

export function gamepadMask(gamepad, settings = DEFAULT_GAMEPAD_SETTINGS) {
  const buttons = gamepad?.buttons || [];
  const axes = gamepad?.axes || [];
  const pressed = (index) => Boolean(buttons[index]?.pressed || buttons[index]?.value > 0.5);
  const axis = (index) => Number(axes[index] || 0);
  let mask = 0;
  if (axis(0) < -0.4 || pressed(14)) mask |= 0x02;
  if (axis(0) > 0.4 || pressed(15)) mask |= 0x01;
  if (axis(1) < -0.4 || pressed(12)) mask |= 0x04;
  if (axis(1) > 0.4 || pressed(13)) mask |= 0x08;
  if (pressed(settings.switchButton)) mask |= 0x10;
  return mask;
}

function buttonPressed(gamepad, index) {
  return Boolean(gamepad?.buttons?.[index]?.pressed || gamepad?.buttons?.[index]?.value > 0.5);
}

export class GamepadController {
  constructor(input, keyboard, settings, onStatus) {
    this.input = input;
    this.keyboard = keyboard;
    this.settings = { ...DEFAULT_GAMEPAD_SETTINGS, ...settings };
    this.onStatus = onStatus;
    this.previousButtons = new Map();
    this.nextDirectionTime = 0;
    this.lastDirection = { x: 0, y: 0 };
    this.selectedIndex = this.settings.gamepadIndex;
  }

  update(now) {
    const gamepads = navigator.getGamepads?.() || [];
    const gamepad = gamepads[this.selectedIndex] || [...gamepads].find(Boolean);
    if (!gamepad) {
      this.input.setJoystickMask(0);
      this.keyboard.releaseGamepadKey();
      this.keyboard.hideGamepadCursor?.();
      this._releaseSpecialKeys();
      this.onStatus?.("No gamepad detected");
      return;
    }

    this.onStatus?.(gamepad.id || "Gamepad connected");
    const toggle = this._edge(gamepad, this.settings.vkbToggleButton);
    if (toggle) this.keyboard.toggle();

    if (this.keyboard.active) {
      this.input.setJoystickMask(0);
      this._updateVirtualKeyboard(gamepad, now);
    } else {
      this.keyboard.releaseGamepadKey();
      this.keyboard.hideGamepadCursor?.();
      this._releaseSpecialKeys();
      this.input.setJoystickMask(gamepadMask(gamepad, this.settings));
    }
    this._rememberButtons(gamepad);
  }

  _updateVirtualKeyboard(gamepad, now) {
    const x = this._axisDirection(gamepad, 0, 14, 15);
    const y = this._axisDirection(gamepad, 1, 12, 13);
    if (x !== 0 || y !== 0) {
      const changed = x !== this.lastDirection.x || y !== this.lastDirection.y;
      if (changed || now >= this.nextDirectionTime) {
        this.keyboard.move(y, x);
        this.nextDirectionTime = now + (changed ? 300 : 70);
      }
    }
    this.lastDirection = { x, y };

    const current = this.keyboard.currentCell();
    if (buttonPressed(gamepad, this.settings.vkbAButton)) this.keyboard.holdGamepadKey(current);
    else this.keyboard.releaseGamepadKey();
    this.keyboard.holdGamepadSpecial("SPACE", buttonPressed(gamepad, this.settings.vkbBButton));
    this.keyboard.holdGamepadSpecial("RETURN", buttonPressed(gamepad, this.settings.vkbXButton));
    this.keyboard.holdGamepadSpecial("SHIFT", buttonPressed(gamepad, this.settings.vkbShiftButton));
    this.keyboard.holdGamepadSpecial("CTRL", buttonPressed(gamepad, this.settings.vkbCtrlButton));
  }

  _axisDirection(gamepad, axisIndex, negativeButton, positiveButton) {
    const axis = Number(gamepad.axes?.[axisIndex] || 0);
    if (axis < -0.4 || buttonPressed(gamepad, negativeButton)) return -1;
    if (axis > 0.4 || buttonPressed(gamepad, positiveButton)) return 1;
    return 0;
  }

  _edge(gamepad, index) {
    const next = buttonPressed(gamepad, index);
    return next && !this.previousButtons.get(index);
  }

  _rememberButtons(gamepad) {
    for (const [index, button] of (gamepad.buttons || []).entries()) {
      this.previousButtons.set(index, Boolean(button?.pressed || button?.value > 0.5));
    }
  }

  _releaseSpecialKeys() {
    for (const label of ["SPACE", "RETURN", "SHIFT", "CTRL"]) {
      this.keyboard.holdGamepadSpecial(label, false);
    }
    this.lastDirection = { x: 0, y: 0 };
  }
}
