import test from "node:test";
import assert from "node:assert/strict";
import {
  KEY_CELLS,
  KEY_MATRIX,
  PHYSICAL_LAYOUT,
  CTRL_LEGENDS,
  legendFontCode,
  resolveKeyboardChord,
} from "../keymap.js";

test("the browser keymap exposes all 45 unique matrix cells", () => {
  assert.equal(KEY_MATRIX.length, 9);
  assert.equal(KEY_CELLS.length, 45);
  assert.equal(new Set(KEY_CELLS.map((cell) => cell.id)).size, 45);
  assert.deepEqual(
    KEY_MATRIX[0].map((cell) => [cell.row, cell.bit, cell.label]),
    [[0, 0, "CTRL"], [0, 1, "SHIFT"], [0, 2, "Z"], [0, 3, "X"], [0, 4, "C"]],
  );
});

test("every non-modifier shortcut key exposes its JR-100 CTRL legend", () => {
  const shortcutKeys = PHYSICAL_LAYOUT.flat().filter(
    (cell) => !cell.modifier && !["SPACE", "RETURN"].includes(cell.label),
  );

  assert.equal(shortcutKeys.length, 41);
  assert.ok(shortcutKeys.every((cell) => CTRL_LEGENDS[cell.label]));
});

test("virtual keys follow the four physical JR-100 rows", () => {
  assert.equal(PHYSICAL_LAYOUT.length, 4);
  assert.deepEqual(PHYSICAL_LAYOUT[0].map((cell) => cell.label), ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-"]);
  assert.deepEqual(PHYSICAL_LAYOUT[2].map((cell) => cell.label), ["CTRL", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", ":"]);
});

test("host characters synthesize JR shift only when the ROM key table requires it", () => {
  assert.deepEqual(resolveKeyboardChord({ code: "KeyA", key: "A" }).map((cell) => cell.label), ["A"]);
  assert.deepEqual(resolveKeyboardChord({ code: "Digit1", key: "!" }).map((cell) => cell.label), ["SHIFT", "1"]);
  assert.deepEqual(resolveKeyboardChord({ code: "Semicolon", key: ":" }).map((cell) => cell.label), [":"]);
});

test("modern editing keys map to the complete JR-100 CTRL shortcuts", () => {
  assert.deepEqual(resolveKeyboardChord({ code: "ArrowLeft", key: "ArrowLeft" }).map((cell) => cell.label), ["CTRL", "6"]);
  assert.deepEqual(resolveKeyboardChord({ code: "Backspace", key: "Backspace" }).map((cell) => cell.label), ["CTRL", "-"]);
  assert.deepEqual(resolveKeyboardChord({ code: "Delete", key: "Delete" }).map((cell) => cell.label), ["CTRL", "5"]);
  assert.deepEqual(resolveKeyboardChord({ code: "CapsLock", key: "CapsLock" }).map((cell) => cell.label), ["SHIFT"]);
});

test("ROM keyboard codes select alpha and shifted graphic glyphs", () => {
  assert.equal(legendFontCode(0x41, 0x00, false, false), 0x21);
  assert.equal(legendFontCode(0x41, 0x00, true, false), 0x21);
  assert.equal(legendFontCode(0x31, 0x21, false, false), 0x11);
  assert.equal(legendFontCode(0x31, 0x21, true, false), 0x01);
  assert.equal(legendFontCode(0x31, 0x21, false, true), 0x51);
  assert.equal(legendFontCode(0x31, 0x21, true, true), 0x41);
});
