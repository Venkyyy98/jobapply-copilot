"use client";

import { useState } from "react";

export function DeleteDataButton() {
  const [status, setStatus] = useState("");

  async function deleteData() {
    const confirmed = window.confirm("Delete your beta profile, tokens, jobs, generated output records, and actions?");
    if (!confirmed) return;
    const response = await fetch("/api/me", { method: "DELETE" });
    setStatus(response.ok ? "Your beta tracker data has been deleted." : "Could not delete data. Please try again.");
  }

  return (
    <div>
      <button type="button" className="ghost-button" onClick={deleteData}>Delete my beta data</button>
      {status ? <p className="small-note">{status}</p> : null}
    </div>
  );
}
