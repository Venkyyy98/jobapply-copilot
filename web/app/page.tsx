import Link from "next/link";

import { JobCard } from "@/components/job-card";
import { fetchPublicJobs } from "@/lib/api";

export default async function HomePage() {
  const jobs = await fetchPublicJobs({ sort: "most_applied" }).catch(() => ({
    items: [],
    available_role_families: [],
    total: 0
  }));

  return (
    <>
      <section className="hero">
        <div>
          <p className="eyebrow">Public feed + private workspace</p>
          <h1>Turn your extension into a real application command center.</h1>
          <p>
            JobApply Copilot Web turns the local assistant into a public jobs surface and a signed-in workspace for
            analysis, tailored docs, outreach, and applied-job tracking. It stays compliant: no scraping beyond user
            synced jobs, no CAPTCHA bypass, no auto-submit.
          </p>
          <div className="pill-row">
            <Link href="/jobs" className="primary-button">
              Browse synced jobs
            </Link>
            <Link href="/app" className="ghost-button">
              Open workspace
            </Link>
          </div>
        </div>
        <div className="hero-side">
          <div className="hero-metric">
            <p>Public-safe feed</p>
            <strong>{jobs.total}</strong>
            <span className="muted">roles synced from extension analysis and manual entries</span>
          </div>
          <div className="hero-metric">
            <p>Anonymous social proof</p>
            <strong>Saved · Analyzed · Applied</strong>
            <span className="muted">aggregate counts without exposing any user identity</span>
          </div>
          <div className="hero-metric">
            <p>Private workflow</p>
            <strong>Docs + outreach + tracker</strong>
            <span className="muted">all the existing copilot features, organized in one signed-in workspace</span>
          </div>
        </div>
      </section>

      <div className="section-head">
        <h2>What the web app adds</h2>
      </div>
      <section className="feature-grid">
        <div className="panel">
          <h3>Public jobs page</h3>
          <p className="muted">
            LinkedIn-style cards with role, company, location, fit indicators, and anonymous activity counts.
          </p>
        </div>
        <div className="panel">
          <h3>Private workspace</h3>
          <p className="muted">
            Signed-in dashboard for saved jobs, generated docs, outreach drafts, and application pipeline tracking.
          </p>
        </div>
        <div className="panel">
          <h3>Extension remains primary</h3>
          <p className="muted">
            Browser autofill stays in the extension. The website becomes the dashboard and discovery surface around it.
          </p>
        </div>
      </section>

      <div className="section-head">
        <h2>Recent roles</h2>
        <Link href="/jobs" className="inline-link">
          View full feed
        </Link>
      </div>
      <section className="job-grid">
        {jobs.items.slice(0, 4).map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
        {!jobs.items.length ? <div className="panel empty-state">No jobs synced yet. Analyze a job in the extension first.</div> : null}
      </section>
    </>
  );
}
