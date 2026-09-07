import Link from "next/link";

import { DeleteJobButton } from "@/components/delete-job-button";
import type { PrivateJobFeedItem, PublicJobFeedItem } from "@/lib/types";

function hasValidSourceUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

function countLabel(value: number, label: string) {
  return `${value} ${label}`;
}

function formatActionDate(value?: string) {
  if (!value) return "";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

export function JobCard({ job, workspace = false }: { job: PublicJobFeedItem | PrivateJobFeedItem; workspace?: boolean }) {
  const detailHref = workspace ? `/app/jobs?job=${job.id}` : `/jobs/${job.id}`;
  const actionDates = "action_dates" in job ? job.action_dates : {};
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
      {workspace && (actionDates.analyzed || actionDates.applied) ? (
        <div className="job-activity-dates">
          {actionDates.analyzed ? (
            <span>
              <strong>Checked</strong>
              {formatActionDate(actionDates.analyzed)}
            </span>
          ) : null}
          {actionDates.applied ? (
            <span>
              <strong>Applied</strong>
              {formatActionDate(actionDates.applied)}
            </span>
          ) : null}
        </div>
      ) : null}
      <div className="job-card-footer">
        <Link href={detailHref} className="inline-link">
          {workspace ? "Open tracker item" : "View job details"}
        </Link>
        {hasValidSourceUrl(job.source_url) ? (
          <a href={job.source_url} target="_blank" rel="noreferrer" className="inline-link">
            Source posting
          </a>
        ) : (
          <span className="muted">Source unavailable</span>
        )}
        {workspace ? <DeleteJobButton jobId={job.id} /> : null}
      </div>
    </article>
  );
}
