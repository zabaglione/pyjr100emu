import test from "node:test";
import assert from "node:assert/strict";
import { PcmQueue } from "../pcm-queue.js";

test("PCM queue preserves order while reading small render quanta", () => {
  const queue = new PcmQueue(8);
  queue.push(Float32Array.from([1, 2, 3]));
  queue.push(Float32Array.from([4, 5]));

  const first = new Float32Array(2);
  assert.equal(queue.read(first), 2);
  assert.deepEqual([...first], [1, 2]);

  const second = new Float32Array(3);
  assert.equal(queue.read(second), 3);
  assert.deepEqual([...second], [3, 4, 5]);
  assert.equal(queue.length, 0);
});

test("PCM queue drops oldest samples when its latency cap is reached", () => {
  const queue = new PcmQueue(4);
  assert.equal(queue.push(Float32Array.from([1, 2, 3])), 0);
  assert.equal(queue.push(Float32Array.from([4, 5, 6])), 2);

  const output = new Float32Array(4);
  assert.equal(queue.read(output), 4);
  assert.deepEqual([...output], [3, 4, 5, 6]);
});
