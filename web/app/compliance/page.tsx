export default function CompliancePage() {
  return (
    <>
      <section className="page-hero compact compliance-hero">
        <div>
          <p className="eyebrow">Compliance philosophy</p>
          <h1>Assist the candidate. Do not pretend to be the candidate.</h1>
          <p>
            JobApply Copilot is designed for ethical application support: factual tailoring, user review, manual
            submission, and clear boundaries around automation.
          </p>
        </div>
        <div className="trust-badge">
          <strong>User-controlled</strong>
          <span>No auto-submit, no bypassing, no fabricated claims.</span>
        </div>
      </section>

      <section className="compliance-grid">
        <div className="panel compliance-card danger">
          <p className="eyebrow">Blocked behavior</p>
          <h3>What the copilot will not do</h3>
          <ul className="list-card">
            <li>No CAPTCHA, bot-detection, paywall, auth, or rate-limit bypass.</li>
            <li>No auto-submit on job platforms. Final submission is always manual.</li>
            <li>No scraping of disallowed sites. The feed is extension-sync or user-submitted only.</li>
            <li>No fabricated employers, dates, degrees, certifications, or metrics.</li>
          </ul>
        </div>
        <div className="panel compliance-card">
          <p className="eyebrow">Allowed support</p>
          <h3>What the website is for</h3>
          <ul className="list-card">
            <li>Public-safe jobs feed with anonymous counts.</li>
            <li>Private dashboard for analysis, document history, outreach, and tracking.</li>
            <li>Discoverability and publicity layer around your extension.</li>
            <li>Manual, user-controlled application operations.</li>
          </ul>
        </div>
      </section>

      <section className="feature-grid" style={{ marginTop: 18 }}>
        <div className="panel mini-trust-card">
          <h3>Factual inventory</h3>
          <p className="muted">Users supply profile facts, bullets, projects, education, and preferences before generation.</p>
        </div>
        <div className="panel mini-trust-card">
          <h3>Review before use</h3>
          <p className="muted">Generated documents are drafts. Users review and download before submitting anywhere.</p>
        </div>
        <div className="panel mini-trust-card">
          <h3>Private tracker</h3>
          <p className="muted">Jobs, documents, and application actions are scoped to the signed-in account.</p>
        </div>
      </section>
    </>
  );
}
