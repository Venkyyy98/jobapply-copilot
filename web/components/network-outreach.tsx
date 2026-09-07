"use client";

import { useMemo, useState } from "react";

import type { ReferralDraft, TargetContact } from "@/lib/types";

const GROUPS = [
  { key: "previous_company", title: "From Your Previous Company", className: "previous-company" },
  { key: "school", title: "From Your School", className: "school" },
  { key: "beyond_network", title: "Beyond Your Network", className: "beyond-network" }
] as const;

export function NetworkOutreach({ jobId, role, company }: { jobId: number; role: string; company: string }) {
  const [contacts, setContacts] = useState<TargetContact[]>([]);
  const [draft, setDraft] = useState<ReferralDraft | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const grouped = useMemo(
    () => GROUPS.map((group) => ({
      ...group,
      contacts: contacts.filter((contact) => (contact.relationship_type || "beyond_network") === group.key)
    })),
    [contacts]
  );

  async function findContacts() {
    setLoading(true);
    setDraft(null);
    setMessage("Searching public LinkedIn results for shared employers and schools...");
    try {
      const response = await fetch("/api/outreach/find-targets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Could not find contacts.");
      setContacts(payload.contacts || []);
      setMessage((payload.contacts || []).length
        ? `Found ${(payload.contacts || []).length} possible contacts.`
        : (payload.warnings || [])[0] || "No public contacts found.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not find contacts.");
    } finally {
      setLoading(false);
    }
  }

  async function generateDraft(contact: TargetContact) {
    setLoading(true);
    setMessage(`Drafting outreach for ${contact.name || "this contact"}...`);
    try {
      const response = await fetch("/api/outreach/referral-drafts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId, contacts: [contact] })
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || "Could not generate outreach.");
      setDraft((payload.drafts || [])[0] || null);
      setMessage("LinkedIn note and referral email are ready.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not generate outreach.");
    } finally {
      setLoading(false);
    }
  }

  function copy(text: string) {
    void navigator.clipboard.writeText(text);
    setMessage("Copied to clipboard.");
  }

  return (
    <section className="panel network-outreach-panel">
      <div className="section-head compact">
        <div>
          <p className="eyebrow">LinkedIn common ground</p>
          <h2>Find a warmer path into {company}</h2>
          <p className="muted">
            Check public results for people who share one of your previous companies or schools, then draft a personalized note and email.
          </p>
        </div>
        <button className="primary-button" type="button" onClick={findContacts} disabled={loading}>
          {loading ? "Working..." : contacts.length ? "Refresh connections" : "Find connections"}
        </button>
      </div>

      {message ? <p className="network-status">{message}</p> : null}

      {contacts.length ? (
        <div className="network-card-grid">
          {grouped.map((group) => (
            <article className={`network-card ${group.className}`} key={group.key}>
              <div className="network-card-title">
                <h3>{group.title}</h3>
                <span>{group.contacts.length}</span>
              </div>
              {group.contacts.length ? group.contacts.slice(0, 5).map((contact) => (
                <div className="network-person" key={contact.linkedin_url || contact.name}>
                  <span className="network-person-avatar">{(contact.name || "?").charAt(0).toUpperCase()}</span>
                  <div>
                    <strong>{contact.name || "LinkedIn contact"}</strong>
                    <small>{contact.shared_context || contact.title || "Potential company contact"}</small>
                  </div>
                  <div className="network-person-actions">
                    {contact.linkedin_url ? <a href={contact.linkedin_url} target="_blank" rel="noreferrer">View</a> : null}
                    <button type="button" onClick={() => generateDraft(contact)} disabled={loading}>Draft</button>
                  </div>
                </div>
              )) : <p className="muted">No matches in this group yet.</p>}
            </article>
          ))}
        </div>
      ) : null}

      {draft ? (
        <div className="outreach-draft-grid">
          <article className="outreach-draft">
            <div className="network-card-title">
              <h3>LinkedIn note</h3>
              <button type="button" onClick={() => copy(draft.linkedin_note)}>Copy</button>
            </div>
            <p>{draft.linkedin_note}</p>
          </article>
          <article className="outreach-draft">
            <div className="network-card-title">
              <h3>Referral email</h3>
              <button type="button" onClick={() => copy(`Subject: ${draft.email_subject}\n\n${draft.email_body}`)}>Copy</button>
            </div>
            <strong>{draft.email_subject}</strong>
            <pre>{draft.email_body}</pre>
            <a
              className="secondary-button"
              href={`mailto:${encodeURIComponent(draft.email || "")}?subject=${encodeURIComponent(draft.email_subject)}&body=${encodeURIComponent(draft.email_body)}`}
            >
              Open email draft
            </a>
          </article>
        </div>
      ) : null}
      <p className="muted network-disclaimer">
        Results come from public search snippets. Review the person’s LinkedIn profile before sending any message.
      </p>
    </section>
  );
}
