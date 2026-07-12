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

export interface LLMSettings {
  provider: string;
  endpoint: string;
  model: string;
  has_api_key: boolean;
}

export interface Settings {
  has_pat: boolean;
  llm: LLMSettings | null;
  review_count: number;
  max_free_reviews: number;
  agent_language: "zh" | "en";
  enabled_agents: string[];
}

export interface LLMSettingsUpdatePayload {
  provider?: string;
  endpoint?: string;
  model?: string;
  api_key?: string;
}

export interface SettingsUpdatePayload {
  pat?: string;
  llm?: LLMSettingsUpdatePayload;
  agent_language?: "zh" | "en";
  enabled_agents?: string[];
}

export interface CallLogItem {
  id: number;
  call_type: "llm" | "github";
  endpoint: string;
  model: string | null;
  request_summary: string | null;
  latency_ms: number;
  status_code: number | null;
  error_message: string | null;
  retry_count: number;
  created_at: string;
}

export interface PaginatedCallLogs {
  items: CallLogItem[];
  total: number;
  page: number;
  per_page: number;
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

export interface LabelItem {
  name: string;
  color: string;
}

export interface PullRequestItem {
  pr_number: number;
  title: string;
  author: string;
  created_at: string;
  updated_at: string | null;
  head_branch: string;
  base_branch: string;
  review_status: "none" | "queued" | "running" | "succeeded" | "failed";
  review_id: number | null;
  comment_posted: boolean;
  state: "open" | "closed";
  labels: LabelItem[];
  is_draft: boolean;
  merged_at: string | null;
}

export interface ReviewStats {
  total: number;
  succeeded: number;
  failed: number;
  in_progress: number;
}

export interface PaginatedPRs {
  items: PullRequestItem[];
  total: number;
  page: number;
  per_page: number;
  review_stats: ReviewStats | null;
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
  write_comment: boolean;
  writeback_error: string | null;
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

export interface RoutingPlan {
  changed_files: string[];
  selected_agents: string[];
  reasons: Record<string, string[]>;
}

export interface ReviewFinding {
  id: string;
  agent: string;
  severity: string;
  category: string;
  title: string;
  reason: string;
  file: string;
  line_number: number;
  evidence: string;
  fix_suggestion: string;
  verification: string;
  confidence: string;
}

export interface FixSuggestion {
  finding_id: string;
  file: string;
  line_number: number;
  suggestion: string;
  verification: string;
}

export interface ExpertResult {
  agent: string;
  label: string;
  focus: string;
  routing_reasons: string[];
  findings: ReviewFinding[];
}

export interface FinalReport {
  routing_plan: RoutingPlan;
  experts: ExpertResult[];
  findings: ReviewFinding[];
  fix_suggestions: FixSuggestion[];
  summary: {
    total_findings: number;
    by_severity: Record<string, number>;
  };
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
  routing_plan: RoutingPlan | null;
  expert_results: ExpertResult[] | null;
  final_report: FinalReport | null;
  comment_content: string | null;
  writeback_error: string | null;
  write_comment: boolean;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  agent_timings: AgentTimingItem[];
}
