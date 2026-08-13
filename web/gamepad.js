export const DEFAULT_GAMEPAD_SETTINGS = Object.freeze({
  gamepadIndex: 0,
  switchButton: 0,
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
  constructor(
    input,
    settings = DEFAULT_GAMEPAD_SETTINGS,
    onStatus,
    getGamepads = () => navigator.getGamepads?.() || [],
  ) {
    this.input = input;
    this.settings = { ...DEFAULT_GAMEPAD_SETTINGS, ...settings };
    this.onStatus = onStatus;
    this.getGamepads = getGamepads;
    this.selectedIndex = this.settings.gamepadIndex;
  }

  update() {
    const gamepads = this.getGamepads() || [];
    const gamepad = gamepads[this.selectedIndex] || [...gamepads].find(Boolean);
    if (!gamepad) {
      this.input.setJoystickMask(0);
      this.onStatus?.("No gamepad detected");
      return;
    }

    this.onStatus?.(gamepad.id || "Gamepad connected");
    this.input.setJoystickMask(gamepadMask(gamepad, this.settings));
  }
}
