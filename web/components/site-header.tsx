import Link from "next/link";
import { getServerSession } from "next-auth";

import { authOptions } from "@/lib/auth";

export async function SiteHeader() {
  const session = await getServerSession(authOptions);

  return (
    <header className="site-header">
      <div>
        <Link href="/" className="brand">
          JobApply Copilot
        </Link>
        <p className="brand-subtitle">
          Ethical application ops for modern job seekers.
        </p>
      </div>
      <nav className="nav-links">
        {session?.user?.email ? <Link href="/app/jobs">Application tracker</Link> : <Link href="/jobs">Jobs</Link>}
        <Link href="/how-it-works">How it works</Link>
        <Link href="/install-extension">Install</Link>
        <Link href="/compliance">Compliance</Link>
        <Link href="/privacy">Privacy</Link>
        <Link href="/app">Dashboard</Link>
        {session?.user?.email ? <Link href="/app/profile">Onboarding</Link> : null}
        {session?.user?.email ? <Link href="/data-controls">Data</Link> : null}
        {session?.user?.email ? (
          <a href="/api/auth/signout?callbackUrl=/">Sign out</a>
        ) : (
          <Link href="/signin">Sign in</Link>
        )}
      </nav>
    </header>
  );
}
