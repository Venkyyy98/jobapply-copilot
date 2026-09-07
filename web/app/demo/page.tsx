import Link from "next/link";

const sampleReasons = [
  "Sample profile includes production LLM and RAG project experience.",
  "Sample profile includes data pipelines, API delivery, and cloud deployment language.",
  "Demo content is not based on your real resume or personal data."
];

export default function DemoPage() {
  return (
    <>
      <section className="page-hero compact">
        <div>
          <p className="eyebrow">Demo mode</p>
          <h1>Try the workflow without an API key.</h1>
          <p>
            This recruiter-friendly demo uses a sample job, sample candidate profile, and deterministic mocked analysis.
            It does not consume a real OpenAI key or expose personal information.
          </p>
        </div>
        <Link href="/app/profile" className="primary-button">Use my real profile</Link>
      </section>
      <section className="demo-grid">
        <article className="panel">
          <h2>Sample job</h2>
          <p><strong>AI Engineer Consultant</strong></p>
          <p className="muted">Demo Analytics Co · Remote</p>
          <p>
            Build production LLM applications, RAG pipelines, evaluation telemetry, secure APIs, and document-ingestion workflows.
          </p>
        </article>
        <article className="panel">
          <h2>Mocked fit analysis</h2>
          <div className="hero-metric">
            <p>Fit score</p>
            <strong>84</strong>
          </div>
          <ul className="list-card">
            {sampleReasons.map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
        </article>
        <article className="panel">
          <h2>Sample tailored output</h2>
          <p className="sample-label">SAMPLE CONTENT</p>
          <p>
            The generated packet would highlight RAGProbe for retrieval evaluation, AgentOps Copilot for tool-calling
            workflows, and enterprise integration work as evidence of production delivery discipline.
          </p>
          <p className="muted">In real mode, claims are checked against the candidate profile before downloads are returned.</p>
        </article>
      </section>
    </>
  );
}
