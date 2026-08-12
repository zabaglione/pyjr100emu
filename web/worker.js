const PYODIDE_VERSION = "0.26.4";
const PYODIDE_BASE = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

importScripts("./matrix-input-core.js");

let pyodide = null;
let createCore = null;
let resetCore = null;
let runFrame = null;
let setKey = null;
let clearKeys = null;
let setJoystickMask = null;
let frameBuffer = null;
let audioBuffer = null;
let fontData = null;
let normalKeyCodes = null;
let shiftKeyCodes = null;
let loadProgram = null;
let runEntry = null;
let coreState = null;
let debugState = null;
let readMemory = null;
let setBreakpoints = null;
let continueExecution = null;
let stepInstruction = null;
let inputScheduler = null;
let bootPromise = null;

function postError(error) {
  self.postMessage({
    type: "error",
    message: error instanceof Error ? error.message : String(error),
    stack: error instanceof Error ? error.stack || "" : "",
  });
}

function unwrap(value) {
  if (!value || typeof value.toJs !== "function") return value;
  const result = value.toJs({ create_proxies: false });
  value.destroy?.();
  if (result instanceof Map) return mapToObject(result);
  if (Array.isArray(result)) return Uint8Array.from(result);
  return result;
}

function mapToObject(value) {
  return Object.fromEntries(
    [...value.entries()].map(([key, item]) => [key, cloneableValue(item)]),
  );
}

function cloneableValue(value) {
  if (value instanceof Map) return mapToObject(value);
  if (Array.isArray(value)) return value.map(cloneableValue);
  return value;
}

async function boot() {
  if (bootPromise) return bootPromise;
  bootPromise = (async () => {
    self.postMessage({ type: "loading", stage: "pyodide" });
    importScripts(`${PYODIDE_BASE}pyodide.js`);
    pyodide = await loadPyodide({ indexURL: PYODIDE_BASE });

    self.postMessage({ type: "loading", stage: "jr100emu" });
    const packageUrl = new URL("python/jr100emu.zip", self.location.href);
    const response = await fetch(packageUrl);
    if (!response.ok) throw new Error(`Python package fetch failed: ${response.status}`);
    const packageBytes = new Uint8Array(await response.arrayBuffer());
    pyodide.FS.writeFile("/home/pyodide/jr100emu.zip", packageBytes);
    await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, "/home/pyodide/jr100emu.zip")
from jr100emu.browser.bridge import (
    create_core, reset, run_frame, set_key, clear_keys, set_joystick_mask, frame_buffer,
    audio_buffer, font_data, normal_key_codes, shift_key_codes, load_program, run_entry,
    state, debug_state, read_memory, set_breakpoints, continue_execution,
    step_instruction,
)
`);
    createCore = pyodide.globals.get("create_core");
    resetCore = pyodide.globals.get("reset");
    runFrame = pyodide.globals.get("run_frame");
    setKey = pyodide.globals.get("set_key");
    clearKeys = pyodide.globals.get("clear_keys");
    setJoystickMask = pyodide.globals.get("set_joystick_mask");
    frameBuffer = pyodide.globals.get("frame_buffer");
    audioBuffer = pyodide.globals.get("audio_buffer");
    fontData = pyodide.globals.get("font_data");
    normalKeyCodes = pyodide.globals.get("normal_key_codes");
    shiftKeyCodes = pyodide.globals.get("shift_key_codes");
    loadProgram = pyodide.globals.get("load_program");
    runEntry = pyodide.globals.get("run_entry");
    coreState = pyodide.globals.get("state");
    debugState = pyodide.globals.get("debug_state");
    readMemory = pyodide.globals.get("read_memory");
    setBreakpoints = pyodide.globals.get("set_breakpoints");
    continueExecution = pyodide.globals.get("continue_execution");
    stepInstruction = pyodide.globals.get("step_instruction");
    inputScheduler = new self.MatrixInputScheduler(
      (row, bit, pressed) => call(setKey, row, bit, pressed),
    );
    self.postMessage({ type: "ready", pyodideVersion: PYODIDE_VERSION });
  })();
  try {
    await bootPromise;
  } catch (error) {
    bootPromise = null;
    throw error;
  }
}

function call(functionProxy, ...args) {
  return unwrap(functionProxy(...args));
}

async function handleMessage(message) {
  await boot();
  switch (message.type) {
    case "loadRom": {
      const values = new Uint8Array(message.buffer);
      const pyValues = pyodide.toPy([...values]);
      try {
        inputScheduler.clear();
        const info = call(createCore, pyValues, Boolean(message.extendedRam));
        const font = toTransfer(call(fontData));
        const normal = toTransfer(call(normalKeyCodes));
        const shift = toTransfer(call(shiftKeyCodes));
        self.postMessage(
          { type: "romLoaded", info, font: font.buffer, normal: normal.buffer, shift: shift.buffer },
          [font.buffer, normal.buffer, shift.buffer],
        );
        const frame = call(frameBuffer);
        postFrame(frame);
      } finally {
        pyValues.destroy?.();
      }
      break;
    }
    case "runFrame": {
      inputScheduler.beforeFrame();
      const frame = call(runFrame);
      inputScheduler.afterFrame();
      postFrame(frame);
      break;
    }
    case "reset":
      inputScheduler.clear();
      call(clearKeys);
      call(resetCore);
      postFrame(call(frameBuffer));
      break;
    case "key":
      inputScheduler.key(message.row, message.bit, Boolean(message.pressed));
      break;
    case "clearKeys":
      inputScheduler.clear();
      call(clearKeys);
      break;
    case "joystick":
      call(setJoystickMask, message.mask);
      break;
    case "loadProgram": {
      const values = new Uint8Array(message.buffer);
      const pyValues = pyodide.toPy([...values]);
      try {
        const info = call(loadProgram, pyValues, message.filename || "");
        self.postMessage({ type: "programLoaded", info });
      } finally {
        pyValues.destroy?.();
      }
      break;
    }
    case "runEntry":
      inputScheduler.clear();
      call(clearKeys);
      self.postMessage({ type: "entryQueued", command: call(runEntry, message.address) });
      break;
    case "debugSnapshot":
      postDebugSnapshot(message.start, message.length);
      break;
    case "setBreakpoints": {
      const addresses = pyodide.toPy(message.addresses || []);
      try {
        call(setBreakpoints, addresses);
      } finally {
        addresses.destroy?.();
      }
      break;
    }
    case "continue":
      call(continueExecution);
      break;
    case "step":
      call(stepInstruction);
      postFrame(call(frameBuffer));
      postDebugSnapshot(message.start, message.length);
      break;
    default:
      throw new Error(`Unknown worker message: ${message.type}`);
  }
}

function toTransfer(value) {
  const bytes = value instanceof Uint8Array ? value : Uint8Array.from(value || []);
  return new Uint8Array(bytes.slice().buffer);
}

function postFrame(value) {
  const frame = toTransfer(value);
  const pcm = toTransfer(call(audioBuffer));
  const currentState = call(coreState);
  self.postMessage(
    { type: "frame", buffer: frame.buffer, audio: pcm.buffer, state: currentState },
    [frame.buffer, pcm.buffer],
  );
}

function postDebugSnapshot(start = 0, length = 128) {
  const snapshot = call(debugState);
  const memory = toTransfer(call(readMemory, start || 0, length || 128));
  self.postMessage(
    { type: "debugSnapshot", state: snapshot, start: start || 0, memory: memory.buffer },
    [memory.buffer],
  );
}

self.addEventListener("message", (event) => {
  handleMessage(event.data).catch(postError);
});
