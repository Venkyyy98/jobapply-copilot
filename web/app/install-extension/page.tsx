import "@/lib/root-env";

import { getServerSession } from "next-auth";
import Link from "next/link";

import { ExtensionTokenPanel } from "@/components/extension-token-panel";
import { fetchMyProfile } from "@/lib/api";
import { authOptions } from "@/lib/auth";

const chromeStoreUrl = process.env.NEXT_PUBLIC_CHROME_EXTENSION_URL || "";
const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8787";

export default async function InstallExtensionPage() {
  const session = await getServerSession(authOptions);
  const profile = session?.user?.email
    ? await fetchMyProfile().catch(() => ({
        candidate_profile: {},
        preferences: {},
        profile_complete: false,
        compliance_notes: ["Profile service is unavailable."],
        updated_at: ""
      }))
    : null;
  const signedIn = Boolean(session?.user?.email);
  const profileReady = Boolean(profile?.profile_complete);

  return (
    <>
      <section className="page-hero install-hero">
        <div>
          <p className="eyebrow">Chrome extension setup</p>
          <h1>Connect the browser extension to your private profile.</h1>
          <p>
            The extension reads job descriptions from the user’s side of Chrome. The website provides sign-in, profile
            data, tokens, and the application tracker.
          </p>
        </div>
        <div className="install-status-card">
          <p className="eyebrow">Current channel</p>
          {chromeStoreUrl ? (
            <a className="primary-button" href={chromeStoreUrl} target="_blank" rel="noreferrer">
              Add to Chrome
            </a>
          ) : (
            <>
              <strong>Private beta install</strong>
              <span className="muted">Use Load unpacked while Chrome Web Store packaging is prepared.</span>
            </>
          )}
        </div>
      </section>

      <section className="detail-columns">
        <div className="panel guide-panel featured">
          <p className="eyebrow">Connection checklist</p>
          <h2>Follow this order</h2>
          <ol className="ordered-list install-checklist">
            <li className={signedIn ? "done-step" : ""}>Sign in with Google on this website.</li>
            <li className={profileReady ? "done-step" : ""}>Complete and save your beta profile.</li>
            <li>Create your extension token from this page.</li>
            <li>Install the Chrome extension ZIP or Chrome Web Store version.</li>
            <li>Paste the API base URL and token into the extension Options page.</li>
            <li>Open a job posting, analyze it, then generate documents from your own profile.</li>
          </ol>

          <div className="install-actions">
            {!signedIn ? (
              <Link href="/signin" className="primary-button">
                Sign in first
              </Link>
            ) : null}
            {signedIn && !profileReady ? (
              <Link href="/app/profile" className="primary-button">
                Complete profile
              </Link>
            ) : null}
            <span className="pill">API: {apiBaseUrl}</span>
          </div>
        </div>

        <div className="stack">
          <section className="panel">
            <h2>Account status</h2>
            {!signedIn ? <p className="warning">Sign in before creating an extension token.</p> : null}
            {signedIn ? (
              <p className={profileReady ? "inline-status" : "warning"}>
                {profileReady ? "Profile ready. You can create an extension token." : "Profile incomplete. Token creation is locked."}
              </p>
            ) : null}
            {profile?.compliance_notes?.length ? (
              <ul className="list-card">
                {profile.compliance_notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            ) : null}
          </section>

          <ExtensionTokenPanel
            disabled={!signedIn || !profileReady}
            disabledReason={
              !signedIn
                ? "Sign in before creating an extension token."
                : "Complete your beta profile before creating an extension token."
            }
          />
        </div>
      </section>

      <section className="install-guide-grid">
        <div className="panel install-guide">
          <p className="eyebrow">Private tester install</p>
          <h2>Load the extension in Chrome</h2>
          <ol className="ordered-list">
            <li>Unzip the extension release folder you received.</li>
            <li>Open <code>chrome://extensions</code> in Chrome.</li>
            <li>Turn on Developer mode.</li>
            <li>Click Load unpacked and select the unzipped extension folder.</li>
            <li>Open extension Options and paste the API base URL plus your token.</li>
          </ol>
        </div>
        <div className="panel install-guide">
          <p className="eyebrow">What users should expect</p>
          <h2>After setup</h2>
          <ul className="list-card">
            <li>Analyze buttons appear in the extension popup, not inside job sites.</li>
            <li>Generated docs use the signed-in profile attached to the extension token.</li>
            <li>Applied status updates only when the user manually marks it.</li>
          </ul>
        </div>
      </section>
    </>
  );
}
