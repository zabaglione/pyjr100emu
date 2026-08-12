const MATRIX_ROW_LABELS = [
  ["CTRL", "SHIFT", "Z", "X", "C"],
  ["A", "S", "D", "F", "G"],
  ["Q", "W", "E", "R", "T"],
  ["1", "2", "3", "4", "5"],
  ["6", "7", "8", "9", "0"],
  ["Y", "U", "I", "O", "P"],
  ["H", "J", "K", "L", ";"],
  ["V", "B", "N", "M", ","],
  [".", "SPACE", ":", "RETURN", "-"],
];

const KEY_BY_ID = new Map();
const KEY_BY_LABEL = new Map();

export const KEY_MATRIX = MATRIX_ROW_LABELS.map((labels, row) =>
  labels.map((label, bit) => {
    const cell = Object.freeze({
      id: `r${row}b${bit}`,
      label,
      row,
      bit,
      modifier: label === "CTRL" || label === "SHIFT",
    });
    KEY_BY_ID.set(cell.id, cell);
    KEY_BY_LABEL.set(label, cell);
    return cell;
  }),
);

export const KEY_CELLS = Object.freeze(KEY_MATRIX.flat());

function cells(...labels) {
  return Object.freeze(labels.map((label) => KEY_BY_LABEL.get(label)));
}

export const PHYSICAL_LAYOUT = Object.freeze([
  cells("1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-"),
  cells("Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "RETURN"),
  cells("CTRL", "A", "S", "D", "F", "G", "H", "J", "K", "L", ";", ":"),
  cells("SHIFT", "Z", "X", "C", "V", "B", "N", "M", ",", ".", "SPACE"),
]);

export const CTRL_LEGENDS = Object.freeze({
  1: "HOME", 2: "VERIFY", 3: "SAVE", 4: "LOAD", 5: "DELETE",
  6: "LEFT", 7: "DOWN", 8: "UP", 9: "RIGHT", 0: "INSERT", "-": "RUBOUT",
  Q: "GOSUB", W: "RET", E: "END", R: "RUN", T: "THEN",
  Y: "LOCATE", U: "IF", I: "INPUT", O: "OPTION", P: "PRINT",
  A: "AUTO", S: "STOP", D: "DIM", F: "FOR", G: "GOTO",
  H: "POKE", J: "RND(", K: "READ", L: "LIST", ";": "CHR$(", ":": "REM",
  Z: "L.INS", X: "CANCEL", C: "BREAK", V: "GRAPH", B: "HCOPY",
  N: "NEXT", M: "CLS", ",": "DATA", ".": "PEEK(",
});

const SHIFT_CHARACTER_BY_KEY = Object.freeze({
  1: "!", 2: '"', 3: "#", 4: "$", 5: "%",
  6: "&", 7: "'", 8: "(", 9: ")", 0: "^",
  U: "@", I: "\\", O: "[", P: "]", K: "?", L: "/", ";": "+",
  M: "_", ",": "<", ".": ">", ":": "*", "-": "=",
});

function normalCharacter(cell) {
  if (cell.label === "SPACE") return " ";
  if (cell.label === "RETURN") return "\r";
  return cell.label;
}

const CHARACTER_CHORDS = new Map();
for (const cell of KEY_CELLS.filter((candidate) => !candidate.modifier)) {
  CHARACTER_CHORDS.set(normalCharacter(cell), Object.freeze([cell]));
  const shifted = SHIFT_CHARACTER_BY_KEY[cell.label];
  if (shifted) {
    CHARACTER_CHORDS.set(
      shifted,
      Object.freeze([KEY_BY_LABEL.get("SHIFT"), cell]),
    );
  }
}

const CONTROL_ALIASES = new Map([
  ["Home", "1"],
  ["Delete", "5"],
  ["ArrowLeft", "6"],
  ["ArrowDown", "7"],
  ["ArrowUp", "8"],
  ["ArrowRight", "9"],
  ["Insert", "0"],
  ["Backspace", "-"],
]);

const DIRECT_ALIASES = new Map([
  ["Enter", "RETURN"],
  ["NumpadEnter", "RETURN"],
  ["CapsLock", "SHIFT"],
]);

export function resolveKeyboardChord(event) {
  if (event.metaKey || event.altKey) return null;
  if (event.code === "ControlLeft" || event.code === "ControlRight") return cells("CTRL");
  if (event.code === "ShiftLeft" || event.code === "ShiftRight") return cells("SHIFT");
  const controlLabel = CONTROL_ALIASES.get(event.code);
  if (controlLabel) return cells("CTRL", controlLabel);
  const directLabel = DIRECT_ALIASES.get(event.code);
  if (directLabel) return cells(directLabel);

  let value = event.key;
  if (typeof value === "string" && value.length === 1) {
    if (value >= "a" && value <= "z") value = value.toUpperCase();
    const chord = CHARACTER_CHORDS.get(value);
    if (chord) return chord;
  }
  const codeLabel = event.code?.startsWith("Key") ? event.code.slice(3) : null;
  if (codeLabel && KEY_BY_LABEL.has(codeLabel)) return cells(codeLabel);
  return null;
}

export function findKeyCell(event) {
  const chord = resolveKeyboardChord(event);
  return chord?.at(-1) || null;
}

export function getKeyCell(id) {
  return KEY_BY_ID.get(id) || null;
}

export function getKeyByLabel(label) {
  return KEY_BY_LABEL.get(label) || null;
}

export function keyId(row, bit) {
  return `r${row}b${bit}`;
}
