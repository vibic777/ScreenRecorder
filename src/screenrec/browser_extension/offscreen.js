let active = false, recorder, stream, timer, upload = Promise.resolve(), queued = 0, sequence = 0;
let base, token, failed = null;
async function request(path, body, contentType="application/json") {
  const response = await fetch(base + path, {method:body === undefined ? "GET" : "POST",
    headers:{"X-ScreenRec-Token":token, "Content-Type":contentType}, body,
    signal:AbortSignal.timeout(10000)});
  if (!response.ok) throw new Error("Ошибка связи со ScreenRec: " + response.status);
  return response.json();
}
function stop() {
  clearInterval(timer);
  if (recorder && recorder.state !== "inactive") recorder.stop();
  else if (stream) stream.getTracks().forEach(track => track.stop());
}
async function finish() {
  clearInterval(timer);
  try {
    await upload;
    if (failed) await request("/abort", JSON.stringify({error:failed}));
    else await request("/end", "{}");
  } catch(error) {
    console.error("ScreenRec", error);
  } finally {
    stream?.getTracks().forEach(track => track.stop());
    active = false;
    chrome.runtime.sendMessage({target:"background",type:"finished"}).catch(() => {});
  }
}
async function start(message) {
  if (active) throw new Error("Уже идёт запись");
  base = message.base; token = message.token;
  failed = null; queued = 0; sequence = 0; upload = Promise.resolve();
  stream = await navigator.mediaDevices.getUserMedia({audio:false,
    video:{mandatory:{chromeMediaSource:"tab",chromeMediaSourceId:message.streamId,
                      maxFrameRate:message.config.fps}}});
  try {
    const mimeType = ["video/webm;codecs=vp9", "video/webm;codecs=vp8"].find(type => MediaRecorder.isTypeSupported(type));
    if (!mimeType) throw new Error("Браузер не поддерживает запись WebM");
    const bitrate = {high:20000000,balanced:12000000,compact:5000000}[message.config.quality];
    recorder = new MediaRecorder(stream,{mimeType, videoBitsPerSecond:bitrate});
    recorder.ondataavailable = event => {
      if (!event.data.size || failed) return;
      const chunk = event.data, number = sequence++;
      queued += chunk.size;
      if (queued > 64 * 1024 * 1024) {
        failed = "Передача видео не успевает за записью. Уменьшите качество.";
        stop(); return;
      }
      upload = upload.then(async () => {
        try {
          await request("/chunk?seq=" + number, chunk, "application/octet-stream");
        } finally { queued -= chunk.size; }
      }).catch(error => { failed = error.message; stop(); });
    };
    recorder.onstop = finish;
    recorder.onerror = event => { failed = event.error?.message || "Ошибка браузерного кодировщика"; stop(); };
    stream.getVideoTracks()[0].onended = () => stop();
    await request("/begin", JSON.stringify({title:message.title}));
    active = true;
    recorder.start(1000);
    let polling = false;
    timer = setInterval(async () => {
      if (polling) return;
      polling = true;
      try {
        const config = await request("/config");
        if (config.stop) stop();
      } catch(error) { failed = error.message; stop(); }
      finally { polling = false; }
    }, 500);
  } catch(error) {
    stream.getTracks().forEach(track => track.stop());
    try { await request("/abort", JSON.stringify({error:error.message})); } catch(_) {}
    throw error;
  }
}
chrome.runtime.onMessage.addListener((message,sender,respond) => {
  if (message.target !== "offscreen") return;
  if (message.type === "state") { respond({active}); return; }
  if (message.type === "stop") { stop(); respond({ok:active}); return; }
  if (message.type === "start") {
    start(message).then(() => respond({ok:true}), error => respond({ok:false,error:error.message}));
    return true;
  }
});
