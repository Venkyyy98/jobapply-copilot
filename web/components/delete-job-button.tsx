"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function DeleteJobButton({ jobId }: { jobId: number }) {
  const router = useRouter();
  const [status, setStatus] = useState("");

  async function deleteJob() {
    if (!window.confirm("Delete this tracked application and generated documents?")) return;
    const response = await fetch(`/api/jobs/${jobId}/delete`, { method: "DELETE" });
    if (response.ok) {
      setStatus("Deleted.");
      router.refresh();
    } else {
      setStatus("Could not delete this item.");
    }
  }

  return (
    <div>
      <button type="button" className="text-danger-button" onClick={deleteJob}>Delete</button>
      {status ? <span className="small-note">{status}</span> : null}
    </div>
  );
}
