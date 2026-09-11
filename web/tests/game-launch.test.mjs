import test from 'node:test';
import assert from 'node:assert/strict';
import { gameIdFromUrl, validateCatalog, fetchGame, GameLaunch } from '../game-launch.js';
const entry = { id:'chrono-breach', title:'CHRONO BREACH', version:'1.0.0', ramKiB:16,
  entry:768, path:'games/chrono-breach/1.0.0/chrono-breach.prg', sha256:'a'.repeat(64),
  sourceUrl:'https://github.com/zabaglione/jr100dev/tree/main/games/chrono_breach' };
const catalog = (game=entry) => ({schemaVersion:1,games:[game]});
test('only a single catalog ID is accepted', () => {
  assert.equal(gameIdFromUrl('https://example.test/'),null);
  assert.equal(gameIdFromUrl('https://example.test/?game=chrono-breach'),'chrono-breach');
  for(const suffix of ['?game=', '?game=../rom', '?game=https://x.test', '?game=x&game=y'])
    assert.throws(()=>gameIdFromUrl('https://example.test/'+suffix));
});
test('catalog constrains memory, entry, source and artifact paths', () => {
  assert.equal(validateCatalog(catalog()).get('chrono-breach').ramKiB,16);
  for(const patch of [{ramKiB:32},{entry:0x4000},{path:'../bad.prg'},
    {path:'https://remote.test/p.prg'},{sha256:'bad'},{sourceUrl:'javascript:alert(1)'},
    {version:'../1'},{title:''}]) assert.throws(()=>validateCatalog(catalog({...entry,...patch})));
  assert.throws(()=>validateCatalog({schemaVersion:1,games:[entry,entry]}));
});
test('fetch failures and hash mismatches prevent launch', async () => {
  const bytes = new TextEncoder().encode('PROGtest');
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256',bytes));
  const hash = [...digest].map(n=>n.toString(16).padStart(2,'0')).join('');
  const good = {...entry,sha256:hash};
  const fetcher = async url => url.endsWith('catalog.json')
    ? {ok:true,json:async()=>catalog(good)} : {ok:true,arrayBuffer:async()=>bytes.buffer};
  const game = await fetchGame('chrono-breach',new URL('https://example.test/app/'),fetcher);
  assert.deepEqual(game.bytes,bytes);
  await assert.rejects(fetchGame('unknown',new URL('https://example.test/'),fetcher),/Unknown/);
  await assert.rejects(fetchGame('chrono-breach',new URL('https://example.test/'),async()=>({ok:false,status:404})),/404/);
  const bad = async url => url.endsWith('catalog.json')
    ? {ok:true,json:async()=>catalog()} : {ok:true,arrayBuffer:async()=>bytes.buffer};
  await assert.rejects(fetchGame('chrono-breach',new URL('https://example.test/'),bad),/hash/);
});
test('saved ROM boot precedes one and only one program load', () => {
  const launch=new GameLaunch({...entry,bytes:new Uint8Array([1])});
  assert.equal(launch.frame(2_000_000),null);
  launch.romLoaded();
  assert.equal(launch.frame(0),null);
  assert.equal(launch.frame(1_000_000),null);
  assert.equal(launch.frame(1_490_000).id,'chrono-breach');
  assert.equal(launch.frame(2_000_000),null);
  launch.romLoaded();
  assert.equal(launch.frame(3_000_000),null);
});
