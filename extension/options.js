function getInput(id) {
  return document.getElementById(id);
}

function getValue(id) {
  return getInput(id)?.value.trim() || "";
}

function setValue(id, value) {
  const input = getInput(id);
  if (input) input.value = value || "";
}

async function loadSettings() {
  const stored = await chrome.storage.local.get({
    apiBaseUrl: "https://jobapply-copilot-api.onrender.com",
    websiteUrl: "https://jobapply-copilot-web.onrender.com/app/jobs",
    extensionToken: "",
    jacToken: "",
    openaiApiKey: "",
    rememberOpenAiKey: false
  });
  const sessionStored =
    (await chrome.storage.session?.get({ openaiApiKey: "" }).catch(() => ({ openaiApiKey: "" }))) || {
      openaiApiKey: ""
    };

  setValue("apiBaseUrl", stored.apiBaseUrl);
  setValue("websiteUrl", stored.websiteUrl);
  setValue("extensionToken", stored.extensionToken);
  setValue("jacToken", stored.jacToken);
  setValue("openaiApiKey", sessionStored.openaiApiKey || stored.openaiApiKey || "");
  const remember = getInput("rememberOpenAiKey");
  if (remember) remember.checked = Boolean(stored.rememberOpenAiKey);
}

async function saveSettings() {
  const openaiApiKey = getValue("openaiApiKey");
  const rememberOpenAiKey = Boolean(getInput("rememberOpenAiKey")?.checked);
  const localPayload = {
    apiBaseUrl: getValue("apiBaseUrl") || "https://jobapply-copilot-api.onrender.com",
    websiteUrl: getValue("websiteUrl") || "https://jobapply-copilot-web.onrender.com/app/jobs",
    extensionToken: getValue("extensionToken"),
    jacToken: getValue("jacToken"),
    rememberOpenAiKey
  };

  if (rememberOpenAiKey) {
    localPayload.openaiApiKey = openaiApiKey;
    await chrome.storage.session?.remove("openaiApiKey").catch(() => {});
  } else {
    localPayload.openaiApiKey = "";
    await chrome.storage.session?.set({ openaiApiKey }).catch(() => {});
  }

  await chrome.storage.local.set(localPayload);
  document.getElementById("status").textContent = "Saved.";
}

document.getElementById("saveBtn").addEventListener("click", saveSettings);
document.getElementById("removeOpenAiKeyBtn").addEventListener("click", async () => {
  setValue("openaiApiKey", "");
  const remember = getInput("rememberOpenAiKey");
  if (remember) remember.checked = false;
  await chrome.storage.local.set({ openaiApiKey: "", rememberOpenAiKey: false });
  await chrome.storage.session?.remove("openaiApiKey").catch(() => {});
  document.getElementById("status").textContent = "API key removed from this extension.";
});
document.getElementById("testOpenAiKeyBtn").addEventListener("click", async () => {
  const key = getValue("openaiApiKey");
  if (!key) {
    document.getElementById("status").textContent = "Paste an API key before testing.";
    return;
  }
  const apiBase = (getValue("apiBaseUrl") || "https://jobapply-copilot-api.onrender.com").replace(/\/+$/, "");
  try {
    const res = await fetch(`${apiBase}/ai/test_key`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-OpenAI-API-Key": key
      }
    });
    const data = await res.json().catch(() => ({}));
    document.getElementById("status").textContent = res.ok ? data.message || "API key works." : data.detail || "API key test failed.";
  } catch {
    document.getElementById("status").textContent = "Could not reach the API server to test the key.";
  }
});

loadSettings();
