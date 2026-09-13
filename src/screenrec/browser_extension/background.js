let creating;
async function ensureOffscreen() {
  if (await chrome.offscreen.hasDocument()) return;
  if (!creating) creating = chrome.offscreen.createDocument({
    url:"offscreen.html", reasons:["USER_MEDIA"],
    justification:"Передача выбранной вкладки в локальное приложение ScreenRec"
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
    if (!match || Number(match[1]) < 1 || Number(match[1]) > 65535) throw new Error("Неверный код подключения");
    const base = "http://127.0.0.1:" + match[1], token = match[2];
    const response = await fetch(base + "/config", {headers:{"X-ScreenRec-Token":token}, signal:AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error("Код устарел или приложение недоступно");
    const config = await response.json();
    if (!config.ready || config.stop) throw new Error("Начните новый сеанс вкладки в ScreenRec");
    await ensureOffscreen();
    const state = await chrome.runtime.sendMessage({target:"offscreen", type:"state"});
    if (state?.active) throw new Error("Уже записывается вкладка. Сначала остановите её.");
    const [tab] = await chrome.tabs.query({active:true, currentWindow:true});
    const streamId = await chrome.tabCapture.getMediaStreamId({targetTabId:tab.id});
    const result = await chrome.runtime.sendMessage({target:"offscreen", type:"start", base, token, streamId,
                                                    title:tab.title || "Вкладка", config});
    if (!result?.ok) throw new Error(result?.error || "Браузер отказал в захвате вкладки");
    return {ok:true};
  })().then(respond, error => respond({ok:false,error:error.message}));
  return true;
});
