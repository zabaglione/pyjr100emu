export class PcmQueue {
  constructor(maxSamples) {
    if (!Number.isInteger(maxSamples) || maxSamples <= 0) {
      throw new RangeError("maxSamples must be a positive integer");
    }
    this.maxSamples = maxSamples;
    this.chunks = [];
    this.offset = 0;
    this.length = 0;
  }

  push(samples) {
    const input = samples instanceof Float32Array
      ? samples
      : Float32Array.from(samples || []);
    if (input.length === 0) return;

    if (input.length >= this.maxSamples) {
      this.chunks = [input.slice(input.length - this.maxSamples)];
      this.offset = 0;
      this.length = this.maxSamples;
      return;
    }

    this.chunks.push(input);
    this.length += input.length;
    this._dropOldest(this.length - this.maxSamples);
  }

  read(output) {
    if (!(output instanceof Float32Array)) {
      throw new TypeError("output must be a Float32Array");
    }

    let written = 0;
    while (written < output.length && this.chunks.length > 0) {
      const chunk = this.chunks[0];
      const available = chunk.length - this.offset;
      const count = Math.min(output.length - written, available);
      output.set(chunk.subarray(this.offset, this.offset + count), written);
      this.offset += count;
      written += count;
      this.length -= count;
      if (this.offset >= chunk.length) {
        this.chunks.shift();
        this.offset = 0;
      }
    }
    return written;
  }

  drain() {
    const output = new Float32Array(this.length);
    this.read(output);
    return output;
  }

  clear() {
    this.chunks = [];
    this.offset = 0;
    this.length = 0;
  }

  _dropOldest(count) {
    let remaining = Math.max(0, count);
    while (remaining > 0 && this.chunks.length > 0) {
      const chunk = this.chunks[0];
      const available = chunk.length - this.offset;
      const dropped = Math.min(remaining, available);
      this.offset += dropped;
      this.length -= dropped;
      remaining -= dropped;
      if (this.offset >= chunk.length) {
        this.chunks.shift();
        this.offset = 0;
      }
    }
  }
}
