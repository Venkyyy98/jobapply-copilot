const API_BASE = "http://127.0.0.1:8787";

async function configureSidePanelBehavior() {
  if (chrome.sidePanel?.setPanelBehavior) {
    await chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
  }
}

chrome.runtime.onInstalled.addListener(async () => {
  await configureSidePanelBehavior();
});

chrome.runtime.onStartup.addListener(async () => {
  await configureSidePanelBehavior();
});

configureSidePanelBehavior().catch(() => {});

async function getConfig() {
  return chrome.storage.local.get({ jacToken: "", profile: {} });
}

async function apiRequest(path, method = "GET", body = null) {
  const { jacToken } = await getConfig();
  const headers = { "Content-Type": "application/json", "X-JAC-TOKEN": jacToken || "" };
  const controller = new AbortController();
  const longRunning = new Set(["/analyze_job", "/generate_docs", "/referral_drafts", "/find_targets"]);
  const timeoutMs = longRunning.has(path) ? 90000 : 30000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    signal: controller.signal,
  }).catch((err) => {
    if (err?.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.floor(timeoutMs / 1000)}s: ${path}`);
    }
    throw new Error(
      "Cannot reach local server at http://127.0.0.1:8787. Start it with: ./scripts/setup_and_run_server.sh"
    );
  }).finally(() => {
    clearTimeout(timer);
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed: ${res.status}`);
  }
  return data;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    try {
      if (message.type === "api_request") {
        const data = await apiRequest(message.path, message.method, message.body);
        sendResponse({ ok: true, data });
        return;
      }

      if (message.type === "download_file") {
        const { jacToken } = await getConfig();
        const url = `${API_BASE}${message.path}`;
        const filename = message.filename || "download.pdf";
        await chrome.downloads.download({
          url,
          filename,
          headers: [{ name: "X-JAC-TOKEN", value: jacToken || "" }],
          saveAs: Boolean(message.saveAs)
        });
        sendResponse({ ok: true });
        return;
      }

      if (message.type === "download_many") {
        const { jacToken } = await getConfig();
        const downloads = message.downloads || [];
        for (const item of downloads) {
          await chrome.downloads.download({
            url: `${API_BASE}${item.path}`,
            filename: item.filename || "download.pdf",
            headers: [{ name: "X-JAC-TOKEN", value: jacToken || "" }],
            saveAs: false
          });
        }
        sendResponse({ ok: true });
        return;
      }

      if (message.type === "fetch_text_file") {
        const { jacToken } = await getConfig();
        const res = await fetch(`${API_BASE}${message.path}`, {
          method: "GET",
          headers: { "X-JAC-TOKEN": jacToken || "" }
        });
        if (!res.ok) {
          throw new Error(`Text fetch failed: ${res.status}`);
        }
        const text = await res.text();
        sendResponse({ ok: true, text });
        return;
      }

      sendResponse({ ok: false, error: "Unknown message type" });
    } catch (error) {
      sendResponse({ ok: false, error: error.message || String(error) });
    }
  })();

  return true;
});
