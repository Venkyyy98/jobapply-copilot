export type AggregateCounts = {
  saved: number;
  analyzed: number;
  generated_docs: number;
  applied: number;
  outreach_started: number;
  interested: number;
};

export type PublicJobFeedItem = {
  id: number;
  slug: string;
  source_job_id?: number | null;
  source_url: string;
  title: string;
  company: string;
  location: string;
  work_mode: string;
  role_family: string;
  page_title: string;
  summary: string;
  job_text_excerpt: string;
  fit_score?: number | null;
  fit_reasons: string[];
  tailoring_plan: string[];
  suggested_bullets: string[];
  suggested_project_ids: string[];
  matched_keywords: string[];
  missing_keywords: string[];
  keyword_coverage_pct: number;
  compliance_ready: boolean;
  compliance_notes: string[];
  aggregate_counts: AggregateCounts;
  created_at: string;
  updated_at: string;
};

export type PublicJobsResponse = {
  items: PublicJobFeedItem[];
  available_role_families: string[];
  total: number;
};

export type PrivateJobFeedItem = PublicJobFeedItem & {
  user_action: string;
  user_action_metadata: Record<string, unknown>;
  action_updated_at: string;
};

export type UserJobListResponse = {
  items: PrivateJobFeedItem[];
  total: number;
};

export type UserStatsResponse = {
  user: {
    email: string;
    name: string;
    image_url: string;
  };
  counts: Record<string, number>;
  recent_activity: Array<{
    title: string;
    company: string;
    action_type: string;
    updated_at: string;
  }>;
};
