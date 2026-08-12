import { KEY_CELLS, KEY_MATRIX, getKeyCell, keyId } from "./keymap.js";

export class VirtualKeyboard {
  constructor(container, input) {
    this.container = container;
    this.input = input;
    this.buttons = new Map();
    this.cursor = { row: 0, bit: 0 };
    this.active = false;
    this._heldGamepadSource = null;
    this._build();
  }

  _build() {
    this.container.replaceChildren();
    for (const row of KEY_MATRIX) {
      const rowElement = document.createElement("div");
      rowElement.className = "keyboard-row";
      for (const cell of row) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "virtual-key";
        button.dataset.keyId = cell.id;
        button.textContent = cell.label;
        button.setAttribute("aria-label", cell.label);
        this.buttons.set(cell.id, button);
        this._installPointerHandlers(button, cell);
        rowElement.append(button);
      }
      this.container.append(rowElement);
    }
    this._refreshCursor();
  }

  _installPointerHandlers(button, cell) {
    const source = `virtual:${cell.id}`;
    button.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      button.setPointerCapture?.(event.pointerId);
      if (cell.modifier) {
        this.input.toggleLatch(`latch:${source}`, cell);
      } else {
        this.input.press(source, cell);
      }
      this._refreshHeld();
    });
    const release = (event) => {
      event.preventDefault();
      if (!cell.modifier) this.input.release(source);
      this._refreshHeld();
    };
    button.addEventListener("pointerup", release);
    button.addEventListener("pointercancel", release);
    button.addEventListener("lostpointercapture", release);
  }

  setActive(active) {
    this.active = Boolean(active);
    this.container.hidden = !this.active;
    if (!this.active) {
      this.input.releasePrefix("virtual:");
      this.input.releasePrefix("latch:virtual:");
      this.input.releasePrefix("gamepad-vkbd:");
      this.input.releasePrefix("gamepad-special:");
      this.releaseGamepadKey();
      this._refreshCursor();
      this._refreshHeld();
    }
  }

  toggle() {
    this.setActive(!this.active);
    return this.active;
  }

  move(rowDelta, bitDelta) {
    if (!this.active) return;
    this.cursor.row = Math.max(0, Math.min(KEY_MATRIX.length - 1, this.cursor.row + rowDelta));
    this.cursor.bit = Math.max(0, Math.min(KEY_MATRIX[this.cursor.row].length - 1, this.cursor.bit + bitDelta));
    this._refreshCursor();
  }

  holdGamepadKey(cell) {
    if (!this.active) return;
    const source = `gamepad-vkbd:${cell.id}`;
    if (this._heldGamepadSource === source) return;
    this.releaseGamepadKey();
    this.input.press(source, cell);
    this._heldGamepadSource = source;
    this._refreshHeld();
  }

  releaseGamepadKey() {
    if (this._heldGamepadSource !== null) {
      this.input.release(this._heldGamepadSource);
      this._heldGamepadSource = null;
      this._refreshHeld();
    }
  }

  holdGamepadSpecial(label, pressed) {
    const cell = KEY_CELLS.find((candidate) => candidate.label === label);
    if (!cell) return;
    const source = `gamepad-special:${label}`;
    if (pressed) this.input.press(source, cell);
    else this.input.release(source);
    this._refreshHeld();
  }

  currentCell() {
    return getKeyCell(keyId(this.cursor.row, this.cursor.bit));
  }

  _refreshCursor() {
    for (const button of this.buttons.values()) button.classList.remove("cursor");
    const current = this.buttons.get(keyId(this.cursor.row, this.cursor.bit));
    current?.classList.add("cursor");
  }

  _refreshHeld() {
    for (const [id, button] of this.buttons.entries()) {
      const cell = getKeyCell(id);
      button.classList.toggle("held", Boolean(cell && this.input.isPressed(cell.row, cell.bit)));
    }
  }
}
