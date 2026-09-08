import Link from "next/link";
import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { ApiKeyControls } from "@/components/api-key-controls";
import { JobCard } from "@/components/job-card";
import { StatsGrid } from "@/components/stats-grid";
import { authOptions } from "@/lib/auth";
import { fetchMyJobs, fetchMyStats } from "@/lib/api";
import type { UserJobListResponse, UserStatsResponse } from "@/lib/types";

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

function emptyStats(email: string, name?: string | null, image?: string | null): UserStatsResponse {
  return {
    user: {
      email,
      name: name || "",
      image_url: image || ""
    },
    counts: {},
    recent_activity: [],
    application_activity: emptyJobs().activity
  };
}

export default async function WorkspacePage() {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    redirect("/signin");
  }

  const [statsResult, jobsResult] = await Promise.allSettled([fetchMyStats(), fetchMyJobs()]);
  const stats =
    statsResult.status === "fulfilled"
      ? statsResult.value
      : emptyStats(session.user.email, session.user.name, session.user.image);
  const jobs = jobsResult.status === "fulfilled" ? jobsResult.value : emptyJobs();
  const serviceUnavailable = statsResult.status === "rejected" || jobsResult.status === "rejected";

  return (
    <>
      <div className="section-head">
        <div>
          <h1>Application tracker</h1>
          <p className="muted">
            Private tracker for {stats.user.name || stats.user.email}. Extension-analyzed jobs, generated docs, outreach, and applied status stay tied to this account.
          </p>
        </div>
        <Link href="/app/jobs" className="inline-link">
          Open full pipeline
        </Link>
      </div>
      {serviceUnavailable ? (
        <div className="auth-warning">
          The tracker service is waking up or temporarily unavailable. Reload in about a minute; your saved Neon data is not deleted by this message.
        </div>
      ) : null}
      <StatsGrid counts={stats.counts} />
      <ApiKeyControls />
      <div className="workspace-layout" style={{ marginTop: 20 }}>
        <section className="panel">
          <h2>Recent pipeline activity</h2>
          <ul className="list-card">
            {stats.recent_activity.map((item) => (
              <li key={`${item.title}-${item.updated_at}`}>
                <strong>{item.title}</strong> at {item.company}
                <div className="muted">
                  {item.action_type.toLowerCase()} · {new Date(item.updated_at).toLocaleString()}
                </div>
              </li>
            ))}
            {!stats.recent_activity.length ? <li className="empty-state">No private activity yet. Use the jobs feed to start tracking actions.</li> : null}
          </ul>
        </section>
        <aside className="panel">
          <h2>Test the core workflow</h2>
          <ul className="list-card">
            <li><Link href="/app/profile" className="inline-link">Complete beta onboarding and connect the Chrome extension.</Link></li>
            <li>Open a real job posting in Chrome and click Analyze this job in the extension.</li>
            <li>Generate final docs only after approving the tailored packet.</li>
            <li>Click Mark applied after you manually submit so the Applied count updates here.</li>
          </ul>
        </aside>
      </div>
      <div className="section-head">
        <h2>Tracked jobs</h2>
      </div>
      <section className="job-grid">
        {jobs.items.map((job) => (
          <JobCard key={job.id} job={job} workspace />
        ))}
        {!jobs.items.length ? <div className="panel empty-state">No jobs tracked yet. Save or analyze a role to seed your tracker.</div> : null}
      </section>
    </>
  );
}
