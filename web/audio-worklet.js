import { PcmPlaybackBuffer } from "./pcm-playback-buffer.js";

class Jr100PcmProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const maxBufferedSamples = options.processorOptions?.maxBufferedSamples ?? 2940;
    const startThresholdSamples = options.processorOptions?.startThresholdSamples ?? 1470;
    this.playback = new PcmPlaybackBuffer({
      maxBufferedSamples,
      startThresholdSamples,
    });
    this.renderCount = 0;
    this.port.onmessage = (event) => {
      const message = event.data || {};
      if (message.type === "samples") {
        const before = this.playback.metrics.droppedSamples;
        this.playback.push(message.samples);
        if (this.playback.metrics.droppedSamples !== before) this._postMetrics();
      } else if (message.type === "clear") {
        this.playback.clear();
        this._postMetrics();
      }
    };
  }

  process(_inputs, outputs) {
    const output = outputs[0]?.[0];
    if (!output) return true;
    const result = this.playback.read(output);
    if (result.startedNow) {
      this.port.postMessage({ type: "started" });
    }
    this.renderCount += 1;
    if (result.startedNow || result.rebuffered || this.renderCount % 16 === 0) {
      this._postMetrics();
    }
    return true;
  }

  _postMetrics() {
    this.port.postMessage({
      type: "metrics",
      ...this.playback.metrics,
      started: this.playback.started,
    });
  }
}

registerProcessor("jr100-pcm", Jr100PcmProcessor);
