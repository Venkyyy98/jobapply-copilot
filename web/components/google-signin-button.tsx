"use client";

import { signIn } from "next-auth/react";

export function GoogleSignInButton() {
  return (
    <button type="button" className="primary-button" onClick={() => signIn("google", { callbackUrl: "/app" })}>
      Continue with Google
    </button>
  );
}
