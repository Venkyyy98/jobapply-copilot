import Link from "next/link";

import type { PublicJobFeedItem } from "@/lib/types";

function countLabel(value: number, label: string) {
  return `${value} ${label}`;
}

export function JobCard({ job, workspace = false }: { job: PublicJobFeedItem; workspace?: boolean }) {
  return (
    <article className="job-card">
      <div className="job-card-top">
        <div>
          <p className="eyebrow">{job.role_family}</p>
          <h3>{job.title}</h3>
          <p className="muted">
            {job.company}
            {job.location ? ` · ${job.location}` : ""}
          </p>
        </div>
        <div className="score-pill">
          <span>Fit</span>
          <strong>{job.fit_score ?? "--"}</strong>
        </div>
      </div>
      <p className="job-summary">{job.summary || job.job_text_excerpt || "No summary synced yet."}</p>
      <div className="chip-row">
        <span className="chip">{job.work_mode}</span>
        <span className="chip">{countLabel(job.aggregate_counts.saved, "saved")}</span>
        <span className="chip">{countLabel(job.aggregate_counts.analyzed, "analyzed")}</span>
        <span className="chip">{countLabel(job.aggregate_counts.applied, "applied")}</span>
      </div>
      <div className="job-card-footer">
        <Link href={`/jobs/${job.id}`} className="inline-link">
          View details
        </Link>
        {workspace ? (
          <Link href={`/app/jobs?job=${job.id}`} className="inline-link">
            Open in workspace
          </Link>
        ) : (
          <a href={job.source_url} target="_blank" rel="noreferrer" className="inline-link">
            Source posting
          </a>
        )}
      </div>
    </article>
  );
}
