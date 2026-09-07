import Link from "next/link";

import { JobActionBar } from "@/components/job-action-bar";
import { fetchPublicJob } from "@/lib/api";

function hasValidSourceUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export default async function JobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const job = await fetchPublicJob(id);
  const hasDetailedEvidence =
    job.keyword_coverage_pct > 0 ||
    job.matched_keywords.length > 0 ||
    job.suggested_bullets.length > 0 ||
    job.suggested_project_ids.length > 0;

  return (
    <>
      <div className="detail-card detail-hero">
        <div>
          <p className="eyebrow">{job.role_family}</p>
          <h1>{job.title}</h1>
          <p className="muted">
            {job.company}
            {job.location ? ` · ${job.location}` : ""}
            {job.work_mode !== "Unknown" ? ` · ${job.work_mode}` : ""}
          </p>
        </div>
        <div className="score-pill">
          <span>Fit score</span>
          <strong>{job.fit_score ?? "--"}</strong>
        </div>
      </div>
      <p className="small-note" style={{ marginTop: 12 }}>
        Fit score is calculated by JobApply Copilot during analysis from parsed job requirements, matched profile skills, keyword coverage, and optional AI review. Re-analyze the posting after profile changes to refresh this score.
      </p>

      <div className="detail-columns" style={{ marginTop: 20 }}>
        <section className="detail-card">
          <h2>Fit and tailoring</h2>
          <p>{job.summary || job.job_text_excerpt}</p>
          <div className="section-head">
            <h3>{hasDetailedEvidence ? "Why it matches" : "Analysis status"}</h3>
          </div>
          {hasDetailedEvidence ? (
            <ul className="list-card">
              {job.fit_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
              {!job.fit_reasons.length ? <li>No fit reasons were synced for this role.</li> : null}
            </ul>
          ) : (
            <p className="small-note">
              Detailed fit evidence is not available for this saved feed item. Re-analyze the original posting with your current profile to refresh the title, company, source link, keyword coverage, and tailoring notes.
            </p>
          )}
          <div className="section-head">
            <h3>Tailoring plan</h3>
          </div>
          <ul className="list-card">
            {job.tailoring_plan.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>

        <aside className="detail-card">
          <h2>Anonymous activity</h2>
          <div className="stats-grid">
            <div className="stat-card">
              <p>Saved</p>
              <strong>{job.aggregate_counts.saved}</strong>
            </div>
            <div className="stat-card">
              <p>Analyzed</p>
              <strong>{job.aggregate_counts.analyzed}</strong>
            </div>
            <div className="stat-card">
              <p>Docs</p>
              <strong>{job.aggregate_counts.generated_docs}</strong>
            </div>
            <div className="stat-card">
              <p>Applied</p>
              <strong>{job.aggregate_counts.applied}</strong>
            </div>
            <div className="stat-card">
              <p>Outreach</p>
              <strong>{job.aggregate_counts.outreach_started}</strong>
            </div>
          </div>
          <div className="section-head">
            <h3>Keyword coverage</h3>
          </div>
          <div className="chip-row">
            {job.matched_keywords.map((item) => (
              <span className="chip" key={item}>
                {item}
              </span>
            ))}
            {!job.matched_keywords.length ? <span className="muted">No synced keyword coverage yet.</span> : null}
          </div>
          <div className="section-head">
            <h3>Missing keywords</h3>
          </div>
          <div className="chip-row">
            {job.missing_keywords.map((item) => (
              <span className="pill" key={item}>
                {item}
              </span>
            ))}
          </div>
          <div className="section-head">
            <h3>Workspace actions</h3>
          </div>
          <p className="small-note">
            These actions update your signed-in workspace. Final generation and browser autofill still happen through the extension.
          </p>
          <JobActionBar jobId={job.id} />
          <div className="section-head">
            <Link href="/app" className="inline-link">
              Open private workspace
            </Link>
            {hasValidSourceUrl(job.source_url) ? (
              <a href={job.source_url} target="_blank" rel="noreferrer" className="inline-link">
                Open posting
              </a>
            ) : (
              <span className="muted">Source unavailable</span>
            )}
          </div>
        </aside>
      </div>
    </>
  );
}
