const DEFAULT_FRAME_RATE = 60;
const DEFAULT_MAX_CATCH_UP_FRAMES = 4;
const DEFAULT_MAX_ELAPSED_MS = 250;

export class EmulationFramePacer {
  constructor(options = {}) {
    this.frameRate = options.frameRate ?? DEFAULT_FRAME_RATE;
    this.maxCatchUpFrames = options.maxCatchUpFrames ?? DEFAULT_MAX_CATCH_UP_FRAMES;
    this.maxElapsedMs = options.maxElapsedMs ?? DEFAULT_MAX_ELAPSED_MS;
    if (!(this.frameRate > 0)) throw new RangeError("frameRate must be positive");
    if (!Number.isInteger(this.maxCatchUpFrames) || this.maxCatchUpFrames <= 0) {
      throw new RangeError("maxCatchUpFrames must be a positive integer");
    }
    if (!(this.maxElapsedMs > 0)) throw new RangeError("maxElapsedMs must be positive");
    this.frameDurationMs = 1000 / this.frameRate;
    this.lastTimestamp = null;
    this.accumulatorMs = 0;
  }

  reset(timestamp = null) {
    this.lastTimestamp = Number.isFinite(timestamp) ? Number(timestamp) : null;
    this.accumulatorMs = 0;
  }

  advance(timestamp) {
    const now = Number(timestamp);
    if (!Number.isFinite(now)) throw new TypeError("timestamp must be finite");
    if (this.lastTimestamp === null) {
      this.lastTimestamp = now;
      return 0;
    }

    const elapsed = now - this.lastTimestamp;
    this.lastTimestamp = now;
    if (elapsed < 0 || elapsed > this.maxElapsedMs) {
      this.accumulatorMs = 0;
      return 0;
    }

    this.accumulatorMs += elapsed;
    const epsilon = this.frameDurationMs * 1e-9;
    const elapsedFrames = Math.floor(
      (this.accumulatorMs + epsilon) / this.frameDurationMs,
    );
    if (elapsedFrames <= 0) return 0;

    const dispatchedFrames = Math.min(elapsedFrames, this.maxCatchUpFrames);
    this.accumulatorMs -= dispatchedFrames * this.frameDurationMs;
    return dispatchedFrames;
  }
}
