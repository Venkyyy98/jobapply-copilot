import Link from "next/link";

const localSteps = [
  "Start the API on http://127.0.0.1:8787 and the web app on http://127.0.0.1:3000.",
  "Load the extension unpacked from the extension folder in chrome://extensions.",
  "Open extension Options and set API base URL to http://127.0.0.1:8787.",
  "Paste the local JAC_TOKEN into the local shared token field.",
  "Open a real job posting page, run Analyze this job, then generate documents or use an existing resume before clicking Mark applied."
];

const betaSteps = [
  "Go to the hosted website and sign in with Google.",
  "Open beta onboarding, save a factual candidate profile, and create an extension token.",
  "Install the Chrome extension and paste the hosted API URL plus extension token into Options.",
  "Use the extension on a job posting page to analyze it, optionally generate a tailored resume and cover letter, or apply with an existing resume.",
  "After manually submitting the application, click Mark applied so the website tracker updates."
];

export default function HowItWorksPage() {
  return (
    <>
      <section className="page-hero compact">
        <div>
          <p className="eyebrow">How it works</p>
          <h1>From job description to tailored packet in one reviewed flow.</h1>
          <p>
            The extension is the capture layer. The website is the control center. Together they keep candidate data
            user-scoped, document generation factual, and final submission manual.
          </p>
        </div>
        <div className="pill-row">
          <Link href="/install-extension" className="primary-button">Install extension</Link>
          <Link href="/app/profile" className="ghost-button">Set up account</Link>
        </div>
      </section>

      <section className="timeline-grid">
        <div className="timeline-card">
          <span>01</span>
          <h2>Read the posting</h2>
          <p>The user opens a real job page and chooses when the extension should analyze it.</p>
        </div>
        <div className="timeline-card">
          <span>02</span>
          <h2>Match against profile facts</h2>
          <p>The backend compares requirements with saved experience bullets, projects, skills, education, and preferences.</p>
        </div>
        <div className="timeline-card">
          <span>03</span>
          <h2>Draft resume and cover letter</h2>
          <p>The copilot selects the most relevant evidence and creates a packet the user can review before downloading.</p>
        </div>
        <div className="timeline-card">
          <span>04</span>
          <h2>Track the application</h2>
          <p>After manual submission, the user marks applied so their private dashboard reflects real progress.</p>
        </div>
      </section>

      <section className="detail-columns" style={{ marginTop: 20 }}>
        <div className="panel guide-panel">
          <p className="eyebrow">For development</p>
          <h2>Local test path</h2>
          <ol className="ordered-list">
            {localSteps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
        <div className="panel guide-panel featured">
          <p className="eyebrow">For beta users</p>
          <h2>Public beta path</h2>
          <ol className="ordered-list">
            {betaSteps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </div>
      </section>
    </>
  );
}
