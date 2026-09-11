import { gameIdFromUrl, fetchGame, GameLaunch } from "./game-launch.js";
import { BrowserAudio } from "./audio.js";
import { DebuggerPanel, hex } from "./debugger.js";
import { EmulationFramePacer } from "./emulation-pacer.js";
import { DEFAULT_GAMEPAD_SETTINGS, GamepadController } from "./gamepad.js";
import { resolveKeyboardChord } from "./keymap.js";
import { InputRouter, PhysicalKeyboardController } from "./input.js";
import {
  deleteStoredRom,
  loadSettings,
  readStoredRom,
  saveRom,
  saveSettings,
  sha256,
} from "./storage.js";
import { VirtualKeyboard } from "./virtual-keyboard.js";

const WIDTH = 256;
const HEIGHT = 192;
const MAX_PENDING_LOGICAL_FRAMES = 12;
const MAX_WORKER_LOGICAL_FRAMES = 4;
const DEFAULT_SETTINGS = {
  virtualKeyboard: true,
  extendedRam: false,
  audioMuted: false,
  gamepad: DEFAULT_GAMEPAD_SETTINGS,
};

const element = (selector) => document.querySelector(selector);
const screen = element("#screen");
const context = screen.getContext("2d", { alpha: false });
const image = context.createImageData(WIDTH, HEIGHT);
const coreStatus = element("#core-status");
const romStatus = element("#rom-status");
const programStatus = element("#program-status");
const gamepadStatus = element("#gamepad-status");
const errorStatus = element("#error-status");
const romFile = element("#rom-file");
const programFile = element("#program-file");
const programEntry = element("#program-entry");
const runEntryButton = element("#run-entry");
const loadSavedButton = element("#load-saved");
const removeRomButton = element("#remove-rom");
const pauseButton = element("#pause");
const resetButton = element("#reset");
const muteButton = element("#mute");
const audioEnableButton = element("#audio-enable");
const toggleKeyboardButton = element("#toggle-keyboard");
const keyboardMode = element("#keyboard-mode");
const extendedRam = element("#extended-ram");
const toggleDebuggerButton = element("#toggle-debugger");

const settings = loadSettings(DEFAULT_SETTINGS);
let running = false;
let romLoaded = false;
let frameInFlight = false;
let storedRom = null;
let coreReady = false;
let pendingRom = null;
let frameNumber = 0;
let lastState = null;
let pcmSampleCount = 0;
let pcmActiveSampleCount = 0;
let pendingLogicalFrames = 0;
let gameLaunch = null;

const worker = new Worker(new URL("./worker.js", import.meta.url));
const browserAudio = new BrowserAudio({ onStateChange: updateMuteUi });
const framePacer = new EmulationFramePacer({ maxCatchUpFrames: 4 });
const debuggerView = new DebuggerPanel({
  root: element("#debugger"),
  toggleButton: toggleDebuggerButton,
  worker,
  isAvailable: () => romLoaded,
  onPause: () => {
    running = false;
    pauseButton.textContent = "Resume";
    setStatus("Paused");
  },
  onError: setError,
});

function setStatus(message, isReady = false) {
  coreStatus.textContent = message;
  coreStatus.classList.toggle("ready", isReady);
}

function setError(error) {
  errorStatus.textContent = error ? String(error.message || error) : "";
  if (error && !element("#game-launch").hidden) {
    element("#game-launch-status").textContent = errorStatus.textContent;
  }
}

function sendKey(row, bit, pressed) {
  if (romLoaded) worker.postMessage({ type: "key", row, bit, pressed });
}

function sendJoystick(mask) {
  if (romLoaded) worker.postMessage({ type: "joystick", mask });
}

const input = new InputRouter(sendKey, sendJoystick);
const physicalKeyboard = new PhysicalKeyboardController(input, resolveKeyboardChord);
const virtualKeyboard = new VirtualKeyboard(element("#virtual-keyboard"), input);
virtualKeyboard.setActive(Boolean(settings.virtualKeyboard));

const gamepad = new GamepadController(
  input,
  settings.gamepad || DEFAULT_GAMEPAD_SETTINGS,
  (message) => { gamepadStatus.textContent = message; },
);

function updateKeyboardButton() {
  toggleKeyboardButton.textContent = virtualKeyboard.active ? "Hide keyboard" : "Show keyboard";
}

function updateMuteUi() {
  muteButton.textContent = browserAudio.muted ? "Sound off" : browserAudio.ready ? "Sound on" : "Enable sound";
  muteButton.setAttribute("aria-pressed", String(browserAudio.muted));
  muteButton.dataset.audioState = browserAudio.context?.state ?? "not-created";
  muteButton.dataset.audioReady = String(browserAudio.ready);
  audioEnableButton.hidden = !romLoaded || browserAudio.muted || browserAudio.ready;
  muteButton.dataset.audioBackend = browserAudio.backend;
  muteButton.dataset.audioWorkletStarted = String(browserAudio.workletStarted);
  muteButton.dataset.pcmActiveSamples = String(pcmActiveSampleCount);
  muteButton.dataset.audioBufferedSamples = String(browserAudio.metrics.bufferedSamples);
  muteButton.dataset.audioDroppedSamples = String(browserAudio.metrics.droppedSamples);
  muteButton.dataset.audioUnderflowSamples = String(browserAudio.metrics.underflowSamples);
  muteButton.dataset.audioRebufferCount = String(browserAudio.metrics.rebufferCount);
}

function resetFramePacing(timestamp = performance.now()) {
  framePacer.reset(timestamp);
  pendingLogicalFrames = 0;
}

async function unlockAudio() {
  if (browserAudio.muted) return false;
  try {
    const pending = browserAudio.unlock();
    updateMuteUi();
    return await pending;
  } catch (error) {
    if (error.name === "NotAllowedError") return false;
    throw error;
  } finally {
    updateMuteUi();
  }
}

browserAudio.setMuted(Boolean(settings.audioMuted));
extendedRam.checked = Boolean(settings.extendedRam);
updateKeyboardButton();
updateMuteUi();

function drawFrame(buffer) {
  const frame = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
  if (frame.length !== WIDTH * HEIGHT) throw new Error(`Invalid frame size: ${frame.length}`);
  for (let index = 0; index < frame.length; index += 1) {
    const offset = index * 4;
    const value = frame[index] ? 239 : 5;
    image.data[offset] = value;
    image.data[offset + 1] = value;
    image.data[offset + 2] = value;
    image.data[offset + 3] = 255;
  }
  context.putImageData(image, 0, 0);
}

function postRom(bytes) {
  const copy = bytes.slice();
  browserAudio.clear();
  worker.postMessage(
    { type: "loadRom", buffer: copy.buffer, extendedRam: extendedRam.checked },
    [copy.buffer],
  );
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
  // Try permitted autoplay without making ROM/game loading wait on a gesture.
  void unlockAudio().catch(setError);
  updateMuteUi();
  for (const control of [pauseButton, resetButton, toggleKeyboardButton, toggleDebuggerButton, programFile]) {
    control.disabled = false;
  }
  pauseButton.textContent = "Pause";
  resetFramePacing();
  setStatus("Running", true);
  const ram = extendedRam.checked ? "32K RAM" : "16K RAM";
  romStatus.textContent = `${filename || info.name || "ROM"} · ${info.format} · ${info.size} bytes · ${ram}`;
  gameLaunch?.romLoaded();
  const validated = pendingRom;
  pendingRom = null;
  if (!validated) return;
  try {
    storedRom = await saveRom(validated.bytes, validated.metadata);
  } catch (error) {
    setError(error);
  }
}

function updateMachineState(state) {
  if (!state) return;
  lastState = state;
  coreStatus.dataset.clockCount = String(state.clockCount ?? 0);
  virtualKeyboard.setGraphicsMode(Boolean(state.graphicsMode));
  keyboardMode.textContent = state.graphicsMode ? "GRAPH" : "ALPHA";
  if (state.breakpointHit !== null && state.breakpointHit !== undefined) {
    running = false;
    pauseButton.textContent = "Resume";
    setStatus(`Break $${hex(state.breakpointHit, 4)}`);
    debuggerView.request();
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
      virtualKeyboard.setRomAssets(message.font, message.normal, message.shift);
      void setRomUi(message.info, pendingRom?.metadata.filename || storedRom?.filename);
    } else if (message.type === "programLoaded") {
      const info = message.info;
      if (gameLaunch?.state === "loading") {
        if (info.entryPoint !== gameLaunch.game.entry || info.basic) {
          throw new Error("Game entry does not match the catalog");
        }
        gameLaunch.state = "loaded";
        element("#game-launch-status").textContent = `${gameLaunch.game.title} · ${gameLaunch.game.version} · 16KB`;
        screen.focus({preventScroll:true});
      }
      programEntry.value = "";
      programEntry.disabled = true;
      runEntryButton.disabled = true;
      const shownEntry = info.entryPoint ?? info.suggestedEntryPoint;
      const entry = shownEntry === null || shownEntry === undefined
        ? ""
        : ` · entry $${hex(shownEntry, 4)}`;
      const action = info.autostartCommand ? ` · ${info.autostartCommand}` : "";
      const source = info.entrySource === "pbin-start" ? " · PBIN start" : "";
      const format = info.basic ? "BASIC" : `V${info.version}`;
      programStatus.textContent = `${info.name || "PROGRAM"} · ${format}${entry}${source}${action}`;
      if (shownEntry !== null && shownEntry !== undefined) {
        programEntry.value = hex(shownEntry, 4);
        programEntry.disabled = false;
        runEntryButton.disabled = false;
      }
      running = true;
      resetFramePacing();
      pauseButton.textContent = "Pause";
      setStatus("Running", true);
    } else if (message.type === "entryQueued") {
      running = true;
      resetFramePacing();
      pauseButton.textContent = "Pause";
      programStatus.textContent = `${programStatus.textContent.split(" · queued")[0]} · queued ${message.command}`;
      setStatus("Running", true);
    } else if (message.type === "frame") {
      frameInFlight = false;
      drawFrame(message.buffer);
      pcmSampleCount += Math.floor((message.audio?.byteLength || 0) / 2);
      const pcm = message.audio ? new Int16Array(message.audio) : new Int16Array();
      for (const sample of pcm) {
        if (sample !== 0) pcmActiveSampleCount += 1;
      }
      muteButton.dataset.pcmSamples = String(pcmSampleCount);
      muteButton.dataset.pcmActiveSamples = String(pcmActiveSampleCount);
      browserAudio.enqueue(message.audio);
      updateMuteUi();
      updateMachineState(message.state);
      const requestedGame = gameLaunch?.frame(message.state?.clockCount ?? 0);
      if (requestedGame) {
        input.clear();
        worker.postMessage({type:"clearKeys"});
        browserAudio.clear();
        const copy = requestedGame.bytes.slice();
        worker.postMessage({type:"loadProgram", filename:`${requestedGame.id}.prg`, buffer:copy.buffer}, [copy.buffer]);
      }
      frameNumber += Math.max(1, Number(message.logicalFrames) || 0);
      debuggerView.frameTick(frameNumber);
    } else if (message.type === "debugSnapshot") {
      debuggerView.receive(message);
    } else if (message.type === "error") {
      gameLaunch?.cancel();
      pendingRom = null;
      frameInFlight = false;
      debuggerView.clearPending();
      running = false;
      resetFramePacing();
      setStatus("Error");
      setError(message.message);
    }
  } catch (error) {
    gameLaunch?.cancel();
    frameInFlight = false;
    debuggerView.clearPending();
    running = false;
    setError(error);
  }
});

worker.addEventListener("error", (event) => {
  frameInFlight = false;
  debuggerView.clearPending();
  running = false;
  resetFramePacing();
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

programFile.addEventListener("change", async () => {
  const file = programFile.files?.[0];
  if (!file || !romLoaded) return;
  setError(null);
  try {
    const bytes = new Uint8Array(await file.arrayBuffer());
    browserAudio.clear();
    const copy = bytes.slice();
    worker.postMessage(
      { type: "loadProgram", filename: file.name, buffer: copy.buffer },
      [copy.buffer],
    );
  } catch (error) {
    setError(error);
  } finally {
    programFile.value = "";
  }
});

loadSavedButton.addEventListener("click", loadSavedRom);
removeRomButton.addEventListener("click", async () => {
  try {
    browserAudio.clear();
    await deleteStoredRom();
    storedRom = null;
    romLoaded = false;
    running = false;
    resetFramePacing();
    input.clear();
    worker.postMessage({ type: "clearKeys" });
    for (const control of [pauseButton, resetButton, toggleKeyboardButton, toggleDebuggerButton, programFile]) {
      control.disabled = true;
    }
    programEntry.disabled = true;
    runEntryButton.disabled = true;
    programEntry.value = "";
    setStatus("ROM required");
    romStatus.textContent = "No ROM loaded";
    programStatus.textContent = "No program loaded";
    updateMuteUi();
  } catch (error) {
    setError(error);
  }
});

pauseButton.addEventListener("click", () => {
  running = !running;
  resetFramePacing();
  if (running && lastState?.breakpointHit !== null && lastState?.breakpointHit !== undefined) {
    worker.postMessage({ type: "continue" });
    lastState = { ...lastState, breakpointHit: null };
  }
  pauseButton.textContent = running ? "Pause" : "Resume";
  setStatus(running ? "Running" : "Paused", running);
});

resetButton.addEventListener("click", () => {
  if (romLoaded && window.confirm("Really reset? Current game progress will be lost.")) {
    browserAudio.clear();
    input.clear();
    worker.postMessage({ type: "reset" });
    running = true;
    resetFramePacing();
    pauseButton.textContent = "Pause";
    setStatus("Running", true);
  }
});

muteButton.addEventListener("click", () => {
  // When playback is blocked, this button enables sound instead of muting it.
  browserAudio.setMuted(!browserAudio.muted && browserAudio.ready);
  settings.audioMuted = browserAudio.muted;
  saveSettings(settings);
  if (!browserAudio.muted) void unlockAudio().catch(setError);
  updateMuteUi();
});

audioEnableButton.addEventListener("click", () => {
  void unlockAudio().catch(setError);
  screen.focus({ preventScroll: true });
});

toggleKeyboardButton.addEventListener("click", () => {
  settings.virtualKeyboard = virtualKeyboard.toggle();
  saveSettings(settings);
  updateKeyboardButton();
});

extendedRam.addEventListener("change", async () => {
  settings.extendedRam = extendedRam.checked;
  saveSettings(settings);
  if (romLoaded) await loadSavedRom();
});

runEntryButton.addEventListener("click", () => {
  try {
    const token = programEntry.value.trim().replace(/^\$/u, "").replace(/^0x/iu, "");
    if (!/^[0-9a-f]{1,4}$/iu.test(token)) throw new Error("USR entry must be a hexadecimal address");
    const address = Number.parseInt(token, 16);
    input.clear();
    worker.postMessage({ type: "runEntry", address });
    setError(null);
  } catch (error) {
    setError(error);
  }
});

function isEditableTarget(target) {
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target?.isContentEditable;
}

window.addEventListener("keydown", (event) => {
  if ([muteButton, audioEnableButton].includes(event.target) && ["Enter", "Space"].includes(event.code)) {
    return; // Let the native button click enable audio without a JR-100 key.
  }
  void unlockAudio().catch(setError);
  if (event.code === "Escape" && romLoaded) {
    debuggerView.toggle();
    event.preventDefault();
    return;
  }
  if (isEditableTarget(event.target)) return;
  if (!physicalKeyboard.keyDown(event)) return;
  virtualKeyboard.refresh();
  event.preventDefault();
});

window.addEventListener("keyup", (event) => {
  if (isEditableTarget(event.target)) return;
  if (!physicalKeyboard.keyUp(event)) return;
  virtualKeyboard.refresh();
  event.preventDefault();
});

window.addEventListener("click", (event) => {
  if (muteButton.contains(event.target) || audioEnableButton.contains(event.target)) return;
  void unlockAudio().catch(setError);
});
window.addEventListener("blur", () => {
  input.releaseMomentary();
  input.setJoystickMask(0);
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden) input.releaseMomentary();
  resetFramePacing();
});

async function initializeStoredRom() {
  try {
    const gameId = gameIdFromUrl(location.href);
    if (gameId) {
      element("#game-launch").hidden = false;
      element("#game-launch-status").textContent = "Preparing game...";
      const game = await fetchGame(gameId, new URL("./", location.href));
      gameLaunch = new GameLaunch(game);
      extendedRam.checked = false;
      extendedRam.disabled = true;
      element("#game-source").href = game.sourceUrl;
      element("#game-source").hidden = false;
      element("#game-launch-status").textContent = `Starting ${game.title}...`;
    }
    storedRom = await readStoredRom();
    if (gameLaunch && !storedRom) {
      element("#game-launch-status").textContent = "Saved BASIC ROM required";
      throw new Error("Set up your own BASIC ROM in this browser first, then reload this game link.");
    }
    if (storedRom) {
      romStatus.textContent = `${storedRom.filename || "Saved ROM"} · saved locally`;
      await loadSavedRom();
    }
  } catch (error) {
    setError(error);
  }
}

function frameLoop(now) {
  gamepad.update();
  if (!(running && coreReady && romLoaded)) {
    resetFramePacing(now);
  } else {
    pendingLogicalFrames = Math.min(
      MAX_PENDING_LOGICAL_FRAMES,
      pendingLogicalFrames + framePacer.advance(now),
    );
  }
  if (running && coreReady && romLoaded && !frameInFlight && pendingLogicalFrames > 0) {
    const logicalFrames = Math.min(MAX_WORKER_LOGICAL_FRAMES, pendingLogicalFrames);
    pendingLogicalFrames -= logicalFrames;
    frameInFlight = true;
    worker.postMessage({ type: "runFrames", logicalFrames });
  }
  requestAnimationFrame(frameLoop);
}

setStatus("ROM required");
void initializeStoredRom();
requestAnimationFrame(frameLoop);
