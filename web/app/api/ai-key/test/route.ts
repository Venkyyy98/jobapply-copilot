import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8787";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const apiKey = String(body?.apiKey || "").trim();
  if (!apiKey) {
    return NextResponse.json({ detail: "Paste an API key before testing." }, { status: 400 });
  }
  const response = await fetch(`${API_BASE_URL}/ai/test_key`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-OpenAI-API-Key": apiKey
    },
    cache: "no-store"
  });
  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: { "Content-Type": response.headers.get("Content-Type") || "application/json" }
  });
}
