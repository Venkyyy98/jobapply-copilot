import type { Metadata } from "next";
import type { ReactNode } from "react";

import { SiteHeader } from "@/components/site-header";

import "./globals.css";

export const metadata: Metadata = {
  title: "JobApply Copilot",
  description: "Public jobs feed and private application tracker for ethical job search operations."
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="page-shell">
          <SiteHeader />
          {children}
        </div>
      </body>
    </html>
  );
}
