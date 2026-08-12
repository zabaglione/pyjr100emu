const DB_NAME = "jr100emu-web";
const DB_VERSION = 1;
const ROM_STORE = "roms";
const ROM_KEY = "basic";
const SETTINGS_KEY = "jr100emu.settings";

function openDatabase() {
  if (!globalThis.indexedDB) {
    return Promise.reject(new Error("IndexedDB is not available"));
  }
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onerror = () => reject(request.error || new Error("IndexedDB open failed"));
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(ROM_STORE)) {
        request.result.createObjectStore(ROM_STORE);
      }
    };
    request.onsuccess = () => resolve(request.result);
  });
}

function transactionRequest(mode, callback) {
  return openDatabase().then(
    (db) =>
      new Promise((resolve, reject) => {
        const transaction = db.transaction(ROM_STORE, mode);
        const request = callback(transaction.objectStore(ROM_STORE));
        request.onerror = () => reject(request.error || new Error("IndexedDB request failed"));
        request.onsuccess = () => resolve(request.result);
        transaction.oncomplete = () => db.close();
        transaction.onerror = () => reject(transaction.error || new Error("IndexedDB transaction failed"));
      }),
  );
}

export async function readStoredRom() {
  const record = await transactionRequest("readonly", (store) => store.get(ROM_KEY));
  if (!record) return null;
  const bytes = record.bytes instanceof ArrayBuffer ? new Uint8Array(record.bytes) : new Uint8Array(record.bytes.buffer);
  return { ...record, bytes };
}

export async function saveRom(bytes, metadata) {
  const copy = bytes.slice().buffer;
  const record = { ...metadata, bytes: copy, savedAt: new Date().toISOString() };
  await transactionRequest("readwrite", (store) => store.put(record, ROM_KEY));
  return record;
}

export async function deleteStoredRom() {
  await transactionRequest("readwrite", (store) => store.delete(ROM_KEY));
}

export function loadSettings(defaults = {}) {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    return { ...defaults, ...(raw ? JSON.parse(raw) : {}) };
  } catch {
    return { ...defaults };
  }
}

export function saveSettings(settings) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    return false;
  }
  return true;
}

export async function sha256(bytes) {
  if (!globalThis.crypto?.subtle) return "";
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
}
