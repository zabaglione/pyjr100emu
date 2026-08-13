import { PcmQueue } from "./pcm-queue.js";

const DEFAULT_SAMPLE_RATE = 44100;
// 512 samples is 11.6 ms at 44.1 kHz; retain at most two such quanta.
const DEFAULT_MAX_BUFFERED_SAMPLES = 1024;
const DEFAULT_START_THRESHOLD_SAMPLES = 512;
const DEFAULT_FALLBACK_CHUNK_SAMPLES = 512;

export function pcm16leToFloat32(buffer) {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer || 0);
  const samples = new Float32Array(Math.floor(bytes.byteLength / 2));
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  for (let index = 0; index < samples.length; index += 1) {
    samples[index] = view.getInt16(index * 2, true) / 32768;
  }
  return samples;
}

export function resampleFloat32(samples, sourceRate, targetRate) {
  if (samples.length === 0 || sourceRate === targetRate) return samples;
  if (!(sourceRate > 0) || !(targetRate > 0)) {
    throw new RangeError("sample rates must be positive");
  }
  const outputLength = Math.max(1, Math.round(samples.length * targetRate / sourceRate));
  const output = new Float32Array(outputLength);
  const scale = outputLength <= 1
    ? 0
    : (samples.length - 1) / (outputLength - 1);
  for (let index = 0; index < outputLength; index += 1) {
    const position = index * scale;
    const left = Math.min(samples.length - 1, Math.floor(position));
    const right = Math.min(samples.length - 1, left + 1);
    const fraction = position - left;
    output[index] = samples[left] + (samples[right] - samples[left]) * fraction;
  }
  return output;
}

export class BrowserAudio {
  constructor(options = {}) {
    this.sampleRate = options.sampleRate ?? DEFAULT_SAMPLE_RATE;
    this.lookAhead = options.lookAhead ?? 0.012;
    this.maximumLatency = options.maximumLatency ?? 0.10;
    this.maxBufferedSamples = options.maxBufferedSamples ?? DEFAULT_MAX_BUFFERED_SAMPLES;
    this.startThresholdSamples = options.startThresholdSamples ?? DEFAULT_START_THRESHOLD_SAMPLES;
    this.maxPendingSamples = options.maxPendingSamples ?? this.maxBufferedSamples;
    this.fallbackChunkSamples = options.fallbackChunkSamples ?? DEFAULT_FALLBACK_CHUNK_SAMPLES;
    this.contextFactory = options.contextFactory ?? (() => {
      const Context = globalThis.AudioContext || globalThis.webkitAudioContext;
      return Context
        ? new Context({ sampleRate: this.sampleRate, latencyHint: "interactive" })
        : null;
    });
    this.workletUrl = options.workletUrl ?? new URL("./audio-worklet.js", import.meta.url);
    this.audioWorkletNodeFactory = options.audioWorkletNodeFactory ?? ((context, name, nodeOptions) => {
      const Node = globalThis.AudioWorkletNode;
      return Node ? new Node(context, name, nodeOptions) : null;
    });
    this.audioWorkletLoader = options.audioWorkletLoader ?? ((context, url) => (
      context.audioWorklet.addModule(url)
    ));
    this.context = null;
    this.workletNode = null;
    this.workletStarted = false;
    this.workletAttempted = false;
    this.fallbackReady = false;
    this.nextStart = 0;
    this.muted = false;
    this.backend = "none";
    this.pending = new PcmQueue(this.maxPendingSamples);
    this.fallbackQueue = new PcmQueue(this.maxBufferedSamples);
    this.fallbackSources = new Set();
  }

  async unlock() {
    if (!this.context) this.context = this.contextFactory();
    if (!this.context) return false;
    if (this.context.state === "suspended" && this.context.resume) {
      await this.context.resume();
    }
    await this._ensureOutput();
    if (this.context.state !== "running") return false;
    this.nextStart = Math.max(this.nextStart, this.context.currentTime + this.lookAhead);
    this._flushPending();
    this._pumpFallback();
    return true;
  }

  setMuted(muted) {
    this.muted = Boolean(muted);
    if (this.muted) this.clear();
  }

  clear() {
    this.pending.clear();
    this.fallbackQueue.clear();
    this.workletStarted = false;
    if (this.workletNode) this.workletNode.port.postMessage({ type: "clear" });
    for (const source of this.fallbackSources) {
      try {
        source.stop();
      } catch (_error) {
        // The source may already have ended.
      }
    }
    this.fallbackSources.clear();
    if (this.context) this.nextStart = this.context.currentTime + this.lookAhead;
  }

  enqueue(buffer) {
    if (this.muted) return false;
    const decoded = pcm16leToFloat32(buffer);
    if (decoded.length === 0) return false;
    const samples = this._adaptSampleRate(decoded);
    if (!this.context || this.context.state !== "running" || !this._hasOutput()) {
      this.pending.push(samples);
      return false;
    }
    this._sendSamples(samples);
    return true;
  }

  async _ensureOutput() {
    if (this.workletNode || this.fallbackReady || this.workletAttempted) return;
    this.workletAttempted = true;
    const canLoadWorklet = Boolean(this.context.audioWorklet?.addModule);
    if (canLoadWorklet) {
      try {
        await this.audioWorkletLoader(this.context, this.workletUrl);
        const node = this.audioWorkletNodeFactory(this.context, "jr100-pcm", {
          numberOfInputs: 0,
          numberOfOutputs: 1,
          outputChannelCount: [1],
          processorOptions: {
            maxBufferedSamples: this.maxBufferedSamples,
            startThresholdSamples: this.startThresholdSamples,
          },
        });
        if (node) {
          node.port.onmessage = (event) => {
            if (event.data?.type === "started") this.workletStarted = true;
          };
          node.connect(this.context.destination);
          this.workletNode = node;
          this.backend = "worklet";
          return;
        }
      } catch (_error) {
        this.workletNode = null;
      }
    }
    this.fallbackReady = Boolean(
      this.context.createBuffer && this.context.createBufferSource,
    );
    if (this.fallbackReady) this.backend = "buffer-source";
  }

  _hasOutput() {
    return Boolean(this.workletNode || this.fallbackReady);
  }

  _adaptSampleRate(samples) {
    const targetRate = this.context?.sampleRate ?? this.sampleRate;
    return resampleFloat32(samples, this.sampleRate, targetRate);
  }

  _flushPending() {
    if (!this._hasOutput() || this.pending.length === 0) return;
    const samples = this.pending.drain();
    this._sendSamples(samples);
  }

  _sendSamples(samples) {
    if (this.workletNode) {
      const copy = samples.slice();
      this.workletNode.port.postMessage(
        { type: "samples", samples: copy },
        [copy.buffer],
      );
      return;
    }
    this.fallbackQueue.push(samples);
    this._pumpFallback();
  }

  _pumpFallback() {
    if (!this.fallbackReady || !this.context || this.muted) return;
    while (this.fallbackQueue.length >= this.fallbackChunkSamples) {
      const samples = new Float32Array(this.fallbackChunkSamples);
      this.fallbackQueue.read(samples);
      this._scheduleFallback(samples);
    }
  }

  _scheduleFallback(samples) {
    const now = this.context.currentTime;
    if (this.nextStart < now || this.nextStart > now + this.maximumLatency) {
      this.nextStart = now + this.lookAhead;
    }
    const sampleRate = this.context.sampleRate ?? this.sampleRate;
    const audioBuffer = this.context.createBuffer(1, samples.length, sampleRate);
    audioBuffer.copyToChannel(samples, 0);
    const source = this.context.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.context.destination);
    source.start(this.nextStart);
    this.fallbackSources.add(source);
    source.onended = () => this.fallbackSources.delete(source);
    this.nextStart += samples.length / sampleRate;
  }
}
