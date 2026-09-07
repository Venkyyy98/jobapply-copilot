"use client";

import { useState } from "react";

type TokenResponse = {
  token: string;
  api_base_url: string;
  created_at: string;
};

type ExtensionTokenPanelProps = {
  disabled?: boolean;
  disabledReason?: string;
};

export function ExtensionTokenPanel({ disabled = false, disabledReason = "" }: ExtensionTokenPanelProps) {
  const [token, setToken] = useState<TokenResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function issueToken() {
    if (disabled) {
      setError(disabledReason || "Complete your beta profile before creating an extension token.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/extension-token", { method: "POST" });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(body.detail || "Could not create extension token.");
      }
      setToken(body as TokenResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create extension token.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <h2>Connect Chrome extension</h2>
      <p className="muted">Create a beta access token, then paste the API base URL and token into the extension Options page.</p>
      {disabled && disabledReason ? <p className="warning">{disabledReason}</p> : null}
      <button type="button" className="primary-button" onClick={issueToken} disabled={loading || disabled}>
        {loading ? "Creating..." : "Create extension token"}
      </button>
      {error ? <p className="warning">{error}</p> : null}
      {token ? (
        <div className="token-box">
          <label>
            API base URL
            <input readOnly value={token.api_base_url} />
          </label>
          <label>
            Extension token
            <textarea readOnly rows={3} value={token.token} />
          </label>
          <p className="small-note">This token is shown once. Create a new one if you need to reconnect the extension.</p>
        </div>
      ) : null}
    </section>
  );
}
