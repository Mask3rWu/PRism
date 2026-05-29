"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Project, PullRequestItem, ReviewStatusResponse } from "@/types";

interface Props {
  project: Project;
  initialPRs: PullRequestItem[];
  initialPage: number;
  perPage: number;
}

const STATUS_CONFIG: Record<
  PullRequestItem["review_status"],
  { label: string; className: string }
> = {
  none: {
    label: "Not Reviewed",
    className: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  },
  queued: {
    label: "Queued",
    className: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
  },
  running: {
    label: "Running",
    className: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  },
  succeeded: {
    label: "Succeeded",
    className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  },
  failed: {
    label: "Failed",
    className: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  },
};

const STAGE_LABELS: Record<string, string> = {
  fetching_diff: "Fetching Diff",
  diff_fetched: "Diff Fetched",
  summarizing: "Summarizing",
  summarized: "Summarized",
  analyzing_risks: "Analyzing Risks",
  risks_analyzed: "Risks Analyzed",
  detecting_issues: "Detecting Issues",
  issues_detected: "Issues Detected",
  suggesting_tests: "Generating Tests",
  tests_suggested: "Tests Generated",
  composing_comment: "Composing Comment",
  comment_composed: "Comment Composed",
  writing_back: "Writing to GitHub",
};

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function stageLabel(stage: string | null): string {
  if (!stage) return "";
  return STAGE_LABELS[stage] || stage.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function PRList({ project, initialPRs, initialPage, perPage }: Props) {
  const [prs, setPRs] = useState<PullRequestItem[]>(initialPRs);
  const [page, setPage] = useState(initialPage);
  const [loadingPage, setLoadingPage] = useState(false);
  const [triggeringPRs, setTriggeringPRs] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [reviewStages, setReviewStages] = useState<Record<number, string | null>>({});
  const [reviewErrors, setReviewErrors] = useState<Record<number, string | null>>({});

  const pollingRef = useRef<Record<number, number>>({});
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const startPolling = useCallback(() => {
    stopPolling();

    intervalRef.current = setInterval(async () => {
      const entries = Object.entries(pollingRef.current);
      if (entries.length === 0) {
        stopPolling();
        return;
      }

      for (const [prStr, reviewId] of entries) {
        const prNumber = Number(prStr);
        try {
          const res = await fetch(`/api/reviews/${reviewId}/status`);
          if (!res.ok) continue;
          const data: ReviewStatusResponse = await res.json();

          setReviewStages((prev) => ({ ...prev, [prNumber]: data.stage }));

          if (data.status === "succeeded" || data.status === "failed") {
            const next = { ...pollingRef.current };
            delete next[prNumber];
            pollingRef.current = next;

            const newStatus = data.status as PullRequestItem["review_status"];
            setPRs((prev) =>
              prev.map((pr) =>
                pr.pr_number === prNumber
                  ? { ...pr, review_status: newStatus }
                  : pr
              )
            );

            if (data.status === "failed") {
              setReviewErrors((prev) => ({
                ...prev,
                [prNumber]: data.error_message || "Unknown error",
              }));
            } else {
              setReviewErrors((prev) => {
                const next = { ...prev };
                delete next[prNumber];
                return next;
              });
            }

            if (Object.keys(next).length === 0) {
              stopPolling();
            }
          }
        } catch {
          // ignore polling errors
        }
      }
    }, 3000);
  }, [stopPolling]);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  async function loadPage(newPage: number) {
    setLoadingPage(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/projects/${project.id}/pulls?page=${newPage}&per_page=${perPage}`
      );
      if (!res.ok) {
        setError("Failed to load pull requests");
        return;
      }
      const data = await res.json();
      setPRs(data);
      setPage(newPage);
    } catch {
      setError("Failed to load pull requests");
    } finally {
      setLoadingPage(false);
    }
  }

  async function triggerReview(prNumber: number) {
    setTriggeringPRs((prev) => new Set(prev).add(prNumber));
    setError(null);
    try {
      const res = await fetch(
        `/api/projects/${project.id}/pulls/${prNumber}/review`,
        { method: "POST" }
      );
      if (!res.ok) {
        const data = await res.json();
        setError(data.detail || "Failed to trigger review");
        return;
      }
      const data = await res.json();
      setPRs((prev) =>
        prev.map((pr) =>
          pr.pr_number === prNumber ? { ...pr, review_status: "queued" } : pr
        )
      );
      setReviewErrors((prev) => {
        const next = { ...prev };
        delete next[prNumber];
        return next;
      });
      pollingRef.current = { ...pollingRef.current, [prNumber]: data.id };
      startPolling();
    } catch {
      setError("Failed to trigger review");
    } finally {
      setTriggeringPRs((prev) => {
        const next = new Set(prev);
        next.delete(prNumber);
        return next;
      });
    }
  }

  const isReviewActive = (status: PullRequestItem["review_status"]) =>
    status === "queued" || status === "running";

  return (
    <div>
      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/50 dark:text-red-400">
          {error}
        </div>
      )}

      {prs.length === 0 ? (
        <p className="py-8 text-center text-sm text-zinc-500">
          No open pull requests found.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900">
                <th className="px-4 py-3 text-left font-medium text-zinc-600 dark:text-zinc-400">
                  PR
                </th>
                <th className="px-4 py-3 text-left font-medium text-zinc-600 dark:text-zinc-400">
                  Author
                </th>
                <th className="px-4 py-3 text-left font-medium text-zinc-600 dark:text-zinc-400">
                  Created
                </th>
                <th className="px-4 py-3 text-left font-medium text-zinc-600 dark:text-zinc-400">
                  Branches
                </th>
                <th className="px-4 py-3 text-left font-medium text-zinc-600 dark:text-zinc-400">
                  Status
                </th>
                <th className="px-4 py-3 text-right font-medium text-zinc-600 dark:text-zinc-400">
                  Action
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
              {prs.map((pr) => {
                const status = STATUS_CONFIG[pr.review_status];
                const active = isReviewActive(pr.review_status);
                const triggering = triggeringPRs.has(pr.pr_number);
                const stage = reviewStages[pr.pr_number];
                const reviewError = reviewErrors[pr.pr_number];

                return (
                  <tr
                    key={pr.pr_number}
                    className="bg-white transition-colors hover:bg-zinc-50 dark:bg-zinc-950 dark:hover:bg-zinc-900"
                  >
                    <td className="px-4 py-3">
                      <span className="font-medium text-zinc-900 dark:text-zinc-100">
                        #{pr.pr_number}
                      </span>{" "}
                      <span className="text-zinc-600 dark:text-zinc-400">
                        {pr.title}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-zinc-600 dark:text-zinc-400">
                      {pr.author}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-zinc-500 dark:text-zinc-500">
                      {formatDate(pr.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-zinc-500 dark:text-zinc-500">
                        {pr.head_branch}
                      </span>
                      <span className="mx-1 text-zinc-400">→</span>
                      <span className="text-zinc-500 dark:text-zinc-500">
                        {pr.base_branch}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-col gap-1">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium w-fit ${status.className}`}
                        >
                          {status.label}
                        </span>
                        {active && stage && (
                          <span className="text-xs text-zinc-400 dark:text-zinc-500 animate-pulse">
                            {stageLabel(stage)}
                          </span>
                        )}
                        {reviewError && (
                          <span className="text-xs text-red-500 dark:text-red-400">
                            {reviewError}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => triggerReview(pr.pr_number)}
                        disabled={active || triggering}
                        className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {triggering ? (
                          "Starting..."
                        ) : active ? (
                          "In Progress"
                        ) : pr.review_status === "failed" ? (
                          "Retry"
                        ) : (
                          "Trigger Review"
                        )}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4 flex items-center justify-between">
        <button
          type="button"
          onClick={() => loadPage(page - 1)}
          disabled={page <= 1 || loadingPage}
          className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 transition-colors hover:bg-zinc-100 disabled:opacity-50 disabled:cursor-not-allowed dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-900"
        >
          Previous
        </button>
        <span className="text-sm text-zinc-500">Page {page}</span>
        <button
          type="button"
          onClick={() => loadPage(page + 1)}
          disabled={prs.length < perPage || loadingPage}
          className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 transition-colors hover:bg-zinc-100 disabled:opacity-50 disabled:cursor-not-allowed dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-900"
        >
          Next
        </button>
      </div>
    </div>
  );
}
