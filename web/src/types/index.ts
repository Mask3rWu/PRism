export interface Project {
  id: number;
  name: string;
  repo_owner: string;
  repo_name: string;
  description: string;
  tags: string[];
  is_favorite: boolean;
  permission: string;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreatePayload {
  name: string;
  repo_owner: string;
  repo_name: string;
  description: string;
  permission: string;
}

export interface ProjectUpdatePayload {
  name?: string;
  description?: string;
  tags?: string[];
  is_favorite?: boolean;
}

export interface PaginatedProjects {
  items: Project[];
  total: number;
  page: number;
  per_page: number;
}

export interface Settings {
  has_pat: boolean;
}

export interface GitHubRepoItem {
  full_name: string;
  owner: string;
  name: string;
  private: boolean;
  description: string | null;
  html_url: string;
  permission: string;
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

export interface AgentTimingItem {
  agent_name: string;
  start_time: string;
  end_time: string | null;
}

export interface ReviewStatusResponse {
  id: number;
  status: string;
  stage: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  agent_timings: AgentTimingItem[];
}

export interface SummaryResult {
  overview: string;
  scope: string[];
  key_changes: string[];
  files_changed: string[];
}

export interface RiskItem {
  level: string;
  reason: string;
  file: string;
  code_segment: string;
  suggestion?: string;
}

export interface RiskResult {
  risk_items: RiskItem[];
  overall_risk: string;
}

export interface IssueItem {
  severity: string;
  description: string;
  file: string;
  line: number;
  suggestion?: string;
}

export interface IssueResult {
  issues: IssueItem[];
}

export interface TestSuggestion {
  target: string;
  scenario: string;
  priority: string;
}

export interface TestResult {
  suggested_tests: TestSuggestion[];
}

export interface ReviewDetail {
  id: number;
  project_id: number;
  pr_number: number;
  pr_title: string;
  status: string;
  stage: string | null;
  error_message: string | null;
  summary_result: SummaryResult | null;
  risk_result: RiskResult | null;
  issue_result: IssueResult | null;
  test_result: TestResult | null;
  comment_content: string | null;
  writeback_error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  agent_timings: AgentTimingItem[];
}
