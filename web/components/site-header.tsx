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
          Ethical application ops for data, analytics, and SAP roles.
        </p>
      </div>
      <nav className="nav-links">
        <Link href="/jobs">Jobs</Link>
        <Link href="/compliance">Compliance</Link>
        <Link href="/app">Workspace</Link>
        {session?.user?.email ? (
          <a href="/api/auth/signout?callbackUrl=/">Sign out</a>
        ) : (
          <Link href="/signin">Sign in</Link>
        )}
      </nav>
    </header>
  );
}
