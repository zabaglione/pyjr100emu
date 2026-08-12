import test from "node:test";
import assert from "node:assert/strict";
import { KEY_CELLS, KEY_MATRIX, findKeyCell } from "../keymap.js";

test("the browser keymap exposes all 45 unique matrix cells", () => {
  assert.equal(KEY_MATRIX.length, 9);
  assert.equal(KEY_CELLS.length, 45);
  assert.equal(new Set(KEY_CELLS.map((cell) => cell.id)).size, 45);
  assert.deepEqual(
    KEY_MATRIX[0].map((cell) => [cell.row, cell.bit, cell.label]),
    [[0, 0, "CTL"], [0, 1, "SHIFT"], [0, 2, "Z"], [0, 3, "X"], [0, 4, "C"]],
  );
});

test("physical code mapping uses the JR-100 matrix coordinates", () => {
  assert.deepEqual(findKeyCell({ code: "KeyA", key: "a" }), { ...KEY_MATRIX[1][0] });
  assert.deepEqual(findKeyCell({ code: "Enter", key: "Enter" }), { ...KEY_MATRIX[8][3] });
  assert.deepEqual(findKeyCell({ code: "Semicolon", key: ":" }), { ...KEY_MATRIX[6][4] });
});
