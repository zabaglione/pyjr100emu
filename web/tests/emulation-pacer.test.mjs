import test from "node:test";
import assert from "node:assert/strict";
import { EmulationFramePacer } from "../emulation-pacer.js";

const CYCLES_PER_FRAME = 14_900;
const TARGET_CLOCK_HZ = 894_000;

function measuredClockRate(refreshRate, seconds = 30) {
  const pacer = new EmulationFramePacer();
  pacer.reset(0);
  let frames = 0;
  const refreshes = Math.round(refreshRate * seconds);
  for (let index = 1; index <= refreshes; index += 1) {
    frames += pacer.advance(index * 1000 / refreshRate);
  }
  return frames * CYCLES_PER_FRAME / seconds;
}

for (const refreshRate of [60, 120, 144]) {
  test(`emulation stays at the JR-100 clock on a ${refreshRate} Hz display`, () => {
    const measured = measuredClockRate(refreshRate);
    const relativeError = Math.abs(measured - TARGET_CLOCK_HZ) / TARGET_CLOCK_HZ;

    assert.ok(relativeError <= 0.005, `${measured} cycles/s is outside 0.5%`);
  });
}

test("a short rendering stall is caught up in bounded logical frames", () => {
  const pacer = new EmulationFramePacer({ maxCatchUpFrames: 4 });
  pacer.reset(0);

  assert.equal(pacer.advance(40), 2);
  assert.equal(pacer.advance(50), 1);
});

test("catch-up frames beyond one dispatch remain pending", () => {
  const pacer = new EmulationFramePacer({ maxCatchUpFrames: 4 });
  pacer.reset(0);

  assert.equal(pacer.advance(100), 4);
  assert.equal(pacer.advance(100), 2);
});

test("a background-tab delay is rebased instead of fast-forwarded", () => {
  const pacer = new EmulationFramePacer({ maxElapsedMs: 250 });
  pacer.reset(0);

  assert.equal(pacer.advance(2_000), 0);
  assert.equal(pacer.advance(2_000 + 1000 / 60), 1);
});
