export default function CompliancePage() {
  return (
    <>
      <div className="section-head">
        <h1>Compliance</h1>
        <p className="muted">The website preserves the same operating rules as the extension and local engine.</p>
      </div>
      <section className="compliance-grid">
        <div className="panel">
          <h3>Explicitly blocked</h3>
          <ul className="list-card">
            <li>No CAPTCHA, bot-detection, paywall, auth, or rate-limit bypass.</li>
            <li>No auto-submit on job platforms. Final submission is always manual.</li>
            <li>No scraping of disallowed sites. The feed is extension-sync or user-submitted only.</li>
            <li>No fabricated employers, dates, degrees, certifications, or metrics.</li>
          </ul>
        </div>
        <div className="panel">
          <h3>What the website is for</h3>
          <ul className="list-card">
            <li>Public-safe jobs feed with anonymous counts.</li>
            <li>Private dashboard for analysis, document history, outreach, and tracking.</li>
            <li>Discoverability and publicity layer around your extension.</li>
            <li>Manual, user-controlled application operations.</li>
          </ul>
        </div>
      </section>
    </>
  );
}
