export class InputRouter {
  constructor(sendKey, sendJoystick) {
    this.sendKey = sendKey;
    this.sendJoystick = sendJoystick;
    this.held = new Map();
    this.sourceKeys = new Map();
    this.joystickMask = 0;
  }

  press(source, cell) {
    const key = `${cell.row}:${cell.bit}`;
    this.release(source);
    let sources = this.held.get(key);
    if (!sources) {
      sources = new Set();
      this.held.set(key, sources);
      this.sendKey(cell.row, cell.bit, true);
    }
    sources.add(source);
    this.sourceKeys.set(source, key);
  }

  release(source) {
    const key = this.sourceKeys.get(source);
    if (key === undefined) return;
    this.sourceKeys.delete(source);
    const sources = this.held.get(key);
    if (!sources) return;
    sources.delete(source);
    if (sources.size === 0) {
      this.held.delete(key);
      const [row, bit] = key.split(":").map(Number);
      this.sendKey(row, bit, false);
    }
  }

  toggleLatch(source, cell) {
    if (this.sourceKeys.has(source)) {
      this.release(source);
    } else {
      this.press(source, cell);
    }
  }

  releaseMomentary() {
    for (const source of [...this.sourceKeys.keys()]) {
      if (!source.startsWith("latch:")) this.release(source);
    }
  }

  releasePrefix(prefix) {
    for (const source of [...this.sourceKeys.keys()]) {
      if (source.startsWith(prefix)) this.release(source);
    }
  }

  clear() {
    for (const source of [...this.sourceKeys.keys()]) this.release(source);
    this.setJoystickMask(0);
  }

  setJoystickMask(mask) {
    const next = mask & 0x1f;
    if (next === this.joystickMask) return;
    this.joystickMask = next;
    this.sendJoystick(next);
  }

  isPressed(row, bit) {
    return this.held.has(`${row}:${bit}`);
  }
}
