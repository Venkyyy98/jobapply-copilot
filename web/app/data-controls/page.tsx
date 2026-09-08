import { DeleteDataButton } from "@/components/delete-data-button";

export default function DataControlsPage() {
  return (
    <>
      <div className="section-head">
        <div>
          <h1>Data controls</h1>
          <p className="muted">Export or delete the private data used by your JobApply Copilot beta tracker.</p>
        </div>
      </div>
      <section className="compliance-grid">
        <div className="panel">
          <h2>Export</h2>
          <p className="muted">Download your beta profile, private job records, and tracker actions as JSON.</p>
          <a className="primary-button" href="/api/data-export">Export my data</a>
        </div>
        <div className="panel">
          <h2>Delete</h2>
          <p className="muted">Delete your beta profile, extension tokens, usage events, private jobs, and action history.</p>
          <DeleteDataButton />
        </div>
      </section>
    </>
  );
}
