(function installMatrixInputScheduler(root) {
  const keyId = (row, bit) => `${row}:${bit}`;

  function isModifier(row, bit) {
    return row === 0 && (bit === 0 || bit === 1);
  }

  class MatrixInputScheduler {
    constructor(sendKey, options = {}) {
      this.sendKey = sendKey;
      this.minimumFrames = options.minimumFrames ?? 2;
      this.modifierFrames = options.modifierFrames ?? 4;
      this.modifierLeadFrames = options.modifierLeadFrames ?? 1;
      this.keys = new Map();
    }

    key(row, bit, pressed) {
      const id = keyId(row, bit);
      let state = this.keys.get(id);
      if (!state) {
        state = {
          row,
          bit,
          modifier: isModifier(row, bit),
          desired: false,
          queued: false,
          active: false,
          delay: 0,
          frames: 0,
        };
        this.keys.set(id, state);
      }
      if (pressed) {
        state.desired = true;
        if (!state.active && !state.queued) {
          state.queued = true;
          state.delay = state.modifier || !this._modifierNeedsLead()
            ? 0
            : this.modifierLeadFrames;
        }
      } else {
        state.desired = false;
      }
    }

    beforeFrame() {
      for (const state of this.keys.values()) {
        if (!state.queued || state.active) continue;
        if (state.delay > 0) {
          state.delay -= 1;
          continue;
        }
        state.queued = false;
        state.active = true;
        state.frames = state.modifier ? this.modifierFrames : this.minimumFrames;
        this.sendKey(state.row, state.bit, true);
      }
    }

    afterFrame() {
      for (const [id, state] of this.keys.entries()) {
        if (state.active && state.frames > 0) state.frames -= 1;
        if (state.active && state.frames === 0 && !state.desired) {
          state.active = false;
          this.sendKey(state.row, state.bit, false);
        }
        if (!state.active && !state.queued && !state.desired) this.keys.delete(id);
      }
    }

    clear() {
      for (const state of this.keys.values()) {
        if (state.active) this.sendKey(state.row, state.bit, false);
      }
      this.keys.clear();
    }

    _modifierNeedsLead() {
      return [...this.keys.values()].some(
        (state) => state.modifier && (state.desired || state.queued) && !state.active,
      );
    }
  }

  root.MatrixInputScheduler = MatrixInputScheduler;
}(globalThis));
