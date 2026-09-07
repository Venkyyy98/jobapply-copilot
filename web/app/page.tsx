import Link from "next/link";
import { getServerSession } from "next-auth";

import { JobCard } from "@/components/job-card";
import { fetchMyJobs, fetchPublicJobs } from "@/lib/api";
import { authOptions } from "@/lib/auth";

export default async function HomePage() {
  const session = await getServerSession(authOptions);
  const signedIn = Boolean(session?.user?.email);
  const publicJobs = await fetchPublicJobs({ sort: "most_applied" }).catch(() => ({
    items: [],
    available_role_families: [],
    total: 0
  }));
  const privateJobs = signedIn ? await fetchMyJobs().catch(() => ({ items: [], total: 0 })) : null;
  const visibleJobs = signedIn ? privateJobs?.items || [] : publicJobs.items;
  const visibleJobTotal = signedIn ? privateJobs?.total || 0 : publicJobs.total;

  return (
    <>
      <section className="hero">
        <div>
          <p className="eyebrow">Controlled public beta</p>
          <h1>Tailored job packets without turning applications into autopilot.</h1>
          <p>
            JobApply Copilot starts where candidates already work: on the job posting. The Chrome extension reads the
            role, compares it with your factual profile, drafts compliant resume and cover letter packets, and keeps the
            final submission fully under your control.
          </p>
          <div className="pill-row">
            <Link href="/app/profile" className="primary-button">
              Build my profile
            </Link>
            <Link href="/install-extension" className="ghost-button">
              Install extension
            </Link>
            <Link href="/demo" className="ghost-button">
              Try Demo
            </Link>
            <Link href="/how-it-works" className="ghost-button">
              How it works
            </Link>
            <Link href="/app" className="ghost-button">
              View my tracker
            </Link>
            <Link href="/jobs" className="ghost-button">
              Browse curated jobs
            </Link>
          </div>
        </div>
        <div className="hero-side">
          <div className="hero-metric hero-metric-featured">
            <p>Beta workflow</p>
            <strong>Profile → Analyze → Approve → Apply</strong>
            <span className="muted">factual profile inventory, job-page extraction, tailored packet generation, and manual submission</span>
          </div>
          <div className="hero-metric">
            <p>Guardrails</p>
            <strong>No auto-submit</strong>
            <span className="muted">no CAPTCHA bypass, no fabricated claims, no unsupported resume facts</span>
          </div>
          <div className="hero-metric">
            <p>{signedIn ? "Your reviewed jobs" : "Tracked job examples"}</p>
            <strong>{visibleJobTotal}</strong>
            <span className="muted">
              {signedIn ? "private roles from your extension activity" : "public examples with role details and anonymous activity signals"}
            </span>
          </div>
        </div>
      </section>

      <div className="section-head">
        <div>
          <p className="eyebrow">Workflow</p>
          <h2>Built around human approval.</h2>
        </div>
      </div>
      <section className="process-grid">
        <div className="process-card">
          <span>01</span>
          <h3>Create a factual profile</h3>
          <p className="muted">
            Add your real experience, project bullets, education, skills, and preferences once.
          </p>
        </div>
        <div className="process-card">
          <span>02</span>
          <h3>Analyze the role</h3>
          <p className="muted">
            The extension extracts the visible job description and identifies relevant requirements.
          </p>
        </div>
        <div className="process-card">
          <span>03</span>
          <h3>Generate with guardrails</h3>
          <p className="muted">
            The copilot selects matching bullets/projects and drafts documents only from supported facts.
          </p>
        </div>
        <div className="process-card">
          <span>04</span>
          <h3>Apply and track</h3>
          <p className="muted">
            You submit manually, then mark the application so your private tracker stays current.
          </p>
        </div>
      </section>

      <div className="section-head">
        <h2>{signedIn ? "Recently reviewed jobs" : "Curated job examples"}</h2>
        <Link href="/jobs" className="inline-link">
          {signedIn ? "Open my jobs" : "View job details"}
        </Link>
      </div>
      <section className="job-grid">
        {visibleJobs.slice(0, 4).map((job) => (
          <JobCard key={job.id} job={job} workspace={signedIn} />
        ))}
        {!visibleJobs.length ? (
          <div className="panel empty-state">
            {signedIn ? "No reviewed jobs yet. Analyze a posting from the extension to fill this area." : "No curated jobs yet. Your extension-analyzed jobs stay private by default."}
          </div>
        ) : null}
      </section>
    </>
  );
}
