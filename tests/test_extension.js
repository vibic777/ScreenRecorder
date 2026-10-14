// Run with node tests/test_extension.js (no npm dependencies).
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
let rejectMedia;
let listener;
let attempts = 0;
const context = vm.createContext({
  chrome: {i18n: {getMessage: () => ""}, runtime: {onMessage: {addListener: fn => { listener = fn; }}}},
  navigator: {mediaDevices: {getUserMedia: () => {
    attempts++;
    return new Promise((resolve, reject) => { rejectMedia = reject; });
  }}},
  AbortSignal, clearInterval, console,
  fetch: async () => ({ok: true, json: async () => ({})}),
});
vm.runInContext(fs.readFileSync("src/screenrec/browser_extension/offscreen.js", "utf8"), context);
const start = vm.runInContext("start", context);
const message = {base: "http://127.0.0.1:12345", token: "test", streamId: "id", config: {fps: 30}};
(async () => {
  const first = start(message);
  const failed = assert.rejects(first, /device unavailable/);
  await assert.rejects(start(message), /already active/);
  assert.equal(attempts, 1);
  rejectMedia(new Error("device unavailable"));
  await failed;
  let active;
  listener({target: "offscreen", type: "state"}, {}, state => { active = state.active; });
  assert.equal(active, false);
  const retry = start(message);
  const retried = assert.rejects(retry, /permission denied/);
  rejectMedia(new Error("permission denied"));
  await retried;
  assert.equal(attempts, 2);
  console.log("Extension startup concurrency and failure recovery passed");
})().catch(error => { console.error(error); process.exitCode = 1; });
