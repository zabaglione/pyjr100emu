import test from "node:test";
import assert from "node:assert/strict";
import { BrowserAudio, pcm16leToFloat32 } from "../audio.js";

test("signed little-endian PCM is normalized for Web Audio", () => {
  const bytes = Uint8Array.from([0x00, 0x80, 0x00, 0x00, 0xff, 0x7f]);
  const samples = pcm16leToFloat32(bytes);

  assert.deepEqual([...samples], [-1, 0, 32767 / 32768]);
});

test("browser audio schedules contiguous buffers and drops excess latency", async () => {
  const starts = [];
  const context = {
    state: "running",
    currentTime: 1,
    destination: {},
    createBuffer: (_channels, length) => ({ length, copyToChannel(samples) { this.samples = samples; } }),
    createBufferSource: () => ({ connect() {}, start(time) { starts.push(time); } }),
  };
  const audio = new BrowserAudio({ contextFactory: () => context, lookAhead: 0.02 });
  await audio.unlock();

  audio.enqueue(Uint8Array.from([1, 0, 2, 0]));
  audio.enqueue(Uint8Array.from([3, 0, 4, 0]));

  assert.equal(starts[0], 1.02);
  assert.equal(starts[1], 1.02 + 2 / 44100);
});
