import test from "node:test";
import assert from "node:assert/strict";
import { InputRouter } from "../input.js";

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
