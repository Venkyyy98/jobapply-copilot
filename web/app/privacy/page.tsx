export default function PrivacyPage() {
  return (
    <>
      <div className="section-head">
        <div>
          <h1>Privacy</h1>
          <p className="muted">Plain-language beta privacy notice for JobApply Copilot.</p>
        </div>
      </div>
      <section className="panel legal-copy">
        <h2>What we collect</h2>
        <p>
          JobApply Copilot stores the account identity you use to sign in, profile facts you provide, job descriptions
          you choose to analyze, generated document records, and workspace actions such as saved or applied.
        </p>
        <h2>How it is used</h2>
        <p>
          Your data is used to analyze job postings, tailor documents from your factual profile, power your private
          workspace, enforce beta quotas, and improve reliability. The product does not auto-submit applications.
        </p>
        <h2>AI processing</h2>
        <p>
          Job text and profile facts may be sent to the configured AI provider to generate analysis, resume language,
          cover letters, or outreach drafts. Generated claims are checked against your profile before final documents are
          returned.
        </p>
        <h2>API keys</h2>
        <p>
          If you provide your own OpenAI API key, the web app stores it in browser session storage by default. The
          Chrome extension uses session storage by default as well. Remembering a key is opt-in and stores it only on
          that device. API keys are sent to the backend only for the AI request that needs them and are not stored in the
          backend database.
        </p>
        <h2>Temporary files</h2>
        <p>
          Generated PDFs, DOCX files, and text previews are temporary beta artifacts. The server is configured to delete
          generated output folders after the retention window, and you can delete individual tracked applications or your
          entire beta workspace from data controls.
        </p>
        <h2>Your controls</h2>
        <p>
          You can export or delete beta workspace data from the data controls page. Extension tokens can be replaced by
          creating a new token from onboarding.
        </p>
        <h2>Outreach limitations</h2>
        <p>
          LinkedIn outreach features generate drafts for user-provided or public-search contacts. The product does not
          log into LinkedIn, send bulk messages, bypass platform controls, or use private LinkedIn APIs.
        </p>
      </section>
    </>
  );
}
