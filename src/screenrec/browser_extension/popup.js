const status = document.querySelector("#status");
document.querySelector("#start").onclick = async () => {
  status.textContent = "Подключение…";
  try {
    const pairing = document.querySelector("#code").value.trim();
    const response = await chrome.runtime.sendMessage({target:"background", type:"start", pairing});
    if (!response?.ok) throw new Error(response?.error || "Не удалось подключиться");
    status.textContent = "Запись началась. Можно переключаться на другие вкладки.";
  } catch(error) { status.textContent = error.message; }
};
document.querySelector("#stop").onclick = async () => {
  const response = await chrome.runtime.sendMessage({target:"offscreen", type:"stop"});
  status.textContent = response?.ok ? "Завершение записи…" : "Нет активной записи";
};
