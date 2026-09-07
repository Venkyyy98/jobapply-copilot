export default function TermsPage() {
  return (
    <>
      <div className="section-head">
        <div>
          <h1>Beta terms</h1>
          <p className="muted">JobApply Copilot is an application assistant, not an application submission agent.</p>
        </div>
      </div>
      <section className="panel legal-copy">
        <h2>Beta product</h2>
        <p>
          JobApply Copilot is provided as a beta. Features may change, quotas may be adjusted, and availability may vary
          while the product is being tested.
        </p>
        <h2>User responsibility</h2>
        <p>
          You are responsible for reviewing every generated document, answer, upload, and application field before using
          it. The product is designed to keep final submission under your control.
        </p>
        <h2>Compliance boundaries</h2>
        <p>
          The product must not be used to bypass CAPTCHAs, authentication controls, rate limits, paywalls, platform
          restrictions, or employer application rules. It must not be used to fabricate employers, dates, degrees,
          certifications, metrics, or work authorization status.
        </p>
        <h2>No guarantee</h2>
        <p>
          JobApply Copilot does not guarantee interviews, offers, application outcomes, or the accuracy of third-party job
          postings.
        </p>
      </section>
    </>
  );
}
