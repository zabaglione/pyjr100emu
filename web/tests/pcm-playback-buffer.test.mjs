import test from "node:test";
import assert from "node:assert/strict";
import { PcmPlaybackBuffer } from "../pcm-playback-buffer.js";

function samples(length, value = 0.25) {
  return new Float32Array(length).fill(value);
}

test("playback waits for two JR-100 frames before starting", () => {
  const playback = new PcmPlaybackBuffer({
    maxBufferedSamples: 2940,
    startThresholdSamples: 1470,
  });
  const output = new Float32Array(128);

  playback.push(samples(735));
  assert.equal(playback.read(output).started, false);
  assert.deepEqual([...output], [...new Float32Array(128)]);

  playback.push(samples(735));
  const result = playback.read(output);
  assert.equal(result.started, true);
  assert.equal(result.startedNow, true);
  assert.equal(result.writtenSamples, 128);
});

test("two-frame buffering absorbs a 25 ms producer delay without dropping PCM", () => {
  const playback = new PcmPlaybackBuffer({
    maxBufferedSamples: 2940,
    startThresholdSamples: 1470,
  });
  const output = new Float32Array(128);

  playback.push(samples(1470));
  for (let index = 0; index < 9; index += 1) playback.read(output);
  playback.push(samples(1470));

  assert.equal(playback.metrics.droppedSamples, 0);
  assert.equal(playback.metrics.underflowSamples, 0);
  assert.equal(playback.metrics.rebufferCount, 0);
});

test("an underrun returns to prebuffering instead of repeatedly sputtering", () => {
  const playback = new PcmPlaybackBuffer({
    maxBufferedSamples: 2940,
    startThresholdSamples: 1470,
  });
  const quantum = new Float32Array(128);

  playback.push(samples(1470));
  playback.read(quantum);
  const underrun = playback.read(new Float32Array(2048));
  assert.equal(underrun.started, false);
  assert.equal(underrun.rebuffered, true);
  assert.equal(playback.metrics.rebufferCount, 1);
  assert.equal(playback.metrics.underflowSamples, 706);

  const waiting = playback.read(quantum);
  assert.equal(waiting.started, false);
  assert.equal(waiting.rebuffered, false);
  assert.equal(playback.metrics.rebufferCount, 1);

  playback.push(samples(735));
  assert.equal(playback.read(quantum).started, false);
  playback.push(samples(735));
  assert.equal(playback.read(quantum).startedNow, true);
});
