import { PcmQueue } from "./pcm-queue.js";

export class PcmPlaybackBuffer {
  constructor(options = {}) {
    const maxBufferedSamples = options.maxBufferedSamples;
    const startThresholdSamples = options.startThresholdSamples;
    if (!Number.isInteger(maxBufferedSamples) || maxBufferedSamples <= 0) {
      throw new RangeError("maxBufferedSamples must be a positive integer");
    }
    if (
      !Number.isInteger(startThresholdSamples)
      || startThresholdSamples <= 0
      || startThresholdSamples > maxBufferedSamples
    ) {
      throw new RangeError("startThresholdSamples must fit in the playback buffer");
    }
    this.queue = new PcmQueue(maxBufferedSamples);
    this.startThresholdSamples = startThresholdSamples;
    this.started = false;
    this.droppedSamples = 0;
    this.underflowSamples = 0;
    this.rebufferCount = 0;
  }

  get metrics() {
    return {
      bufferedSamples: this.queue.length,
      droppedSamples: this.droppedSamples,
      underflowSamples: this.underflowSamples,
      rebufferCount: this.rebufferCount,
    };
  }

  push(samples) {
    this.droppedSamples += this.queue.push(samples);
    return this.metrics;
  }

  read(output) {
    if (!(output instanceof Float32Array)) {
      throw new TypeError("output must be a Float32Array");
    }
    output.fill(0);
    let startedNow = false;
    let rebuffered = false;
    if (!this.started) {
      if (this.queue.length < this.startThresholdSamples) {
        return this._readResult(0, startedNow, rebuffered);
      }
      this.started = true;
      startedNow = true;
    }

    const writtenSamples = this.queue.read(output);
    if (writtenSamples < output.length) {
      this.underflowSamples += output.length - writtenSamples;
      this.rebufferCount += 1;
      this.started = false;
      rebuffered = true;
    }
    return this._readResult(writtenSamples, startedNow, rebuffered);
  }

  clear() {
    this.queue.clear();
    this.started = false;
    this.droppedSamples = 0;
    this.underflowSamples = 0;
    this.rebufferCount = 0;
  }

  _readResult(writtenSamples, startedNow, rebuffered) {
    return {
      writtenSamples,
      started: this.started,
      startedNow,
      rebuffered,
      ...this.metrics,
    };
  }
}
