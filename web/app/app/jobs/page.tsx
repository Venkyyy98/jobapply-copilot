import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { JobCard } from "@/components/job-card";
import { authOptions } from "@/lib/auth";
import { fetchMyJobs } from "@/lib/api";

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
  const jobs = await fetchMyJobs(params.status || "");

  return (
    <>
      <div className="section-head">
        <div>
          <h1>My pipeline</h1>
          <p className="muted">Every saved, analyzed, generated, outreach, and applied action tied to your account.</p>
        </div>
      </div>
      <form className="filters-panel" action="/app/jobs">
        <div className="filters-grid">
          <label>
            Status
            <select name="status" defaultValue={params.status || ""}>
              <option value="">All actions</option>
              <option value="SAVED">Saved</option>
              <option value="ANALYZED">Analyzed</option>
              <option value="GENERATED_DOCS">Generated docs</option>
              <option value="OUTREACH_STARTED">Outreach</option>
              <option value="APPLIED">Applied</option>
            </select>
          </label>
        </div>
        <button type="submit" className="primary-button">
          Filter pipeline
        </button>
      </form>
      <section className="job-grid" style={{ marginTop: 18 }}>
        {jobs.items.map((job) => (
          <JobCard key={job.id} job={job} workspace />
        ))}
        {!jobs.items.length ? <div className="panel empty-state">No jobs matched the current pipeline filter.</div> : null}
      </section>
    </>
  );
}
