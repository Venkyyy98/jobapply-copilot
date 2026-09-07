import { getServerSession } from "next-auth";
import { NextRequest, NextResponse } from "next/server";

import { authOptions } from "@/lib/auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8787";

export async function POST(request: NextRequest) {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    return new NextResponse("Authentication required.", { status: 401 });
  }
  const response = await fetch(`${API_BASE_URL}/find_targets`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(process.env.JAC_TOKEN ? { "X-JAC-TOKEN": process.env.JAC_TOKEN } : {}),
      "X-WEB-USER-EMAIL": session.user.email,
      "X-WEB-USER-NAME": session.user.name || "",
      "X-WEB-USER-IMAGE": session.user.image || ""
    },
    body: await request.text(),
    cache: "no-store"
  });
  return new NextResponse(await response.text(), { status: response.status });
}
