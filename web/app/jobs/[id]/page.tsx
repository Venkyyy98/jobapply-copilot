import Link from "next/link";

import { JobActionBar } from "@/components/job-action-bar";
import { fetchPublicJob } from "@/lib/api";

export default async function JobDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const job = await fetchPublicJob(id);

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

      <div className="detail-columns" style={{ marginTop: 20 }}>
        <section className="detail-card">
          <h2>Fit and tailoring</h2>
          <p>{job.summary || job.job_text_excerpt}</p>
          <div className="section-head">
            <h3>Why it matches</h3>
          </div>
          <ul className="list-card">
            {job.fit_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
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
            <a href={job.source_url} target="_blank" rel="noreferrer" className="inline-link">
              Open posting
            </a>
          </div>
        </aside>
      </div>
    </>
  );
}
