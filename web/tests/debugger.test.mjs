import test from "node:test";
import assert from "node:assert/strict";
import { formatMemory, parseBreakpoints } from "../debugger.js";

test("debugger parses common hexadecimal breakpoint notation", () => {
  assert.deepEqual(parseBreakpoints("$E000, 0xe120 0300"), [0xe000, 0xe120, 0x0300]);
  assert.throws(() => parseBreakpoints("E000, nope"), /Invalid breakpoint/u);
});

test("memory dump rows wrap across the 16-bit address boundary", () => {
  const bytes = Uint8Array.from({ length: 32 }, (_, index) => index);
  const lines = formatMemory(0xfff0, bytes).split("\n");

  assert.ok(lines[0].startsWith("FFF0  00 01"));
  assert.ok(lines[1].startsWith("0000  10 11"));
});
