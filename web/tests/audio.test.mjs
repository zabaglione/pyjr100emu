import test from "node:test";
import assert from "node:assert/strict";
import {
  BrowserAudio,
  StreamingLinearResampler,
  pcm16leToFloat32,
  resampleFloat32,
} from "../audio.js";

function createWorkletHarness() {
  const nodes = [];
  const context = {
    state: "running",
    currentTime: 1,
    sampleRate: 44100,
    destination: {},
    audioWorklet: { addModule: async () => {} },
  };
  const audioWorkletNodeFactory = (_context, name, options) => {
    const node = {
      name,
      options,
      connected: false,
      port: {
        messages: [],
        postMessage(message) {
          this.messages.push(message);
        },
      },
      connect() {
        this.connected = true;
      },
    };
    nodes.push(node);
    return node;
  };
  return { context, nodes, audioWorkletNodeFactory };
}

test("signed little-endian PCM is normalized for Web Audio", () => {
  const bytes = Uint8Array.from([0x00, 0x80, 0x00, 0x00, 0xff, 0x7f]);
  const samples = pcm16leToFloat32(bytes);

  assert.deepEqual([...samples], [-1, 0, 32767 / 32768]);
});

test("PCM resampling preserves endpoints for a different AudioContext rate", () => {
  const output = resampleFloat32(Float32Array.from([-1, 0, 1]), 3, 6);

  assert.equal(output.length, 6);
  assert.equal(output[0], -1);
  assert.equal(output[output.length - 1], 1);
  assert.deepEqual(
    [...output].map((value) => Math.round(value * 1_000_000) / 1_000_000),
    [-1, -0.6, -0.2, 0.2, 0.6, 1],
  );
});

test("streaming resampling is continuous across incoming PCM chunks", () => {
  const resampler = new StreamingLinearResampler(3, 6);

  const first = resampler.process(Float32Array.from([0, 1]));
  const second = resampler.process(Float32Array.from([2, 3]));

  assert.deepEqual([...first], [0, 0.5]);
  assert.deepEqual([...second], [1, 1.5, 2, 2.5]);
});

test("browser audio sends PCM to one small audio worklet queue", async () => {
  const harness = createWorkletHarness();
  const audio = new BrowserAudio({
    contextFactory: () => harness.context,
    audioWorkletNodeFactory: harness.audioWorkletNodeFactory,
    audioWorkletLoader: async () => {},
    maxBufferedSamples: 256,
    startThresholdSamples: 128,
  });

  assert.equal(audio.enqueue(Uint8Array.from([0, 0])), false);
  await audio.unlock();

  assert.equal(harness.nodes.length, 1);
  const node = harness.nodes[0];
  assert.equal(node.name, "jr100-pcm");
  assert.equal(node.connected, true);
  assert.equal(node.options.processorOptions.maxBufferedSamples, 256);
  assert.equal(node.options.processorOptions.startThresholdSamples, 128);
  assert.deepEqual([...node.port.messages[0].samples], [0]);

  audio.enqueue(Uint8Array.from([0, 0, 0, 128]));
  assert.equal(node.port.messages.length, 2);
  assert.deepEqual([...node.port.messages[1].samples], [0, -1]);
});

test("browser audio clears queued samples when muted or reset", async () => {
  const harness = createWorkletHarness();
  const audio = new BrowserAudio({
    contextFactory: () => harness.context,
    audioWorkletNodeFactory: harness.audioWorkletNodeFactory,
    audioWorkletLoader: async () => {},
  });
  await audio.unlock();

  audio.enqueue(Uint8Array.from([1, 0]));
  audio.setMuted(true);
  audio.setMuted(false);
  audio.clear();

  const messages = harness.nodes[0].port.messages;
  assert.deepEqual(messages.map((message) => message.type), ["samples", "clear", "clear"]);
  assert.equal(audio.muted, false);
});

test("browser audio exposes worklet buffer and continuity metrics", async () => {
  const harness = createWorkletHarness();
  const audio = new BrowserAudio({
    contextFactory: () => harness.context,
    audioWorkletNodeFactory: harness.audioWorkletNodeFactory,
    audioWorkletLoader: async () => {},
  });
  await audio.unlock();

  harness.nodes[0].port.onmessage({
    data: {
      type: "metrics",
      bufferedSamples: 1400,
      droppedSamples: 0,
      underflowSamples: 0,
      rebufferCount: 0,
    },
  });

  assert.deepEqual(audio.metrics, {
    bufferedSamples: 1400,
    droppedSamples: 0,
    underflowSamples: 0,
    rebufferCount: 0,
  });
});

test("worklet metrics retain samples dropped before audio unlock", async () => {
  const harness = createWorkletHarness();
  const audio = new BrowserAudio({
    contextFactory: () => harness.context,
    audioWorkletNodeFactory: harness.audioWorkletNodeFactory,
    audioWorkletLoader: async () => {},
    maxPendingSamples: 2,
  });

  audio.enqueue(Uint8Array.from([1, 0, 2, 0, 3, 0]));
  await audio.unlock();
  harness.nodes[0].port.onmessage({
    data: {
      type: "metrics",
      bufferedSamples: 2,
      droppedSamples: 0,
      underflowSamples: 0,
      rebufferCount: 0,
    },
  });

  assert.equal(audio.metrics.droppedSamples, 1);
});

test("fallback audio schedules buffered chunks contiguously", async () => {
  const starts = [];
  const context = {
    state: "running",
    currentTime: 1,
    sampleRate: 44100,
    destination: {},
    createBuffer: (_channels, length) => ({ length, copyToChannel(samples) { this.samples = samples; } }),
    createBufferSource: () => ({ connect() {}, start(time) { starts.push(time); } }),
  };
  const audio = new BrowserAudio({
    contextFactory: () => context,
    lookAhead: 0.02,
    fallbackChunkSamples: 2,
  });
  await audio.unlock();

  audio.enqueue(Uint8Array.from([1, 0, 2, 0]));
  audio.enqueue(Uint8Array.from([3, 0, 4, 0]));

  assert.equal(starts[0], 1.02);
  assert.equal(starts[1], 1.02 + 2 / 44100);
});
