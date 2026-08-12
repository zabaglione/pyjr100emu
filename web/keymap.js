const ROW_LABELS = [
  ["CTL", "SHIFT", "Z", "X", "C"],
  ["A", "S", "D", "F", "G"],
  ["Q", "W", "E", "R", "T"],
  ["1", "2", "3", "4", "5"],
  ["6", "7", "8", "9", "0"],
  ["Y", "U", "I", "O", "P"],
  ["H", "J", "K", "L", ";"],
  ["V", "B", "N", "M", ","],
  [".", "SPACE", ":", "RETURN", "-"],
];

const CODE_BY_LABEL = {
  C: ["KeyC"],
  X: ["KeyX"],
  Z: ["KeyZ"],
  SHIFT: ["ShiftLeft", "ShiftRight"],
  CTL: ["ControlLeft", "ControlRight"],
  A: ["KeyA"],
  S: ["KeyS"],
  D: ["KeyD"],
  F: ["KeyF"],
  G: ["KeyG"],
  Q: ["KeyQ"],
  W: ["KeyW"],
  E: ["KeyE"],
  R: ["KeyR"],
  T: ["KeyT"],
  1: ["Digit1"],
  2: ["Digit2"],
  3: ["Digit3"],
  4: ["Digit4"],
  5: ["Digit5"],
  6: ["Digit6"],
  7: ["Digit7"],
  8: ["Digit8"],
  9: ["Digit9"],
  0: ["Digit0"],
  Y: ["KeyY"],
  U: ["KeyU"],
  I: ["KeyI"],
  O: ["KeyO"],
  P: ["KeyP"],
  H: ["KeyH"],
  J: ["KeyJ"],
  K: ["KeyK"],
  L: ["KeyL"],
  ";": ["Semicolon"],
  V: ["KeyV"],
  B: ["KeyB"],
  N: ["KeyN"],
  M: ["KeyM"],
  ",": ["Comma"],
  ".": ["Period"],
  SPACE: ["Space"],
  RETURN: ["Enter"],
  "-": ["Minus"],
  ":": ["Semicolon", "Quote"],
};

const KEY_BY_CODE = new Map();
const KEY_BY_ID = new Map();

export const KEY_MATRIX = ROW_LABELS.map((labels, row) =>
  labels.map((label, bit) => {
    const cell = {
      id: `r${row}b${bit}`,
      label,
      row,
      bit,
      codes: CODE_BY_LABEL[label] || [],
      modifier: label === "CTL" || label === "SHIFT",
    };
    KEY_BY_ID.set(cell.id, cell);
    for (const code of cell.codes) {
      if (!KEY_BY_CODE.has(code)) {
        KEY_BY_CODE.set(code, cell);
      }
    }
    return Object.freeze(cell);
  }),
);

export const KEY_CELLS = Object.freeze(KEY_MATRIX.flat());

const KEY_BY_VALUE = new Map([
  [" ", KEY_BY_ID.get("r8b1")],
  ["Enter", KEY_BY_ID.get("r8b3")],
  [";", KEY_BY_ID.get("r6b4")],
  [":", KEY_BY_ID.get("r8b2")],
  ["*", KEY_BY_ID.get("r8b2")],
  ["+", KEY_BY_ID.get("r8b2")],
  [",", KEY_BY_ID.get("r7b4")],
  [".", KEY_BY_ID.get("r8b0")],
  ["-", KEY_BY_ID.get("r8b4")],
]);

export function findKeyCell(event) {
  return KEY_BY_CODE.get(event.code) || KEY_BY_VALUE.get(event.key) || null;
}

export function getKeyCell(id) {
  return KEY_BY_ID.get(id) || null;
}

export function keyId(row, bit) {
  return `r${row}b${bit}`;
}
