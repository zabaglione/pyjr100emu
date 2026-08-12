const PYODIDE_VERSION = "0.26.4";
const PYODIDE_BASE = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

let pyodide = null;
let createCore = null;
let resetCore = null;
let runFrame = null;
let setKey = null;
let clearKeys = null;
let setJoystickMask = null;
let frameBuffer = null;
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
  if (result instanceof Map) return Object.fromEntries(result.entries());
  if (Array.isArray(result)) return Uint8Array.from(result);
  return result;
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
)
`);
    createCore = pyodide.globals.get("create_core");
    resetCore = pyodide.globals.get("reset");
    runFrame = pyodide.globals.get("run_frame");
    setKey = pyodide.globals.get("set_key");
    clearKeys = pyodide.globals.get("clear_keys");
    setJoystickMask = pyodide.globals.get("set_joystick_mask");
    frameBuffer = pyodide.globals.get("frame_buffer");
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
        const info = call(createCore, pyValues);
        self.postMessage({ type: "romLoaded", info });
        const frame = call(frameBuffer);
        postFrame(frame);
      } finally {
        pyValues.destroy?.();
      }
      break;
    }
    case "runFrame":
      postFrame(call(runFrame));
      break;
    case "reset":
      call(resetCore);
      postFrame(call(frameBuffer));
      break;
    case "key":
      call(setKey, message.row, message.bit, Boolean(message.pressed));
      break;
    case "clearKeys":
      call(clearKeys);
      break;
    case "joystick":
      call(setJoystickMask, message.mask);
      break;
    default:
      throw new Error(`Unknown worker message: ${message.type}`);
  }
}

function postFrame(value) {
  const frame = value instanceof Uint8Array ? value : Uint8Array.from(value || []);
  const transferable = frame.buffer.slice(frame.byteOffset, frame.byteOffset + frame.byteLength);
  self.postMessage({ type: "frame", buffer: transferable }, [transferable]);
}

self.addEventListener("message", (event) => {
  handleMessage(event.data).catch(postError);
});
