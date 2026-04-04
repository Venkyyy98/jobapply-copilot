export default function SignInPage() {
  return (
    <section className="signin-card">
      <p className="eyebrow">Google authentication</p>
      <h1>Sign in to your workspace</h1>
      <p className="muted">
        The public jobs feed is open. The private workspace requires Google sign-in so actions, docs, outreach, and history can stay user-scoped.
      </p>
      <a className="primary-button" href="/api/auth/signin/google">
        Continue with Google
      </a>
    </section>
  );
}
