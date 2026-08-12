export class InputRouter {
  constructor(sendKey, sendJoystick) {
    this.sendKey = sendKey;
    this.sendJoystick = sendJoystick;
    this.held = new Map();
    this.sourceKeys = new Map();
    this.joystickMask = 0;
  }

  press(source, cell) {
    this.pressChord(source, [cell]);
  }

  pressChord(source, cells) {
    this.release(source);
    const keys = new Set();
    for (const cell of cells) {
      if (!cell) continue;
      const key = `${cell.row}:${cell.bit}`;
      let sources = this.held.get(key);
      if (!sources) {
        sources = new Set();
        this.held.set(key, sources);
        this.sendKey(cell.row, cell.bit, true);
      }
      sources.add(source);
      keys.add(key);
    }
    if (keys.size > 0) this.sourceKeys.set(source, keys);
  }

  release(source) {
    const keys = this.sourceKeys.get(source);
    if (keys === undefined) return;
    this.sourceKeys.delete(source);
    for (const key of keys) {
      const sources = this.held.get(key);
      if (!sources) continue;
      sources.delete(source);
      if (sources.size === 0) {
        this.held.delete(key);
        const [row, bit] = key.split(":").map(Number);
        this.sendKey(row, bit, false);
      }
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

export class PhysicalKeyboardController {
  constructor(input, resolveChord) {
    this.input = input;
    this.resolveChord = resolveChord;
  }

  keyDown(event) {
    if (event.code === "ShiftLeft" || event.code === "ShiftRight") return true;
    const chord = this.resolveChord(event);
    if (!chord) return false;
    if (event.repeat) return true;
    if (!chord.some((cell) => cell.label === "SHIFT")) {
      this.input.release("physical:ShiftLeft");
      this.input.release("physical:ShiftRight");
    }
    this.input.pressChord(`physical:${event.code}`, chord);
    return true;
  }

  keyUp(event) {
    if (event.code === "ShiftLeft" || event.code === "ShiftRight") return true;
    const source = `physical:${event.code}`;
    if (!this.input.sourceKeys.has(source)) return Boolean(this.resolveChord(event));
    this.input.release(source);
    return true;
  }
}
