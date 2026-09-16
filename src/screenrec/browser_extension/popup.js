const message = (key, fallback) => chrome.i18n.getMessage(key) || fallback;
const status = document.querySelector("#status");
document.querySelector("#title").textContent = message("popupTitle", "Record this tab");
document.querySelector("#hint").textContent = message("popupHint", "Select Browser tab in ScreenRec, click Start recording, and copy the connection code.");
document.querySelector("#code-label").textContent = message("popupCode", "Connection code");
document.querySelector("#code").placeholder = message("popupPlaceholder", "port:code");
document.querySelector("#start").textContent = message("popupStart", "Connect and record this tab");
document.querySelector("#stop").textContent = message("popupStop", "Stop tab recording");
document.querySelector("#start").onclick = async () => {
  status.textContent = message("popupConnecting", "Connecting…");
  try {
    const pairing = document.querySelector("#code").value.trim();
    const response = await chrome.runtime.sendMessage({target:"background", type:"start", pairing});
    if (!response?.ok) throw new Error(response?.error || message("popupConnectError", "Could not connect"));
    status.textContent = message("popupStarted", "Recording started. You can switch to other tabs.");
  } catch(error) { status.textContent = error.message; }
};
document.querySelector("#stop").onclick = async () => {
  const response = await chrome.runtime.sendMessage({target:"offscreen", type:"stop"});
  status.textContent = response?.ok ? message("popupStopping", "Stopping recording…") : message("popupNoActive", "No active recording");
};