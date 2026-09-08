import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { JobCard } from "@/components/job-card";
import { NetworkOutreach } from "@/components/network-outreach";
import {
  ApplicationActivityCharts,
  ApplicationActivitySummary,
  DailyApplicationActivity
} from "@/components/application-activity";
import { authOptions } from "@/lib/auth";
import { fetchMyJobs } from "@/lib/api";
import type { UserJobListResponse } from "@/lib/types";

function emptyJobs(): UserJobListResponse {
  return {
    items: [],
    total: 0,
    activity: {
      periods: {
        today: { checked: 0, applied: 0 },
        week: { checked: 0, applied: 0 },
        month: { checked: 0, applied: 0 },
        all: { checked: 0, applied: 0 }
      },
      filtered: { checked: 0, applied: 0 },
      daily: []
    }
  };
}

export default async function WorkspaceJobsPage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    redirect("/signin");
  }
  const params = await searchParams;
  let serviceUnavailable = false;
  const jobs = await fetchMyJobs({
    q: params.q || "",
    status: params.status || "",
    date_from: params.date_from || "",
    date_to: params.date_to || ""
  }).catch(() => {
    serviceUnavailable = true;
    return emptyJobs();
  });
  const hasDateFilter = Boolean(params.date_from || params.date_to);
  const selectedJob = jobs.items.find((job) => String(job.id) === String(params.job || ""));
  const today = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  const toDateStr = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const todayValue = toDateStr(today);
  const weekStart = new Date(today);
  weekStart.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  const weekStartValue = toDateStr(weekStart);
  const monthStartValue = `${todayValue.slice(0, 8)}01`;

  return (
    <>
      <div className="section-head">
        <div>
          <h1>My pipeline</h1>
          <p className="muted">
            Your private application pipeline from extension activity and job-detail actions. Use the Applied filter to confirm how many roles you submitted.
          </p>
        </div>
      </div>
      {serviceUnavailable ? (
        <div className="auth-warning">
          The application tracker service is waking up or temporarily unavailable. Reload in about a minute; this does not mean your saved jobs were deleted.
        </div>
      ) : null}
      <ApplicationActivitySummary activity={jobs.activity} filtered={hasDateFilter} />
      <ApplicationActivityCharts activity={jobs.activity} />
      <form className="filters-panel" action="/app/jobs">
        <div className="filter-heading">
          <div>
          <h2>Search and filter applications</h2>
          <p className="muted">Search every tracked application by company or job title, then narrow by status or date.</p>
          </div>
          <div className="quick-filter-links">
            <a href={`/app/jobs?status=APPLIED&date_from=${todayValue}&date_to=${todayValue}`}>Applied today</a>
            <a href={`/app/jobs?status=APPLIED&date_from=${weekStartValue}&date_to=${todayValue}`}>Applied this week</a>
            <a href={`/app/jobs?status=APPLIED&date_from=${monthStartValue}&date_to=${todayValue}`}>Applied this month</a>
          </div>
        </div>
        <div className="filters-grid">
          <label className="tracker-search-field">
            Company or job role
            <input
              type="search"
              name="q"
              placeholder="e.g. Deloitte or AI Engineer"
              defaultValue={params.q || ""}
            />
          </label>
          <label>
            Status
            <select name="status" defaultValue={params.status || ""}>
              <option value="">All actions</option>
              <option value="SAVED">Saved</option>
              <option value="ANALYZED">Checked / analyzed</option>
              <option value="GENERATED_DOCS">Generated docs</option>
              <option value="OUTREACH_STARTED">Outreach</option>
              <option value="APPLIED">Applied</option>
            </select>
          </label>
          <label>
            Start date
            <input type="date" name="date_from" defaultValue={params.date_from || ""} />
          </label>
          <label>
            End date
            <input type="date" name="date_to" defaultValue={params.date_to || ""} />
          </label>
        </div>
        <div className="filter-actions">
          <button type="submit" className="primary-button">Search applications</button>
          <a href="/app/jobs" className="secondary-button">Clear filters</a>
          {params.q ? <span className="muted">{jobs.total} matching application{jobs.total === 1 ? "" : "s"}</span> : null}
        </div>
      </form>
      {selectedJob?.source_job_id ? (
        <NetworkOutreach
          jobId={selectedJob.source_job_id}
          role={selectedJob.title}
          company={selectedJob.company}
        />
      ) : null}
      <section className="job-grid" style={{ marginTop: 18 }}>
        {jobs.items.map((job) => (
          <JobCard key={job.id} job={job} workspace />
        ))}
        {!jobs.items.length ? (
          <div className="panel empty-state">
            No applications matched that company, role, status, or date.
          </div>
        ) : null}
      </section>
      <DailyApplicationActivity activity={jobs.activity} />
    </>
  );
}
