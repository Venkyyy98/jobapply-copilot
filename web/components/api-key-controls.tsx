"use client";

import { useEffect, useState } from "react";

const SESSION_KEY = "jobapply.openaiApiKey";
const LOCAL_KEY = "jobapply.openaiApiKey.remembered";

export function ApiKeyControls() {
  const [apiKey, setApiKey] = useState("");
  const [remember, setRemember] = useState(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    const remembered = window.localStorage.getItem(LOCAL_KEY) || "";
    const session = window.sessionStorage.getItem(SESSION_KEY) || "";
    setApiKey(session || remembered);
    setRemember(Boolean(remembered));
  }, []);

  function saveKey(nextKey = apiKey, persist = remember) {
    if (persist) {
      window.localStorage.setItem(LOCAL_KEY, nextKey);
      window.sessionStorage.removeItem(SESSION_KEY);
    } else {
      window.sessionStorage.setItem(SESSION_KEY, nextKey);
      window.localStorage.removeItem(LOCAL_KEY);
    }
  }

  async function testKey() {
    if (!apiKey.trim()) {
      setStatus("Paste an API key before testing.");
      return;
    }
    saveKey();
    setStatus("Testing key...");
    const response = await fetch("/api/ai-key/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ apiKey })
    });
    const data = await response.json().catch(() => ({}));
    setStatus(response.ok ? data.message || "API key works." : data.detail || "API key test failed.");
  }

  function removeKey() {
    window.sessionStorage.removeItem(SESSION_KEY);
    window.localStorage.removeItem(LOCAL_KEY);
    setApiKey("");
    setRemember(false);
    setStatus("API key removed from this browser.");
  }

  return (
    <section className="panel api-key-panel">
      <p className="eyebrow">Bring your own key</p>
      <h2>Use your OpenAI key for AI requests</h2>
      <p className="muted">
        Stored in this browser session by default and sent only when an AI request needs it. Remembering the key stores it on this device.
      </p>
      <label>
        OpenAI API key
        <input
          type="password"
          value={apiKey}
          placeholder="sk-..."
          onChange={(event) => setApiKey(event.target.value)}
          onBlur={() => saveKey()}
        />
      </label>
      <label className="check-row">
        <input
          type="checkbox"
          checked={remember}
          onChange={(event) => {
            const next = event.target.checked;
            setRemember(next);
            saveKey(apiKey, next);
          }}
        />
        Remember key on this device
      </label>
      <div className="pill-row">
        <button type="button" className="primary-button" onClick={testKey}>Test API Key</button>
        <button type="button" className="ghost-button" onClick={removeKey}>Remove API Key</button>
      </div>
      {status ? <p className="small-note">{status}</p> : null}
    </section>
  );
}
