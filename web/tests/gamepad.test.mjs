import test from "node:test";
import assert from "node:assert/strict";
import {
  DEFAULT_GAMEPAD_SETTINGS,
  GamepadController,
  gamepadMask,
} from "../gamepad.js";

function pad({ axes = [0, 0], pressed = [] } = {}) {
  const buttons = Array.from({ length: 16 }, (_, index) => ({ pressed: pressed.includes(index), value: pressed.includes(index) ? 1 : 0 }));
  return { axes, buttons };
}

test("standard d-pad and axis controls map to the JR-100 port", () => {
  assert.equal(gamepadMask(pad({ axes: [-1, -1], pressed: [0] })), 0x16);
  assert.equal(gamepadMask(pad({ pressed: [15, 13] })), 0x09);
});

test("the switch button can be configured", () => {
  assert.equal(gamepadMask(pad({ pressed: [7] }), { switchButton: 7 }), 0x10);
});

test("a visible virtual keyboard never captures gamepad controls", () => {
  const masks = [];
  const input = { setJoystickMask: (mask) => masks.push(mask) };
  const controller = new GamepadController(
    input,
    DEFAULT_GAMEPAD_SETTINGS,
    () => {},
    () => [pad({ axes: [1, -1], pressed: [0, 8] })],
  );

  controller.update();

  assert.deepEqual(masks, [0x15]);
});
