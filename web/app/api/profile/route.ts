import { getServerSession } from "next-auth";
import type { Session } from "next-auth";
import { NextRequest, NextResponse } from "next/server";

import { authOptions } from "@/lib/auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8787";

function invalidProfileRedirect(request: NextRequest, message: string) {
  const url = new URL("/app/profile", process.env.NEXTAUTH_URL || request.url);
  url.searchParams.set("error", message);
  return NextResponse.redirect(url, { status: 303 });
}

function userHeaders(session: Session) {
  return {
    "Content-Type": "application/json",
    "X-WEB-USER-EMAIL": session?.user?.email || "",
    "X-WEB-USER-NAME": session?.user?.name || "",
    "X-WEB-USER-IMAGE": session?.user?.image || ""
  };
}

function parseJsonField(value: FormDataEntryValue | null, label: string) {
  try {
    return JSON.parse(String(value || "{}"));
  } catch {
    throw new Error(
      `${label} is not valid JSON. Use double quotes around keys and text values, and use arrays like ["Python"] or [{"company": "Example"}].`
    );
  }
}

export async function POST(request: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    return new NextResponse("Authentication required.", { status: 401 });
  }

  const form = await request.formData();
  try {
    const candidateProfile = parseJsonField(form.get("candidate_profile"), "Candidate profile JSON");
    const preferences = parseJsonField(form.get("preferences"), "Preferences JSON");
    const response = await fetch(`${API_BASE_URL}/web/me/profile`, {
      method: "PUT",
      headers: userHeaders(session),
      body: JSON.stringify({ candidate_profile: candidateProfile, preferences })
    });
    if (!response.ok) {
      const detail = await response.text();
      const isRenderError = response.status === 502 || detail.trim().startsWith("<!DOCTYPE html>");
      return invalidProfileRedirect(
        request,
        isRenderError
          ? "The profile service is waking up or temporarily unavailable. Reload in about a minute and save again."
          : detail || `Profile service returned ${response.status}. Please try again.`
      );
    }
  } catch (error) {
    return invalidProfileRedirect(request, error instanceof Error ? error.message : "Invalid profile JSON.");
  }

  return NextResponse.redirect(new URL("/app/profile?saved=1", process.env.NEXTAUTH_URL || request.url));
}
