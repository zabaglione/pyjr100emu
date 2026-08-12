export function pcm16leToFloat32(buffer) {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer || 0);
  const samples = new Float32Array(Math.floor(bytes.byteLength / 2));
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  for (let index = 0; index < samples.length; index += 1) {
    samples[index] = view.getInt16(index * 2, true) / 32768;
  }
  return samples;
}

export class BrowserAudio {
  constructor(options = {}) {
    this.sampleRate = options.sampleRate ?? 44100;
    this.lookAhead = options.lookAhead ?? 0.025;
    this.maximumLatency = options.maximumLatency ?? 0.18;
    this.contextFactory = options.contextFactory ?? (() => {
      const Context = globalThis.AudioContext || globalThis.webkitAudioContext;
      return Context ? new Context({ sampleRate: this.sampleRate }) : null;
    });
    this.context = null;
    this.nextStart = 0;
    this.muted = false;
  }

  async unlock() {
    if (!this.context) this.context = this.contextFactory();
    if (!this.context) return false;
    if (this.context.state === "suspended") await this.context.resume();
    this.nextStart = Math.max(this.nextStart, this.context.currentTime + this.lookAhead);
    return this.context.state === "running";
  }

  setMuted(muted) {
    this.muted = Boolean(muted);
    if (this.muted && this.context) this.nextStart = this.context.currentTime + this.lookAhead;
  }

  enqueue(buffer) {
    if (this.muted || !this.context || this.context.state !== "running") return false;
    const samples = pcm16leToFloat32(buffer);
    if (samples.length === 0) return false;
    const now = this.context.currentTime;
    if (this.nextStart < now || this.nextStart > now + this.maximumLatency) {
      this.nextStart = now + this.lookAhead;
    }
    const audioBuffer = this.context.createBuffer(1, samples.length, this.sampleRate);
    audioBuffer.copyToChannel(samples, 0);
    const source = this.context.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.context.destination);
    source.start(this.nextStart);
    this.nextStart += samples.length / this.sampleRate;
    return true;
  }
}
