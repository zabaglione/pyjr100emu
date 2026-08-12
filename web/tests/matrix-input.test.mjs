import test from "node:test";
import assert from "node:assert/strict";
import { MatrixInputScheduler } from "../matrix-input.js";

function runFrame(scheduler) {
  scheduler.beforeFrame();
  scheduler.afterFrame();
}

test("a tap shorter than one browser frame remains visible for two core frames", () => {
  const events = [];
  const scheduler = new MatrixInputScheduler((...event) => events.push(event));

  scheduler.key(1, 0, true);
  scheduler.key(1, 0, false);
  runFrame(scheduler);
  assert.deepEqual(events, [[1, 0, true]]);
  runFrame(scheduler);
  assert.deepEqual(events, [[1, 0, true], [1, 0, false]]);
});

test("a modifier is scanned one frame before the chord key", () => {
  const events = [];
  const scheduler = new MatrixInputScheduler((...event) => events.push(event));

  scheduler.key(0, 0, true);
  scheduler.key(7, 0, true);
  scheduler.beforeFrame();
  assert.deepEqual(events, [[0, 0, true]]);
  scheduler.afterFrame();
  scheduler.beforeFrame();
  assert.deepEqual(events, [[0, 0, true], [7, 0, true]]);
});

test("clearing input releases active keys immediately", () => {
  const events = [];
  const scheduler = new MatrixInputScheduler((...event) => events.push(event));
  scheduler.key(0, 1, true);
  scheduler.beforeFrame();

  scheduler.clear();

  assert.deepEqual(events, [[0, 1, true], [0, 1, false]]);
});
