const DEFAULT_API_BASE = "http://127.0.0.1:8787";

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
  const [localConfig, sessionConfig] = await Promise.all([
    chrome.storage.local.get({
      apiBaseUrl: DEFAULT_API_BASE,
      extensionToken: "",
      jacToken: "",
      openaiApiKey: "",
      profile: {}
    }),
    chrome.storage.session?.get({ openaiApiKey: "" }).catch(() => ({ openaiApiKey: "" })) || Promise.resolve({ openaiApiKey: "" }),
  ]);
  return {
    ...localConfig,
    openaiApiKey: sessionConfig.openaiApiKey || localConfig.openaiApiKey || "",
  };
}

function normalizeApiBase(value) {
  return String(value || DEFAULT_API_BASE).replace(/\/+$/, "");
}

const AI_REQUEST_PATHS = new Set(["/analyze_job", "/generate_docs", "/company_issue", "/referral_drafts", "/ai/test_key"]);

function buildAuthHeaders(config, includeOpenAiKey = false) {
  const headers = { "Content-Type": "application/json" };
  if (config.extensionToken) {
    headers.Authorization = `Bearer ${config.extensionToken}`;
  } else if (config.jacToken) {
    headers["X-JAC-TOKEN"] = config.jacToken;
  }
  if (includeOpenAiKey && config.openaiApiKey) {
    headers["X-OpenAI-API-Key"] = config.openaiApiKey;
  }
  return headers;
}

async function apiRequest(path, method = "GET", body = null) {
  const config = await getConfig();
  const apiBase = normalizeApiBase(config.apiBaseUrl);
  const headers = buildAuthHeaders(config, AI_REQUEST_PATHS.has(path));
  const controller = new AbortController();
  const longRunning = new Set(["/analyze_job", "/generate_docs", "/referral_drafts", "/find_targets"]);
  const timeoutMs = longRunning.has(path) ? 90000 : 30000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const res = await fetch(`${apiBase}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    signal: controller.signal,
  }).catch((err) => {
    if (err?.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.floor(timeoutMs / 1000)}s: ${path}`);
    }
    throw new Error(
      `Cannot reach JobApply Copilot API at ${apiBase}. Check the extension Options page.`
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
        const config = await getConfig();
        const apiBase = normalizeApiBase(config.apiBaseUrl);
        const url = `${apiBase}${message.path}`;
        const authHeaders = [];
        if (config.extensionToken) {
          authHeaders.push({ name: "Authorization", value: `Bearer ${config.extensionToken}` });
        } else if (config.jacToken) {
          authHeaders.push({ name: "X-JAC-TOKEN", value: config.jacToken });
        }
        const options = {
          url,
          headers: authHeaders,
          saveAs: Boolean(message.saveAs)
        };
        if (!String(message.path || "").startsWith("/download/") && message.filename) {
          options.filename = message.filename;
        }
        await chrome.downloads.download(options);
        sendResponse({ ok: true });
        return;
      }

      if (message.type === "download_many") {
        const config = await getConfig();
        const apiBase = normalizeApiBase(config.apiBaseUrl);
        const authHeaders = [];
        if (config.extensionToken) {
          authHeaders.push({ name: "Authorization", value: `Bearer ${config.extensionToken}` });
        } else if (config.jacToken) {
          authHeaders.push({ name: "X-JAC-TOKEN", value: config.jacToken });
        }
        const downloads = message.downloads || [];
        for (const item of downloads) {
          const options = {
            url: `${apiBase}${item.path}`,
            headers: authHeaders,
            saveAs: false
          };
          if (!String(item.path || "").startsWith("/download/") && item.filename) {
            options.filename = item.filename;
          }
          await chrome.downloads.download(options);
        }
        sendResponse({ ok: true });
        return;
      }

      if (message.type === "fetch_text_file") {
        const config = await getConfig();
        const apiBase = normalizeApiBase(config.apiBaseUrl);
        const res = await fetch(`${apiBase}${message.path}`, {
          method: "GET",
          headers: buildAuthHeaders(config, false)
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
