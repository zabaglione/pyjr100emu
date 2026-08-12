import test from "node:test";
import assert from "node:assert/strict";
import { gamepadMask } from "../gamepad.js";

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
