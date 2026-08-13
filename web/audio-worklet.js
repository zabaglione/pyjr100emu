import { PcmQueue } from "./pcm-queue.js";

class Jr100PcmProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const maxBufferedSamples = options.processorOptions?.maxBufferedSamples ?? 1024;
    const startThresholdSamples = options.processorOptions?.startThresholdSamples ?? 512;
    this.queue = new PcmQueue(maxBufferedSamples);
    this.startThresholdSamples = startThresholdSamples;
    this.started = false;
    this.port.onmessage = (event) => {
      const message = event.data || {};
      if (message.type === "samples") {
        this.queue.push(message.samples);
      } else if (message.type === "clear") {
        this.queue.clear();
        this.started = false;
      }
    };
  }

  process(_inputs, outputs) {
    const output = outputs[0]?.[0];
    if (!output) return true;
    output.fill(0);
    if (!this.started) {
      if (this.queue.length < this.startThresholdSamples) return true;
      this.started = true;
      this.port.postMessage({ type: "started" });
    }
    this.queue.read(output);
    return true;
  }
}

registerProcessor("jr100-pcm", Jr100PcmProcessor);
