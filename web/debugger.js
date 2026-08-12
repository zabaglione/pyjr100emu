export function hex(value, width = 2) {
  return Number(value || 0).toString(16).toUpperCase().padStart(width, "0");
}

export function parseBreakpoints(value) {
  if (!value.trim()) return [];
  return value.split(/[\s,]+/u).filter(Boolean).map((token) => {
    const clean = token.replace(/^\$/u, "").replace(/^0x/iu, "");
    if (!/^[0-9a-f]{1,4}$/iu.test(clean)) throw new Error(`Invalid breakpoint: ${token}`);
    return Number.parseInt(clean, 16);
  });
}

export function formatMemory(start, bytes) {
  const lines = [];
  for (let offset = 0; offset < bytes.length; offset += 16) {
    const row = [...bytes.slice(offset, offset + 16)].map((value) => hex(value)).join(" ");
    lines.push(`${hex((start + offset) & 0xffff, 4)}  ${row}`);
  }
  return lines.join("\n");
}

export class DebuggerPanel {
  constructor({ root, toggleButton, worker, isAvailable, onPause, onError }) {
    this.root = root;
    this.toggleButton = toggleButton;
    this.worker = worker;
    this.isAvailable = isAvailable;
    this.onPause = onPause;
    this.onError = onError;
    this.pending = false;
    this.lastState = null;
    this.cpu = root.querySelector("#debug-cpu");
    this.via = root.querySelector("#debug-via");
    this.memory = root.querySelector("#debug-memory");
    this.memoryStart = root.querySelector("#memory-start");
    this.breakpoints = root.querySelector("#breakpoints");
    this._installHandlers();
  }

  get visible() {
    return !this.root.hidden;
  }

  toggle() {
    this.root.hidden = !this.root.hidden;
    this.toggleButton.textContent = this.root.hidden ? "Debugger" : "Hide debugger";
    if (this.visible) this.request();
    return this.visible;
  }

  request() {
    if (!this.isAvailable() || !this.visible || this.pending) return;
    this.pending = true;
    this.worker.postMessage({
      type: "debugSnapshot",
      start: this.memoryAddress(),
      length: 128,
    });
  }

  frameTick(frameNumber) {
    if (this.visible && frameNumber % 6 === 0) this.request();
  }

  receive(message) {
    this.pending = false;
    const state = message.state;
    this.lastState = state;
    const cpu = state.cpu;
    const via = state.via;
    this.cpu.textContent = `A ${hex(cpu.a)}  B ${hex(cpu.b)}  IX ${hex(cpu.ix, 4)}\nSP ${hex(cpu.sp, 4)}  PC ${hex(cpu.pc, 4)}  ${cpu.flags}\nCLOCK ${state.clockCount}`;
    this.via.textContent = `ORA ${hex(via.ora)} ORB ${hex(via.orb)} DDRA ${hex(via.ddra)} DDRB ${hex(via.ddrb)}\nACR ${hex(via.acr)} PCR ${hex(via.pcr)} IFR ${hex(via.ifr)} IER ${hex(via.ier)}\nT1 ${hex(via.t1, 4)} T2 ${hex(via.t2, 4)}`;
    this.memory.textContent = formatMemory(message.start, new Uint8Array(message.memory));
  }

  clearPending() {
    this.pending = false;
  }

  memoryAddress() {
    const value = this.memoryStart.value.trim().replace(/^\$/u, "").replace(/^0x/iu, "");
    const address = Number.parseInt(value || "0", 16);
    return Number.isFinite(address) ? address & 0xffff : 0;
  }

  _setMemoryAddress(address) {
    this.memoryStart.value = hex(address & 0xffff, 4);
    this.pending = false;
    this.request();
  }

  _installHandlers() {
    this.toggleButton.addEventListener("click", () => this.toggle());
    this.root.querySelector("#debug-step").addEventListener("click", () => {
      if (!this.isAvailable()) return;
      this.onPause();
      this.worker.postMessage({
        type: "step",
        start: this.memoryAddress(),
        length: 128,
      });
    });
    this.root.querySelector("#debug-refresh").addEventListener("click", () => this.request());
    this.memoryStart.addEventListener("change", () => this.request());
    this.root.querySelector("#apply-breakpoints").addEventListener("click", () => {
      try {
        this.worker.postMessage({
          type: "setBreakpoints",
          addresses: parseBreakpoints(this.breakpoints.value),
        });
        this.onError(null);
      } catch (error) {
        this.onError(error);
      }
    });
    this.root.querySelector("#debug-stack").addEventListener("click", () => {
      if (this.lastState) this._setMemoryAddress(this.lastState.cpu.sp - 32);
    });
    this.root.querySelector("#debug-vram").addEventListener("click", () => {
      this._setMemoryAddress(0xc100);
    });
  }
}
