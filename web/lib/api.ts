import "@/lib/root-env";

import { getServerSession } from "next-auth";

import { authOptions } from "@/lib/auth";
import type {
  ExtensionTokenResponse,
  PublicJobFeedItem,
  PublicJobsResponse,
  UserProfileResponse,
  UserJobListResponse,
  UserStatsResponse
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8787";

function buildUrl(path: string, params?: URLSearchParams) {
  const url = new URL(path, API_BASE_URL);
  if (params) {
    url.search = params.toString();
  }
  return url.toString();
}

async function apiFetch<T>(path: string, init?: RequestInit, includeAuthHeaders = false): Promise<T> {
  const headers = new Headers(init?.headers || {});
  if (process.env.JAC_TOKEN) {
    headers.set("X-JAC-TOKEN", process.env.JAC_TOKEN);
  }
  if (includeAuthHeaders) {
    const session = await getServerSession(authOptions);
    if (!session?.user?.email) {
      throw new Error("Authentication required");
    }
    headers.set("X-WEB-USER-EMAIL", session.user.email);
    headers.set("X-WEB-USER-NAME", session.user.name || "");
    headers.set("X-WEB-USER-IMAGE", session.user.image || "");
  }
  const response = await fetch(buildUrl(path), {
    ...init,
    headers,
    cache: "no-store"
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `API request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function fetchPublicJobs(filters?: {
  q?: string;
  role_family?: string;
  location?: string;
  fit_min?: string;
  fit_max?: string;
  sort?: string;
}) {
  const params = new URLSearchParams();
  Object.entries(filters || {}).forEach(([key, value]) => {
    if (value) {
      params.set(key, value);
    }
  });
  return apiFetch<PublicJobsResponse>(`/web/jobs?${params.toString()}`);
}

export async function fetchPublicJob(id: string) {
  return apiFetch<PublicJobFeedItem>(`/web/jobs/${id}`);
}

export async function fetchMyJobs(filters: { q?: string; status?: string; date_from?: string; date_to?: string } | string = "") {
  const params = new URLSearchParams();
  const normalized = typeof filters === "string" ? { status: filters } : filters;
  Object.entries(normalized).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  return apiFetch<UserJobListResponse>(`/web/me/jobs?${params.toString()}`, undefined, true);
}

export async function fetchMyStats() {
  return apiFetch<UserStatsResponse>("/web/me/stats", undefined, true);
}

export async function fetchMyProfile() {
  return apiFetch<UserProfileResponse>("/web/me/profile", undefined, true);
}

export async function createExtensionToken() {
  return apiFetch<ExtensionTokenResponse>("/web/me/extension-token", { method: "POST" }, true);
}
