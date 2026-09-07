import "@/lib/root-env";

import { GoogleSignInButton } from "@/components/google-signin-button";

export default async function SignInPage({
  searchParams
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const params = await searchParams;
  const hasGoogleError = params.error === "google";
  const nextAuthUrl = process.env.NEXTAUTH_URL || "http://localhost:3000";
  const redirectUri = `${nextAuthUrl.replace(/\/$/, "")}/api/auth/callback/google`;
  const origin = nextAuthUrl.replace(/\/$/, "");
  const missing = [
    ["GOOGLE_CLIENT_ID", process.env.GOOGLE_CLIENT_ID],
    ["GOOGLE_CLIENT_SECRET", process.env.GOOGLE_CLIENT_SECRET],
    ["NEXTAUTH_SECRET", process.env.NEXTAUTH_SECRET],
    ["NEXTAUTH_URL", process.env.NEXTAUTH_URL]
  ]
    .filter(([, value]) => !value)
    .map(([key]) => key);
  const googleReady = missing.length === 0;

  return (
    <section className="signin-card">
      <p className="eyebrow">Google authentication</p>
      <h1>Sign in to your workspace</h1>
      <p className="muted">
        The public jobs feed is open. The private workspace requires Google sign-in so actions, docs, outreach, and history can stay user-scoped.
      </p>
      {hasGoogleError ? (
        <div className="auth-warning">
          Google sign-in is not configured for this app URL yet. Add the OAuth values below, restart the web app, then open the site at {origin}.
        </div>
      ) : null}
      {!googleReady ? (
        <div className="auth-setup">
          <h2>Local setup needed</h2>
          <p className="muted">Missing env values: {missing.join(", ")}</p>
          <ol className="ordered-list">
            <li>Create a Google OAuth client for a Web application.</li>
            <li>Add this authorized JavaScript origin: <code>{origin}</code></li>
            <li>Add this authorized redirect URI: <code>{redirectUri}</code></li>
            <li>Put the client ID, client secret, NextAuth secret, and URL in <code>.env</code>.</li>
            <li>Restart the web app and try sign-in again.</li>
          </ol>
        </div>
      ) : (
        <GoogleSignInButton />
      )}
    </section>
  );
}
