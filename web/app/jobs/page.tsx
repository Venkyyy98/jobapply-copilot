import { JobCard } from "@/components/job-card";
import { JobsFilterBar } from "@/components/jobs-filter-bar";
import { fetchPublicJobs } from "@/lib/api";

export default async function JobsPage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const data = await fetchPublicJobs(params).catch(() => ({
    items: [],
    available_role_families: [],
    total: 0
  }));

  return (
    <>
      <div className="section-head">
        <div>
          <h1>Recent jobs</h1>
          <p className="muted">Public-safe feed of roles synced from the extension or entered manually.</p>
        </div>
      </div>
      <JobsFilterBar searchParams={params} roleFamilies={data.available_role_families} />
      <div className="section-head">
        <p className="muted">{data.total} roles in the current result set</p>
      </div>
      <section className="job-grid">
        {data.items.map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
        {!data.items.length ? (
          <div className="panel empty-state">No roles matched the current filters. Clear the filters or sync new jobs.</div>
        ) : null}
      </section>
    </>
  );
}
