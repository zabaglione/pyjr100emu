importScripts("./matrix-input-core.js");

const CYCLES_PER_FRAME = 14900;

let wasm = null;
let inputScheduler = null;
let bootPromise = null;

function postError(error) {
  self.postMessage({
    type: "error",
    message: error instanceof Error ? error.message : String(error),
    stack: error instanceof Error ? error.stack || "" : "",
  });
}

function lastError() {
  if (!wasm) return "WASM core is not ready";
  return wasm.UTF8ToString(wasm._jr_last_error()) || "WASM core operation failed";
}

function check(result) {
  if (result !== 0) throw new Error(lastError());
}

function jsonResult() {
  return JSON.parse(wasm.UTF8ToString(wasm._jr_result_json()));
}

function jsonAt(pointer) {
  return JSON.parse(wasm.UTF8ToString(pointer));
}

function copyBytes(pointer, length) {
  if (!pointer || length <= 0) return new Uint8Array();
  return wasm.HEAPU8.slice(pointer, pointer + length);
}

function transferInput(values) {
  const bytes = values instanceof Uint8Array ? values : new Uint8Array(values || 0);
  const pointer = wasm._jr_input_resize(bytes.byteLength);
  if (bytes.byteLength > 0) wasm.HEAPU8.set(bytes, pointer);
  return bytes.byteLength;
}

function state() {
  return jsonAt(wasm._jr_state_json());
}

function debugState() {
  return jsonAt(wasm._jr_debug_json());
}

async function boot() {
  if (bootPromise) return bootPromise;
  bootPromise = (async () => {
    self.postMessage({ type: "loading", stage: "WASM" });
    importScripts("./wasm/jr100-core.js");
    if (typeof self.createJR100Module !== "function") {
      throw new Error("WASM module factory is unavailable");
    }
    wasm = await self.createJR100Module({
      locateFile(path) {
        const filename = path.split("/").at(-1);
        return new URL(`./wasm/${filename}`, self.location.href).href;
      },
    });
    inputScheduler = new self.MatrixInputScheduler(
      (row, bit, pressed) => check(wasm._jr_set_key(row, bit, pressed ? 1 : 0)),
    );
    self.postMessage({ type: "ready", core: "C++/WASM" });
  })();
  try {
    await bootPromise;
  } catch (error) {
    bootPromise = null;
    throw error;
  }
}

function postFrame() {
  const frame = copyBytes(wasm._jr_frame_data(), wasm._jr_frame_size());
  const audioLength = wasm._jr_audio_size() * 2;
  const pcm = copyBytes(wasm._jr_audio_data(), audioLength);
  check(wasm._jr_clear_audio());
  const currentState = state();
  self.postMessage(
    { type: "frame", buffer: frame.buffer, audio: pcm.buffer, state: currentState },
    [frame.buffer, pcm.buffer],
  );
}

function postDebugSnapshot(start = 0, length = 128) {
  const address = Number(start || 0) & 0xffff;
  const requested = Number(length || 128);
  const pointer = wasm._jr_read_memory(address, requested);
  const actual = wasm._jr_read_memory_size();
  if (actual !== requested) throw new Error(lastError());
  const memory = copyBytes(pointer, actual);
  self.postMessage(
    { type: "debugSnapshot", state: debugState(), start: address, memory: memory.buffer },
    [memory.buffer],
  );
}

async function handleMessage(message) {
  await boot();
  switch (message.type) {
    case "loadRom": {
      const values = new Uint8Array(message.buffer);
      inputScheduler.clear();
      const size = transferInput(values);
      check(wasm._jr_create_core(size, message.extendedRam ? 1 : 0));
      const info = jsonResult();
      const font = copyBytes(wasm._jr_font_data(), wasm._jr_font_size());
      const codeLength = wasm._jr_key_code_size();
      const normal = copyBytes(wasm._jr_normal_codes(), codeLength);
      const shift = copyBytes(wasm._jr_shift_codes(), codeLength);
      self.postMessage(
        { type: "romLoaded", info, font: font.buffer, normal: normal.buffer, shift: shift.buffer },
        [font.buffer, normal.buffer, shift.buffer],
      );
      postFrame();
      break;
    }
    case "runFrame":
      inputScheduler.beforeFrame();
      check(wasm._jr_run_frame(CYCLES_PER_FRAME));
      inputScheduler.afterFrame();
      postFrame();
      break;
    case "reset":
      inputScheduler.clear();
      check(wasm._jr_clear_keys());
      check(wasm._jr_reset());
      postFrame();
      break;
    case "key":
      inputScheduler.key(message.row, message.bit, Boolean(message.pressed));
      break;
    case "clearKeys":
      inputScheduler.clear();
      check(wasm._jr_clear_keys());
      break;
    case "joystick":
      check(wasm._jr_set_joystick(message.mask));
      break;
    case "loadProgram": {
      const values = new Uint8Array(message.buffer);
      const size = transferInput(values);
      const result = wasm.ccall(
        "jr_load_program",
        "number",
        ["number", "string"],
        [size, message.filename || ""],
      );
      check(result);
      self.postMessage({ type: "programLoaded", info: jsonResult() });
      break;
    }
    case "runEntry":
      inputScheduler.clear();
      check(wasm._jr_clear_keys());
      check(wasm._jr_run_entry(message.address));
      self.postMessage({
        type: "entryQueued",
        command: wasm.UTF8ToString(wasm._jr_result_json()),
      });
      break;
    case "debugSnapshot":
      postDebugSnapshot(message.start, message.length);
      break;
    case "setBreakpoints": {
      const addresses = message.addresses || [];
      const bytes = new Uint8Array(addresses.length * 2);
      const view = new DataView(bytes.buffer);
      addresses.forEach((address, index) => view.setUint16(index * 2, address, true));
      transferInput(bytes);
      check(wasm._jr_set_breakpoints(addresses.length));
      break;
    }
    case "continue":
      check(wasm._jr_continue());
      break;
    case "step":
      check(wasm._jr_step());
      postFrame();
      postDebugSnapshot(message.start, message.length);
      break;
    default:
      throw new Error(`Unknown worker message: ${message.type}`);
  }
}

self.addEventListener("message", (event) => {
  handleMessage(event.data).catch(postError);
});
