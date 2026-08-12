import { DEFAULT_GAMEPAD_SETTINGS, GamepadController } from "./gamepad.js";
import { findKeyCell } from "./keymap.js";
import { InputRouter } from "./input.js";
import { loadSettings, readStoredRom, saveRom, saveSettings, sha256, deleteStoredRom } from "./storage.js";
import { VirtualKeyboard } from "./virtual-keyboard.js";

const WIDTH = 256;
const HEIGHT = 192;
const DEFAULT_SETTINGS = {
  virtualKeyboard: false,
  gamepad: DEFAULT_GAMEPAD_SETTINGS,
};

const screen = document.querySelector("#screen");
const context = screen.getContext("2d", { alpha: false });
const image = context.createImageData(WIDTH, HEIGHT);
const coreStatus = document.querySelector("#core-status");
const romStatus = document.querySelector("#rom-status");
const gamepadStatus = document.querySelector("#gamepad-status");
const errorStatus = document.querySelector("#error-status");
const romFile = document.querySelector("#rom-file");
const loadSavedButton = document.querySelector("#load-saved");
const removeRomButton = document.querySelector("#remove-rom");
const pauseButton = document.querySelector("#pause");
const resetButton = document.querySelector("#reset");
const toggleKeyboardButton = document.querySelector("#toggle-keyboard");

const settings = loadSettings(DEFAULT_SETTINGS);
let running = false;
let romLoaded = false;
let frameInFlight = false;
let storedRom = null;
let coreReady = false;
let pendingRom = null;

const worker = new Worker(new URL("./worker.js", import.meta.url));

function setStatus(message, isReady = false) {
  coreStatus.textContent = message;
  coreStatus.classList.toggle("ready", isReady);
}

function setError(error) {
  errorStatus.textContent = error ? String(error.message || error) : "";
}

function sendKey(row, bit, pressed) {
  if (romLoaded) worker.postMessage({ type: "key", row, bit, pressed });
}

function sendJoystick(mask) {
  if (romLoaded) worker.postMessage({ type: "joystick", mask });
}

const input = new InputRouter(sendKey, sendJoystick);
const virtualKeyboard = new VirtualKeyboard(document.querySelector("#virtual-keyboard"), input);
virtualKeyboard.setActive(Boolean(settings.virtualKeyboard));
toggleKeyboardButton.textContent = virtualKeyboard.active ? "Hide keyboard" : "Virtual keyboard";

const gamepad = new GamepadController(
  input,
  virtualKeyboard,
  settings.gamepad || DEFAULT_GAMEPAD_SETTINGS,
  (message) => { gamepadStatus.textContent = message; },
);

function drawFrame(buffer) {
  const frame = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  if (frame.length !== WIDTH * HEIGHT) throw new Error(`Invalid frame size: ${frame.length}`);
  for (let index = 0; index < frame.length; index += 1) {
    const offset = index * 4;
    const value = frame[index] ? 255 : 0;
    image.data[offset] = value;
    image.data[offset + 1] = value;
    image.data[offset + 2] = value;
    image.data[offset + 3] = 255;
  }
  context.putImageData(image, 0, 0);
}

function postRom(bytes) {
  const copy = bytes.slice();
  worker.postMessage({ type: "loadRom", buffer: copy.buffer }, [copy.buffer]);
}

async function loadRomBytes(bytes, name) {
  if (!bytes?.length) throw new Error("The selected ROM is empty");
  const digest = await sha256(bytes);
  pendingRom = {
    bytes: bytes.slice(),
    metadata: { filename: name || "jr100.rom", sha256: digest, size: bytes.length },
  };
  postRom(bytes);
}

async function loadSavedRom() {
  setError(null);
  try {
    const record = await readStoredRom();
    if (!record) throw new Error("No saved ROM is available");
    pendingRom = null;
    storedRom = record;
    postRom(record.bytes);
  } catch (error) {
    setError(error);
  }
}

async function setRomUi(info, filename) {
  romLoaded = true;
  running = true;
  pauseButton.disabled = false;
  resetButton.disabled = false;
  toggleKeyboardButton.disabled = false;
  pauseButton.textContent = "Pause";
  setStatus("Running", true);
  romStatus.textContent = `${filename || info.name || "ROM"} (${info.format}, ${info.size} bytes)`;
  const validated = pendingRom;
  pendingRom = null;
  if (!validated) return;
  try {
    storedRom = await saveRom(validated.bytes, validated.metadata);
  } catch (error) {
    setError(error);
  }
}

worker.addEventListener("message", (event) => {
  const message = event.data;
  try {
    if (message.type === "loading") {
      setStatus(`Loading ${message.stage}`);
    } else if (message.type === "ready") {
      coreReady = true;
      setStatus("Core ready");
    } else if (message.type === "romLoaded") {
      void setRomUi(message.info, pendingRom?.metadata.filename || storedRom?.filename);
    } else if (message.type === "frame") {
      frameInFlight = false;
      drawFrame(message.buffer);
    } else if (message.type === "error") {
      pendingRom = null;
      frameInFlight = false;
      running = false;
      setStatus("Error");
      setError(message.message);
    }
  } catch (error) {
    frameInFlight = false;
    running = false;
    setError(error);
  }
});

worker.addEventListener("error", (event) => {
  frameInFlight = false;
  running = false;
  setStatus("Worker error");
  setError(event.message || "Worker failed");
});

romFile.addEventListener("change", async () => {
  const file = romFile.files?.[0];
  if (!file) return;
  setError(null);
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    storedRom = { filename: file.name };
    await loadRomBytes(bytes, file.name);
  } catch (error) {
    setError(error);
  } finally {
    romFile.value = "";
  }
});

loadSavedButton.addEventListener("click", loadSavedRom);
removeRomButton.addEventListener("click", async () => {
  try {
    await deleteStoredRom();
    storedRom = null;
    romLoaded = false;
    running = false;
    input.clear();
    pauseButton.disabled = true;
    resetButton.disabled = true;
    toggleKeyboardButton.disabled = true;
    setStatus("ROM required");
    romStatus.textContent = "No ROM loaded";
  } catch (error) {
    setError(error);
  }
});

pauseButton.addEventListener("click", () => {
  running = !running;
  pauseButton.textContent = running ? "Pause" : "Resume";
  setStatus(running ? "Running" : "Paused", running);
});

resetButton.addEventListener("click", () => {
  if (romLoaded) worker.postMessage({ type: "reset" });
});

toggleKeyboardButton.addEventListener("click", () => {
  const active = virtualKeyboard.toggle();
  toggleKeyboardButton.textContent = active ? "Hide keyboard" : "Virtual keyboard";
  settings.virtualKeyboard = active;
  saveSettings(settings);
});

window.addEventListener("keydown", (event) => {
  const cell = findKeyCell(event);
  if (!cell) return;
  event.preventDefault();
  if (!event.repeat) input.press(`physical:${event.code}`, cell);
});

window.addEventListener("keyup", (event) => {
  const cell = findKeyCell(event);
  if (!cell) return;
  event.preventDefault();
  input.release(`physical:${event.code}`);
});

window.addEventListener("blur", () => {
  input.releaseMomentary();
  input.setJoystickMask(0);
  virtualKeyboard.releaseGamepadKey();
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden) input.releaseMomentary();
});

async function initializeStoredRom() {
  try {
    storedRom = await readStoredRom();
    if (storedRom) {
      romStatus.textContent = `${storedRom.filename || "Saved ROM"} (saved locally)`;
      await loadSavedRom();
    }
  } catch (error) {
    setError(error);
  }
}

function frameLoop(now) {
  gamepad.update(now);
  if (running && coreReady && romLoaded && !frameInFlight) {
    frameInFlight = true;
    worker.postMessage({ type: "runFrame" });
  }
  requestAnimationFrame(frameLoop);
}

setStatus("ROM required");
initializeStoredRom();
requestAnimationFrame(frameLoop);
