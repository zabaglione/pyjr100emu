import {
  CTRL_LEGENDS,
  KEY_CELLS,
  PHYSICAL_LAYOUT,
  getKeyCell,
  legendFontCode,
} from "./keymap.js";

const TYPEABLE_CELLS = KEY_CELLS.filter((cell) => !cell.modifier);

export class VirtualKeyboard {
  constructor(container, input) {
    this.container = container;
    this.input = input;
    this.buttons = new Map();
    this.legendCanvases = new Map();
    this.cursor = { row: 0, column: 0 };
    this.cursorVisible = false;
    this.active = false;
    this.graphicsMode = false;
    this.font = null;
    this.normalCodes = null;
    this.shiftCodes = null;
    this._heldGamepadSource = null;
    this._build();
  }

  _build() {
    this.container.replaceChildren();
    for (const [rowIndex, row] of PHYSICAL_LAYOUT.entries()) {
      const rowElement = document.createElement("div");
      rowElement.className = `keyboard-row keyboard-row-${rowIndex + 1}`;
      for (const cell of row) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `virtual-key key-${cell.label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
        button.dataset.keyId = cell.id;
        button.setAttribute("aria-label", cell.label);

        const ctrlLegend = document.createElement("span");
        ctrlLegend.className = "ctrl-legend";
        ctrlLegend.textContent = CTRL_LEGENDS[cell.label] || "";

        const face = document.createElement("span");
        face.className = "key-face";
        const main = this._createLegendCanvas("main-legend");
        const alternate = this._createLegendCanvas("alternate-legend");
        const text = document.createElement("span");
        text.className = "key-text";
        text.textContent = cell.label;
        face.append(main, text, alternate);
        button.append(ctrlLegend, face);

        this.buttons.set(cell.id, button);
        this.legendCanvases.set(cell.id, { main, alternate, text });
        this._installPointerHandlers(button, cell);
        rowElement.append(button);
      }
      this.container.append(rowElement);
    }
    this._refreshCursor();
    this._updateLegends();
  }

  _createLegendCanvas(className) {
    const canvas = document.createElement("canvas");
    canvas.className = className;
    canvas.width = 8;
    canvas.height = 8;
    canvas.hidden = true;
    canvas.setAttribute("aria-hidden", "true");
    return canvas;
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

  setRomAssets(font, normalCodes, shiftCodes) {
    this.font = new Uint8Array(font || 0);
    this.normalCodes = new Uint8Array(normalCodes || 0);
    this.shiftCodes = new Uint8Array(shiftCodes || 0);
    this._updateLegends();
  }

  setGraphicsMode(active) {
    const next = Boolean(active);
    if (next === this.graphicsMode) return;
    this.graphicsMode = next;
    this.container.classList.toggle("graphics-mode", next);
    this._updateLegends();
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
      this.hideGamepadCursor();
      this._refreshCursor();
      this._refreshHeld();
    }
  }

  toggle() {
    this.setActive(!this.active);
    return this.active;
  }

  move(rowDelta, columnDelta) {
    if (!this.active) return;
    if (rowDelta !== 0 || columnDelta !== 0) this.cursorVisible = true;
    this.cursor.row = Math.max(0, Math.min(PHYSICAL_LAYOUT.length - 1, this.cursor.row + rowDelta));
    this.cursor.column = Math.max(
      0,
      Math.min(PHYSICAL_LAYOUT[this.cursor.row].length - 1, this.cursor.column + columnDelta),
    );
    this._refreshCursor();
  }

  holdGamepadKey(cell) {
    if (!this.active || !cell) return;
    this.cursorVisible = true;
    this._refreshCursor();
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
    return PHYSICAL_LAYOUT[this.cursor.row]?.[this.cursor.column] || null;
  }

  hideGamepadCursor() {
    if (!this.cursorVisible) return;
    this.cursorVisible = false;
    this._refreshCursor();
  }

  _refreshCursor() {
    for (const button of this.buttons.values()) button.classList.remove("cursor");
    if (!this.cursorVisible) return;
    const current = this.currentCell();
    this.buttons.get(current?.id)?.classList.add("cursor");
  }

  _refreshHeld() {
    for (const [id, button] of this.buttons.entries()) {
      const cell = getKeyCell(id);
      button.classList.toggle("held", Boolean(cell && this.input.isPressed(cell.row, cell.bit)));
    }
    this._updateLegends();
  }

  refresh() {
    this._refreshHeld();
  }

  _updateLegends() {
    const shiftPressed = this.input.isPressed(0, 1);
    for (const [index, cell] of TYPEABLE_CELLS.entries()) {
      const legends = this.legendCanvases.get(cell.id);
      if (!legends) continue;
      const normal = this.normalCodes?.[index] || 0;
      const shifted = this.shiftCodes?.[index] || 0;
      const namedKey = cell.label === "SPACE" || cell.label === "RETURN";
      const normalGlyph = legendFontCode(normal, shifted, false, this.graphicsMode);
      const shiftedGlyph = legendFontCode(normal, shifted, true, this.graphicsMode);
      const active = shiftPressed ? shiftedGlyph : normalGlyph;
      const alternate = shiftPressed ? normalGlyph : shiftedGlyph;
      const hasFont = !namedKey && this.font?.length >= 1024 && active !== 0;
      legends.text.hidden = hasFont;
      legends.main.hidden = !hasFont;
      if (hasFont) this._drawGlyph(legends.main, active, "#72e6f4");
      legends.main.dataset.code = active.toString(16).padStart(2, "0");
      legends.alternate.hidden = !hasFont || alternate === 0 || alternate === active;
      if (hasFont && alternate) this._drawGlyph(legends.alternate, alternate, "#b7f5fb");
      legends.alternate.dataset.code = alternate.toString(16).padStart(2, "0");
    }
  }

  _drawGlyph(canvas, code, color) {
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, 8, 8);
    context.fillStyle = color;
    const offset = (code & 0x7f) * 8;
    for (let y = 0; y < 8; y += 1) {
      const row = this.font[offset + y] || 0;
      for (let x = 0; x < 8; x += 1) {
        if (row & (0x80 >> x)) context.fillRect(x, y, 1, 1);
      }
    }
  }
}
