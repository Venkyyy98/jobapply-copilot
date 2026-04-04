"use client";

import { useState } from "react";

type Props = {
  jobId: number;
};

const ACTIONS = [
  { action: "SAVED", label: "Save" },
  { action: "ANALYZED", label: "Analyze" },
  { action: "GENERATED_DOCS", label: "Generate docs" },
  { action: "OUTREACH_STARTED", label: "Open outreach" },
  { action: "APPLIED", label: "Mark applied" }
] as const;

export function JobActionBar({ jobId }: Props) {
  const [status, setStatus] = useState("");

  async function trigger(action: string) {
    setStatus("Saving action...");
    const response = await fetch(`/api/jobs/${jobId}/action`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ action })
    });
    if (!response.ok) {
      const message = await response.text();
      setStatus(message || "Action failed.");
      return;
    }
    setStatus(`${action.toLowerCase()} recorded.`);
  }

  return (
    <div className="action-bar">
      <div className="action-button-row">
        {ACTIONS.map((item) => (
          <button key={item.action} type="button" className="secondary-button" onClick={() => void trigger(item.action)}>
            {item.label}
          </button>
        ))}
      </div>
      {status ? <p className="inline-status">{status}</p> : null}
    </div>
  );
}
