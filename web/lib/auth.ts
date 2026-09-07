import "@/lib/root-env";

import { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";

const secureCookies = process.env.NODE_ENV === "production";

export const authOptions: NextAuthOptions = {
  secret: process.env.NEXTAUTH_SECRET,
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || ""
    })
  ],
  session: {
    strategy: "jwt"
  },
  cookies: {
    sessionToken: {
      // v2 intentionally ignores session cookies encrypted before the local
      // NEXTAUTH_SECRET was loaded consistently from the repository root.
      name: secureCookies ? "__Secure-jobapply.session-token.v2" : "jobapply.session-token.v2",
      options: {
        httpOnly: true,
        sameSite: "lax",
        path: "/",
        secure: secureCookies
      }
    }
  },
  pages: {
    signIn: "/signin"
  },
  callbacks: {
    async session({ session, token }) {
      if (session.user) {
        session.user.email = token.email;
        session.user.name = token.name;
        session.user.image = typeof token.picture === "string" ? token.picture : session.user.image;
      }
      return session;
    }
  }
};
