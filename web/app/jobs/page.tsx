import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { JobCard } from "@/components/job-card";
import { JobsFilterBar } from "@/components/jobs-filter-bar";
import { fetchPublicJobs } from "@/lib/api";
import { authOptions } from "@/lib/auth";

export default async function JobsPage({
  searchParams
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const session = await getServerSession(authOptions);
  const signedIn = Boolean(session?.user?.email);
  if (signedIn) {
    const query = new URLSearchParams();
    for (const key of ["status", "date_from", "date_to"]) {
      if (params[key]) query.set(key, params[key]);
    }
    redirect(`/app/jobs${query.size ? `?${query.toString()}` : ""}`);
  }
  const publicData = !signedIn
    ? await fetchPublicJobs(params).catch(() => ({
        items: [],
        available_role_families: [],
        total: 0
      }))
    : { items: [], available_role_families: [], total: 0 };
  const items = publicData.items;
  const total = publicData.total;

  return (
    <>
      <div className="section-head">
        <div>
          <h1>Curated job details</h1>
          <p className="muted">
            Public-safe examples and shared roles. Jobs analyzed from a user's extension stay private unless deliberately curated.
          </p>
        </div>
      </div>
      <JobsFilterBar searchParams={params} roleFamilies={publicData.available_role_families} />
      <div className="section-head">
        <p className="muted">
          {total} roles in the current result set
        </p>
      </div>
      <section className="job-grid">
        {items.map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
        {!items.length ? (
          <div className="panel empty-state">
            No curated roles matched the current filters.
          </div>
        ) : null}
      </section>
    </>
  );
}
