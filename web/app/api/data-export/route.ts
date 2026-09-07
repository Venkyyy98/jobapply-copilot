import { getServerSession } from "next-auth";
import { NextResponse } from "next/server";

import { authOptions } from "@/lib/auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8787";

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    return new NextResponse("Authentication required.", { status: 401 });
  }
  const response = await fetch(`${API_BASE_URL}/web/me/export`, {
    headers: {
      "X-WEB-USER-EMAIL": session.user.email,
      "X-WEB-USER-NAME": session.user.name || "",
      "X-WEB-USER-IMAGE": session.user.image || ""
    }
  });
  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: {
      "Content-Type": "application/json",
      "Content-Disposition": "attachment; filename=jobapply-copilot-data.json"
    }
  });
}
