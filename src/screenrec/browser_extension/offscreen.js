const msg = (key, fallback) => chrome.i18n.getMessage(key) || fallback;
let active = false, recorder, stream, timer, upload = Promise.resolve(), queued = 0, sequence = 0;
let base, token, failed = null, cancelled = false;
async function request(path, body, contentType="application/json", extraHeaders={}) {
  const response = await fetch(base + path, {method:body === undefined ? "GET" : "POST",
    headers:{"X-ScreenRec-Token":token, "Content-Type":contentType, ...extraHeaders}, body,
    signal:AbortSignal.timeout(10000)});
  if (!response.ok) throw new Error(msg("bridgeError", "ScreenRec connection error: ") + response.status);
  return response.json();
}
async function uploadChunk(chunk, sequenceNumber) {
  const partSize = 8 * 1024 * 1024;
  for (let offset = 0; offset < chunk.size; offset += partSize) {
    await request("/chunk?seq=" + sequenceNumber + "&part=" + offset,
      chunk.slice(offset, Math.min(offset + partSize, chunk.size)), "application/octet-stream",
      {"X-Chunk-Size": String(chunk.size)});
  }
}
function stop() {
  cancelled = true;
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
  if (active) throw new Error(msg("alreadyRecording", "Recording is already active"));
  active = true;
  cancelled = false;
  base = message.base; token = message.token;
  failed = null; queued = 0; sequence = 0; upload = Promise.resolve();
  stream = null; recorder = null;
  try {
    stream = await navigator.mediaDevices.getUserMedia({audio:false,
      video:{mandatory:{chromeMediaSource:"tab",chromeMediaSourceId:message.streamId,
                        maxFrameRate:message.config.fps}}});
    if (cancelled) throw new Error(msg("popupNoActive", "No active recording"));
    const mimeType = ["video/webm;codecs=vp9", "video/webm;codecs=vp8"].find(type => MediaRecorder.isTypeSupported(type));
    if (!mimeType) throw new Error(msg("webmUnsupported", "The browser does not support WebM recording"));
    const bitrate = {high:20000000,balanced:12000000,compact:5000000}[message.config.quality];
    recorder = new MediaRecorder(stream,{mimeType, videoBitsPerSecond:bitrate});
    recorder.ondataavailable = event => {
      if (!event.data.size || failed) return;
      const chunk = event.data, number = sequence++;
      queued += chunk.size;
      if (queued > 32 * 1024 * 1024) {
        failed = msg("uploadBehind", "Video transfer is falling behind. Reduce quality.");
        stop(); return;
      }
      upload = upload.then(async () => {
        try {
          await uploadChunk(chunk, number);
        } finally { queued -= chunk.size; }
      }).catch(error => { failed = error.message; stop(); });
    };
    recorder.onstop = finish;
    recorder.onerror = event => { failed = event.error?.message || msg("encoderError", "Browser encoder error"); stop(); };
    stream.getVideoTracks()[0].onended = () => stop();
    await request("/begin", JSON.stringify({title:message.title}));
    if (cancelled) throw new Error(msg("popupNoActive", "No active recording"));
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
    active = false;
    stream?.getTracks().forEach(track => track.stop());
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
