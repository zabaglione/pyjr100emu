import test from "node:test";
import assert from "node:assert/strict";
import { InputRouter, PhysicalKeyboardController } from "../input.js";
import { resolveKeyboardChord } from "../keymap.js";

const cell = { row: 1, bit: 0 };

test("input sources share a pressed matrix cell", () => {
  const keys = [];
  const router = new InputRouter((...args) => keys.push(args), () => {});

  router.press("physical:KeyA", cell);
  router.press("virtual:r1b0", cell);
  router.release("physical:KeyA");
  assert.deepEqual(keys, [[1, 0, true]]);
  assert.equal(router.isPressed(1, 0), true);

  router.release("virtual:r1b0");
  assert.deepEqual(keys, [[1, 0, true], [1, 0, false]]);
});

test("a chord shares modifier state and releases every matrix cell", () => {
  const keys = [];
  const router = new InputRouter((...args) => keys.push(args), () => {});

  router.pressChord("shortcut:left", [{ row: 0, bit: 0 }, { row: 4, bit: 0 }]);
  router.release("shortcut:left");

  assert.deepEqual(keys, [
    [0, 0, true], [4, 0, true], [0, 0, false], [4, 0, false],
  ]);
});

test("uppercase host letters do not leave JR shift held", () => {
  const keys = [];
  const router = new InputRouter((...args) => keys.push(args), () => {});
  const keyboard = new PhysicalKeyboardController(router, resolveKeyboardChord);

  keyboard.keyDown({ code: "ShiftLeft", key: "Shift", repeat: false });
  keyboard.keyDown({ code: "KeyA", key: "A", repeat: false, shiftKey: true });

  assert.equal(router.isPressed(0, 1), false);
  assert.equal(router.isPressed(1, 0), true);
});

test("host shift is synthesized with the character instead of sent early", () => {
  const keys = [];
  const router = new InputRouter((...args) => keys.push(args), () => {});
  const keyboard = new PhysicalKeyboardController(router, resolveKeyboardChord);

  keyboard.keyDown({ code: "ShiftLeft", key: "Shift", repeat: false });
  assert.deepEqual(keys, []);
  keyboard.keyDown({ code: "Digit1", key: "!", repeat: false, shiftKey: true });

  assert.deepEqual(keys, [[0, 1, true], [3, 0, true]]);
});

test("momentary release preserves latched modifiers and joystick clearing is masked", () => {
  const keys = [];
  const masks = [];
  const router = new InputRouter((...args) => keys.push(args), (mask) => masks.push(mask));

  router.toggleLatch("latch:shift", { row: 0, bit: 1 });
  router.press("physical:KeyA", cell);
  router.setJoystickMask(0x1f);
  router.releaseMomentary();

  assert.equal(router.isPressed(0, 1), true);
  assert.equal(router.isPressed(1, 0), false);
  assert.deepEqual(masks, [0x1f]);
  router.clear();
  assert.equal(router.isPressed(0, 1), false);
  assert.deepEqual(masks, [0x1f, 0]);
  assert.equal(keys.at(-1)[2], false);
});

test("a source prefix can release virtual keys without touching physical keys", () => {
  const keys = [];
  const router = new InputRouter((...args) => keys.push(args), () => {});
  router.press("physical:KeyA", cell);
  router.press("virtual:r1b0", cell);
  router.releasePrefix("virtual:");
  assert.equal(router.isPressed(1, 0), true);
  router.release("physical:KeyA");
  assert.equal(router.isPressed(1, 0), false);
  assert.deepEqual(keys, [[1, 0, true], [1, 0, false]]);
});
