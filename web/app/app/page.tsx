import Link from "next/link";
import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { JobCard } from "@/components/job-card";
import { StatsGrid } from "@/components/stats-grid";
import { authOptions } from "@/lib/auth";
import { fetchMyJobs, fetchMyStats } from "@/lib/api";

export default async function WorkspacePage() {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    redirect("/signin");
  }

  const [stats, jobs] = await Promise.all([fetchMyStats(), fetchMyJobs()]);

  return (
    <>
      <div className="section-head">
        <div>
          <h1>Workspace</h1>
          <p className="muted">
            Private dashboard for {stats.user.name || stats.user.email}. Actions here stay user-scoped even when the job feed is public.
          </p>
        </div>
        <Link href="/app/jobs" className="inline-link">
          Open full pipeline
        </Link>
      </div>
      <StatsGrid counts={stats.counts} />
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
          <h2>Copilot surfaces</h2>
          <ul className="list-card">
            <li>Analyze and generate final docs in the extension, then sync back into this workspace.</li>
            <li>Track `saved`, `analyzed`, `generated_docs`, `applied`, and `outreach_started` status per role.</li>
            <li>Use the extension for browser prefill; this web app intentionally does not submit or prefill web forms.</li>
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
        {!jobs.items.length ? <div className="panel empty-state">No jobs tracked yet. Save or analyze a role to seed your workspace.</div> : null}
      </section>
    </>
  );
}
