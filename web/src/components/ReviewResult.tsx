"use client";

import { useState } from "react";
import { flushSync } from "react-dom";
import type { ReviewDetail, IssueItem, RiskItem, TestSuggestion } from "@/types";

const SEVERITY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

const SEVERITY_STYLES: Record<string, string> = {
  critical:
    "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  high: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  medium:
    "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  low: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
};

const RISK_STYLES: Record<string, string> = {
  high: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  medium:
    "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  low: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
};

const STATUS_STYLES: Record<string, string> = {
  succeeded:
    "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  failed: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  running:
    "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  queued:
    "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
};

const AGENT_LABELS: Record<string, string> = {
  summary: "PR Summary",
  risk_analysis: "Risk Analysis",
  issue_detection: "Issue Detection",
  test_suggestions: "Test Suggestions",
  security_review: "Security Review",
  performance_review: "Performance Review",
  business_compliance_review: "Business & Compliance Review",
  aggregate_results: "Result Aggregation",
  comment_compose: "Comment Compose",
};

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes}m ${remainingSeconds}s`;
}

function agentDuration(
  timing: NonNullable<ReviewDetail["agent_timings"]>[number]
): string {
  if (!timing.end_time) return "—";
  const start = new Date(timing.start_time).getTime();
  const end = new Date(timing.end_time).getTime();
  return formatDuration(end - start);
}

function overallDuration(review: ReviewDetail): string | null {
  if (!review.started_at || !review.completed_at) return null;
  const start = new Date(review.started_at).getTime();
  const end = new Date(review.completed_at).getTime();
  return formatDuration(end - start);
}

function CollapsibleSection({
  title,
  icon,
  defaultOpen = true,
  badge,
  children,
}: {
  title: string;
  icon: string;
  defaultOpen?: boolean;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-5 py-4 bg-zinc-50 dark:bg-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{icon}</span>
          <span className="font-semibold text-zinc-900 dark:text-zinc-100">
            {title}
          </span>
          {badge}
        </div>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className={`size-5 text-zinc-400 transition-transform ${open ? "rotate-180" : ""}`}
        >
          <path
            fillRule="evenodd"
            d="M5.22 8.22a.75.75 0 011.06 0L10 11.94l3.72-3.72a.75.75 0 111.06 1.06l-4.25 4.25a.75.75 0 01-1.06 0L5.22 9.28a.75.75 0 010-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </button>
      {open && (
        <div className="border-t border-zinc-200 dark:border-zinc-800 px-5 py-4">
          {children}
        </div>
      )}
    </div>
  );
}

export default function ReviewResult({ review, projectPermission }: { review: ReviewDetail; projectPermission?: string }) {
  const [issueSortAsc, setIssueSortAsc] = useState(false);
  const [postingComment, setPostingComment] = useState(false);
  const [commentPosted, setCommentPosted] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);
  const [selectedExpert, setSelectedExpert] = useState<string | null>(null);

  async function handlePostComment() {
    flushSync(() => {
      setPostingComment(true);
      setCommentError(null);
    });
    try {
      const res = await fetch(`/api/reviews/${review.id}/retry-writeback`, { method: "POST" });
      if (res.ok) {
        setCommentPosted(true);
      } else {
        const data = await res.json().catch(() => ({ detail: "Failed to post comment" }));
        setCommentError(data.detail || "Failed to post comment");
      }
    } catch {
      setCommentError("Failed to post comment");
    } finally {
      setPostingComment(false);
    }
  }

  const canComment = !commentPosted && projectPermission && projectPermission !== "Viewer" && review.status === "succeeded" && review.comment_content && !(review.write_comment && !review.writeback_error);

  // Normalize LLM field name variations
  const summaryResult = review.summary_result && {
    ...review.summary_result,
    files_changed: review.summary_result.files_changed ?? [],
  };
  const rawRisk = review.risk_result as {
    risk_items?: RiskItem[];
    risks?: RiskItem[];
    overall_risk?: string;
  } | null;
  const riskItems: RiskItem[] = rawRisk?.risk_items ?? rawRisk?.risks ?? [];
  const overallRisk: string = rawRisk?.overall_risk
    ?? (riskItems.some((r) => r.level === "high") ? "high"
      : riskItems.some((r) => r.level === "medium") ? "medium"
      : riskItems.length > 0 ? "low"
      : "unknown");
  const riskResult = rawRisk && { ...rawRisk, risk_items: riskItems, overall_risk: overallRisk };

  const rawTest = review.test_result as {
    suggested_tests?: TestSuggestion[];
    tests?: TestSuggestion[];
  } | null;
  const suggestedTests: TestSuggestion[] = rawTest?.suggested_tests ?? rawTest?.tests ?? [];
  const testResult = rawTest && { ...rawTest, suggested_tests: suggestedTests };
  const finalReport = review.final_report;
  const routingPlan = finalReport?.routing_plan ?? review.routing_plan;
  const expertResults = review.expert_results ?? finalReport?.experts ?? [];
  const activeExpert = expertResults.find((expert) => expert.agent === selectedExpert)
    ?? expertResults[0];

  const statusStyle =
    STATUS_STYLES[review.status] ||
    "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400";

  function sortedIssues(issues: IssueItem[]): IssueItem[] {
    const sorted = [...issues].sort((a, b) => {
      const aOrder =
        SEVERITY_ORDER[a.severity] ?? 99;
      const bOrder =
        SEVERITY_ORDER[b.severity] ?? 99;
      return issueSortAsc ? aOrder - bOrder : bOrder - aOrder;
    });
    return sorted;
  }

  const duration = overallDuration(review);

  return (
    <div className="mt-4 space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
            Review #{review.id}
          </h1>
          <span
            className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${statusStyle}`}
          >
            {review.status.charAt(0).toUpperCase() + review.status.slice(1)}
          </span>
        </div>
        <div className="mt-1 flex items-center gap-3 text-sm text-zinc-500 dark:text-zinc-400">
          <span>
            PR #{review.pr_number}: {review.pr_title}
          </span>
        </div>
        {duration && (
          <p className="mt-1 text-sm text-zinc-400 dark:text-zinc-500">
            Total duration: {duration}
            {review.completed_at && (
              <> · Completed {formatDate(review.completed_at)}</>
            )}
          </p>
        )}
      </div>

      {/* Error message */}
      {review.error_message && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/50 dark:text-red-400">
          <span className="font-medium">Error: </span>
          {review.error_message}
        </div>
      )}

      {/* Writeback error */}
      {review.writeback_error && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-400">
          <span className="font-medium">Writeback: </span>
          {review.writeback_error}
        </div>
      )}

      {/* Comment button */}
      {canComment && (
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handlePostComment}
            disabled={postingComment || commentPosted}
            className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {postingComment ? "Commenting..." : "Comment on GitHub"}
          </button>
          {commentError && (
            <span className="text-xs text-red-600 dark:text-red-400">{commentError}</span>
          )}
        </div>
      )}

      {/* Not started / in progress */}
      {(review.status === "queued" || review.status === "running") && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-700 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-400">
          {review.status === "queued"
            ? "Review is queued and will start shortly."
            : `Review in progress — current stage: ${review.stage || "..."}`}
        </div>
      )}

      {/* PR Summary */}
      {summaryResult && (
        <CollapsibleSection title="PR Summary" icon="📋">
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
                Overview
              </h3>
              <p className="mt-1 text-sm text-zinc-900 dark:text-zinc-100">
                {summaryResult.overview}
              </p>
            </div>
            {summaryResult.scope.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
                  Scope
                </h3>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {summaryResult.scope.map((s) => (
                    <span
                      key={s}
                      className="inline-flex rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                    >
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {summaryResult.key_changes.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
                  Key Changes
                </h3>
                <ul className="mt-1 list-inside list-disc space-y-0.5 text-sm text-zinc-700 dark:text-zinc-300">
                  {summaryResult.key_changes.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
            )}
            {summaryResult.files_changed?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
                  Files Changed
                </h3>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {summaryResult.files_changed.map((f) => (
                    <code
                      key={f}
                      className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs font-mono text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                    >
                      {f}
                    </code>
                  ))}
                </div>
              </div>
            )}
          </div>
        </CollapsibleSection>
      )}

      {/* Dynamic routing */}
      {finalReport && (
        <CollapsibleSection
          title="Dynamic Review Plan"
          icon="Route"
          defaultOpen={false}
        >
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400">Selected Experts</h3>
              <div className="mt-2 flex flex-wrap gap-2">
                {(routingPlan?.selected_agents ?? []).map((agent) => (
                  <span key={agent} className="rounded bg-zinc-100 px-2 py-1 text-xs text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                    {AGENT_LABELS[agent] ?? agent}
                  </span>
                ))}
              </div>
              {(routingPlan?.selected_agents ?? []).map((agent) => (
                <p key={`${agent}-reason`} className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                  <span className="font-medium text-zinc-700 dark:text-zinc-300">{AGENT_LABELS[agent] ?? agent}: </span>
                  {(routingPlan?.reasons?.[agent] ?? []).join(" ")}
                </p>
              ))}
            </div>
          </div>
        </CollapsibleSection>
      )}

      {/* Findings returned by the dynamically selected experts */}
      {expertResults.length > 0 && (
        <CollapsibleSection
          title="Expert Findings"
          icon="Results"
          badge={
            <span className="inline-flex rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
              {expertResults.reduce((count, expert) => count + expert.findings.length, 0)} findings
            </span>
          }
        >
          <div role="tablist" aria-label="Expert review results" className="flex gap-1 overflow-x-auto border-b border-zinc-200 pb-2 dark:border-zinc-800">
            {expertResults.map((expert) => (
              <button
                key={expert.agent}
                id={`expert-tab-${expert.agent}`}
                type="button"
                role="tab"
                aria-selected={activeExpert?.agent === expert.agent}
                aria-controls={`expert-panel-${expert.agent}`}
                onClick={() => setSelectedExpert(expert.agent)}
                className={`shrink-0 border-b-2 px-3 py-2 text-xs font-medium transition-colors ${
                  activeExpert?.agent === expert.agent
                    ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
                    : "border-transparent text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
                }`}
              >
                {expert.label || AGENT_LABELS[expert.agent] || expert.agent}
                <span className="ml-1.5 text-zinc-400 dark:text-zinc-500">{expert.findings.length}</span>
              </button>
            ))}
          </div>

          {activeExpert && (
            <section
              id={`expert-panel-${activeExpert.agent}`}
              role="tabpanel"
              aria-labelledby={`expert-tab-${activeExpert.agent}`}
              className="pt-4"
            >
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                  {activeExpert.label || AGENT_LABELS[activeExpert.agent] || activeExpert.agent}
                </h3>
                {activeExpert.focus && (
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">
                    {activeExpert.focus}
                  </span>
                )}
              </div>

              {activeExpert.routing_reasons.length > 0 && (
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  {activeExpert.routing_reasons.join(" ")}
                </p>
              )}

              {activeExpert.findings.length === 0 ? (
                <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">
                  No findings reported.
                </p>
              ) : (
                <div className="mt-3 space-y-4">
                  {activeExpert.findings.map((finding, index) => (
                    <article
                      key={`${finding.file}-${finding.line_number}-${finding.title}-${index}`}
                      className="border-l-2 border-zinc-200 pl-3 dark:border-zinc-700"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_STYLES[finding.severity] || "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"}`}
                        >
                          {finding.severity.toUpperCase()}
                        </span>
                        <h4 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                          {finding.title}
                        </h4>
                      </div>

                      <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">
                        {finding.reason}
                      </p>

                      <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                        {finding.file}
                        {finding.line_number ? `:${finding.line_number}` : ""}
                        {finding.category ? ` - ${finding.category}` : ""}
                        {finding.confidence ? ` - ${finding.confidence} confidence` : ""}
                      </p>

                      {finding.evidence && (
                        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded bg-zinc-100 px-2 py-1.5 text-xs text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
                          {finding.evidence}
                        </pre>
                      )}

                      {finding.fix_suggestion && (
                        <p className="mt-2 text-sm text-zinc-700 dark:text-zinc-300">
                          <span className="font-medium text-zinc-900 dark:text-zinc-100">Fix: </span>
                          {finding.fix_suggestion}
                        </p>
                      )}

                      {finding.verification && (
                        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                          <span className="font-medium text-zinc-700 dark:text-zinc-300">Verify: </span>
                          {finding.verification}
                        </p>
                      )}
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}
        </CollapsibleSection>
      )}

      {/* Risk Analysis */}
      {riskResult && (
        <CollapsibleSection
          title="Risk Analysis"
          icon="⚠️"
          badge={
            riskResult.overall_risk && (
              <span
                className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${RISK_STYLES[riskResult.overall_risk] || "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"}`}
              >
                {riskResult.overall_risk.toUpperCase()}
              </span>
            )
          }
          defaultOpen={
            riskResult.overall_risk === "high" ||
            riskResult.overall_risk === "medium"
          }
        >
          {riskResult.risk_items.length === 0 ? (
            <p className="text-sm text-zinc-500">No risks identified.</p>
          ) : (
            <div className="space-y-3">
              {riskResult.risk_items.map((item, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-3"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${RISK_STYLES[item.level] || "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"}`}
                    >
                      {item.level.toUpperCase()}
                    </span>
                    <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {item.reason}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500 dark:text-zinc-400">
                    <span>
                      <span className="font-medium">File:</span> {item.file}
                    </span>
                    {item.code_segment && (
                      <code className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400 max-w-full truncate">
                        {item.code_segment}
                      </code>
                    )}
                  </div>
                  {item.suggestion && (
                    <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                      <span className="font-medium">Suggestion: </span>
                      {item.suggestion}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </CollapsibleSection>
      )}

      {/* Issue Detection */}
      {review.issue_result && (
        <CollapsibleSection
          title="Issue Detection"
          icon="🐛"
          badge={
            <span className="inline-flex rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
              {review.issue_result.issues.length}
            </span>
          }
          defaultOpen={
            (review.issue_result.issues ?? []).length > 0
          }
        >
          {review.issue_result.issues.length === 0 ? (
            <p className="text-sm text-zinc-500">No issues detected.</p>
          ) : (
            <div>
              <div className="mb-3 flex items-center justify-end">
                <button
                  type="button"
                  onClick={() => setIssueSortAsc(!issueSortAsc)}
                  className="inline-flex items-center gap-1 rounded-lg border border-zinc-200 px-2.5 py-1 text-xs text-zinc-600 transition-colors hover:bg-zinc-100 dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-900"
                >
                  Severity {issueSortAsc ? "↑" : "↓"}
                </button>
              </div>
              <div className="space-y-2">
                {sortedIssues(review.issue_result.issues).map((issue, i) => (
                  <div
                    key={i}
                    className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-3"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${SEVERITY_STYLES[issue.severity] || "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"}`}
                      >
                        {issue.severity.toUpperCase()}
                      </span>
                      <span className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                        {issue.description}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-500 dark:text-zinc-400">
                      <span>
                        <span className="font-medium">File:</span> {issue.file}
                        {issue.line ? `:${issue.line}` : ""}
                      </span>
                    </div>
                    {issue.suggestion && (
                      <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                        <span className="font-medium">Fix: </span>
                        {issue.suggestion}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </CollapsibleSection>
      )}

      {/* Test Suggestions */}
      {testResult && (
        <CollapsibleSection
          title="Test Suggestions"
          icon="🧪"
          badge={
            <span className="inline-flex rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
              {testResult.suggested_tests.length}
            </span>
          }
        >
          {testResult.suggested_tests.length === 0 ? (
            <p className="text-sm text-zinc-500">No test suggestions.</p>
          ) : (
            <div className="space-y-2">
              {testResult.suggested_tests.map((test, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-zinc-200 dark:border-zinc-800 p-3 flex items-start justify-between gap-3"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                        {test.target}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-zinc-900 dark:text-zinc-100">
                      {test.scenario}
                    </p>
                  </div>
                  <span
                    className={`inline-flex shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                      test.priority === "high"
                        ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                        : test.priority === "medium"
                          ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
                          : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                    }`}
                  >
                    {test.priority}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CollapsibleSection>
      )}

      {/* Agent Timings */}
      {review.agent_timings.length > 0 && (
        <CollapsibleSection
          title="Agent Timings"
          icon="⏱️"
          defaultOpen={false}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-200 dark:border-zinc-800">
                  <th className="py-2 text-left font-medium text-zinc-500 dark:text-zinc-400">
                    Agent
                  </th>
                  <th className="py-2 text-right font-medium text-zinc-500 dark:text-zinc-400">
                    Duration
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/50">
                {review.agent_timings.map((t) => (
                  <tr key={t.agent_name}>
                    <td className="py-2 text-zinc-700 dark:text-zinc-300">
                      {AGENT_LABELS[t.agent_name] || t.agent_name}
                    </td>
                    <td className="py-2 text-right font-mono text-xs text-zinc-500 dark:text-zinc-400">
                      {agentDuration(t)}
                    </td>
                  </tr>
                ))}
                {duration && (
                  <tr className="border-t border-zinc-200 dark:border-zinc-800">
                    <td className="py-2 font-medium text-zinc-900 dark:text-zinc-100">
                      Total
                    </td>
                    <td className="py-2 text-right font-mono text-xs font-medium text-zinc-700 dark:text-zinc-300">
                      {duration}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      )}
    </div>
  );
}
