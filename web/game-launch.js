// Public game IDs resolve only to versioned artifacts in this app's catalog.
const ID = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/u;
const VERSION = /^\d+\.\d+\.\d+$/u;
const HASH = /^[a-f0-9]{64}$/u;

export function gameIdFromUrl(value) {
  const ids = new URL(value).searchParams.getAll('game');
  if (!ids.length) return null;
  if (ids.length !== 1 || !ID.test(ids[0]) || ids[0].length > 64) {
    throw new Error('Invalid game ID. Open a game from the Wiki catalog.');
  }
  return ids[0];
}

export function validateCatalog(data) {
  if (data?.schemaVersion !== 1 || !Array.isArray(data.games)) {
    throw new Error('Invalid game catalog');
  }
  const games = new Map();
  for (const game of data.games) {
    if (typeof game.id !== 'string' || !ID.test(game.id) || typeof game.title !== 'string' || !game.title.trim()
      || game.title.length > 64 || !VERSION.test(game.version) || game.ramKiB !== 16
      || !Number.isInteger(game.entry) || game.entry < 0x300 || game.entry >= 0x3000
      || game.path !== `games/${game.id}/${game.version}/${game.id}.prg`
      || !HASH.test(game.sha256) || games.has(game.id)
      || typeof game.sourceUrl !== 'string'
      || !game.sourceUrl.startsWith('https://github.com/zabaglione/jr100dev/tree/')) {
      throw new Error('Invalid game catalog entry');
    }
    games.set(game.id, {...game});
  }
  return games;
}

export async function fetchGame(id, baseUrl, fetcher = globalThis.fetch) {
  const response = await fetcher(new URL('games/catalog.json', baseUrl).href, {cache:'no-cache'});
  if (!response.ok) throw new Error(`Game catalog could not be loaded (${response.status})`);
  const game = validateCatalog(await response.json()).get(id);
  if (!game) throw new Error(`Unknown game: ${id}`);
  const artifact = await fetcher(new URL(game.path, baseUrl).href, {cache:'no-cache'});
  if (!artifact.ok) throw new Error(`Game could not be loaded (${artifact.status})`);
  const bytes = new Uint8Array(await artifact.arrayBuffer());
  if (bytes.length > 65536 || bytes.length < 8) throw new Error('Invalid game file size');
  if (!globalThis.crypto?.subtle) throw new Error('Game verification requires HTTPS or localhost');
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  const actual = [...new Uint8Array(digest)].map(n => n.toString(16).padStart(2,'0')).join('');
  if (actual !== game.sha256) throw new Error('Game hash mismatch. Reload the page to retry.');
  if (String.fromCharCode(...bytes.slice(0,4)) !== 'PROG') throw new Error('Invalid game file');
  return {...game, bytes};
}

export class GameLaunch {
  constructor(game) {
    this.game = game;
    this.state = 'waiting';
  }
  romLoaded() {
    if (this.state === 'waiting') this.state = 'booting';
  }
  frame(clockCount) {
    // Run the ROM's RAM initialization before installing program bytes.
    if (this.state !== 'booting' || clockCount < 1_490_000) return null;
    this.state = 'loading';
    return this.game;
  }
  cancel() { this.state = 'cancelled'; }
}
