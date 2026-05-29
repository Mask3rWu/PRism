export interface Project {
  id: number;
  name: string;
  repo_owner: string;
  repo_name: string;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreatePayload {
  name: string;
  repo_owner: string;
  repo_name: string;
  pat: string;
  description: string;
}

export interface ProjectUpdatePayload {
  description?: string;
  pat?: string;
}

export interface PullRequestItem {
  pr_number: number;
  title: string;
  author: string;
  created_at: string;
  head_branch: string;
  base_branch: string;
  review_status: "none" | "queued" | "running" | "succeeded" | "failed";
}

export interface ReviewStatusResponse {
  id: number;
  status: string;
  stage: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  agent_timings: { agent_name: string; start_time: string; end_time: string | null }[];
}
