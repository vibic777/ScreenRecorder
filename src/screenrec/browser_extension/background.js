const msg = (key, fallback) => chrome.i18n.getMessage(key) || fallback;
let creating;
async function ensureOffscreen() {
  if (await chrome.offscreen.hasDocument()) return;
  if (!creating) creating = chrome.offscreen.createDocument({
    url:"offscreen.html", reasons:["USER_MEDIA"],
    justification:msg("bridgeJustification", "Transfer selected tab locally to ScreenRec")
  }).finally(() => { creating = null; });
  await creating;
}
chrome.runtime.onMessage.addListener((message, sender, respond) => {
  if (message.target !== "background") return;
  if (message.type === "finished") {
    chrome.offscreen.closeDocument().catch(() => {});
    return;
  }
  if (message.type !== "start") return;
  (async () => {
    const match = /^(\d{1,5}):([A-Za-z0-9_-]{32,128})$/.exec(message.pairing || "");
    if (!match || Number(match[1]) < 1 || Number(match[1]) > 65535) throw new Error(msg("invalidPairing", "Invalid connection code"));
    const base = "http://127.0.0.1:" + match[1], token = match[2];
    const response = await fetch(base + "/config", {headers:{"X-ScreenRec-Token":token}, signal:AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error(msg("stalePairing", "Code expired or app unavailable"));
    const config = await response.json();
    if (!config.ready || config.stop) throw new Error(msg("startTabSession", "Start a new tab session in ScreenRec"));
    await ensureOffscreen();
    const state = await chrome.runtime.sendMessage({target:"offscreen", type:"state"});
    if (state?.active) throw new Error(msg("tabAlreadyRecording", "This tab is already being recorded. Stop it first."));
    const [tab] = await chrome.tabs.query({active:true, currentWindow:true});
    const streamId = await chrome.tabCapture.getMediaStreamId({targetTabId:tab.id});
    const result = await chrome.runtime.sendMessage({target:"offscreen", type:"start", base, token, streamId,
                                                    title:tab.title || msg("tabDefault", "Tab"), config});
    if (!result?.ok) throw new Error(result?.error || msg("captureDenied", "The browser denied tab capture"));
    return {ok:true};
  })().then(respond, error => respond({ok:false,error:error.message}));
  return true;
});
