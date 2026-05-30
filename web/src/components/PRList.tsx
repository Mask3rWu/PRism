"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Project, PullRequestItem, PaginatedPRs, ReviewStatusResponse } from "@/types";

interface Props {
  project: Project;
  initialPRs: PullRequestItem[];
  initialTotal: number;
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
    label: "Reviewed",
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

const SORT_OPTIONS = [
  { value: "created-desc", label: "Newest" },
  { value: "created-asc", label: "Oldest" },
  { value: "updated-desc", label: "Recently Updated" },
  { value: "updated-asc", label: "Least Recently Updated" },
] as const;

function stageLabel(stage: string | null): string {
  if (!stage) return "";
  return STAGE_LABELS[stage] || stage.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = now - then;

  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;

  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;

  return `${Math.floor(months / 12)}y ago`;
}

function getContrastColor(hex: string): string {
  const r = parseInt(hex.slice(0, 2), 16);
  const g = parseInt(hex.slice(2, 4), 16);
  const b = parseInt(hex.slice(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6 ? "#1a1a1a" : "#ffffff";
}

function prStateIcon(pr: PullRequestItem): string | null {
  if (pr.state === "open" || !pr.state) return null;
  return pr.merged_at ? "merged" : "closed";
}

export default function PRList({ project, initialPRs, initialTotal, initialPage, perPage }: Props) {
  const [prs, setPRs] = useState<PullRequestItem[]>(initialPRs);
  const [total, setTotal] = useState(initialTotal);
  const [page, setPage] = useState(initialPage);
  const [loadingPage, setLoadingPage] = useState(false);
  const [triggeringPRs, setTriggeringPRs] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [reviewStages, setReviewStages] = useState<Record<number, string | null>>({});
  const [reviewErrors, setReviewErrors] = useState<Record<number, string | null>>({});

  // Filter state
  const [stateFilter, setStateFilter] = useState<"open" | "closed">("open");
  const [sortValue, setSortValue] = useState("created-desc");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [author, setAuthor] = useState("");
  const [authorInput, setAuthorInput] = useState("");
  const [selectedLabels, setSelectedLabels] = useState<string[]>([]);
  const [prStatusFilter, setPrStatusFilter] = useState<string[]>([]);
  const [showMoreFilters, setShowMoreFilters] = useState(false);

  const pollingRef = useRef<Record<number, number>>({});
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const authorDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Refs for latest filter values — avoids stale closure in setTimeout callbacks
  const stateFilterRef = useRef(stateFilter);
  stateFilterRef.current = stateFilter;
  const sortValueRef = useRef(sortValue);
  sortValueRef.current = sortValue;
  const searchRef = useRef(search);
  searchRef.current = search;
  const authorRef = useRef(author);
  authorRef.current = author;
  const selectedLabelsRef = useRef(selectedLabels);
  selectedLabelsRef.current = selectedLabels;
  const prStatusFilterRef = useRef(prStatusFilter);
  prStatusFilterRef.current = prStatusFilter;

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

  // Debounce search
  useEffect(() => {
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    searchDebounceRef.current = setTimeout(() => {
      setSearch(searchInput);
    }, 400);
    return () => {
      if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    };
  }, [searchInput]);

  // Debounce author
  useEffect(() => {
    if (authorDebounceRef.current) clearTimeout(authorDebounceRef.current);
    authorDebounceRef.current = setTimeout(() => {
      setAuthor(authorInput);
    }, 400);
    return () => {
      if (authorDebounceRef.current) clearTimeout(authorDebounceRef.current);
    };
  }, [authorInput]);

  // Reload when debounced search/author settle
  const filterMountedRef = useRef(false);
  useEffect(() => {
    if (!filterMountedRef.current) {
      filterMountedRef.current = true;
      return;
    }
    loadPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, author]);

  function buildQueryParams(newPage: number): string {
    const [sort, direction] = sortValueRef.current.split("-");
    const params = new URLSearchParams({
      page: String(newPage),
      per_page: String(perPage),
      state: stateFilterRef.current,
      search: searchRef.current,
      author: authorRef.current,
      sort,
      direction,
    });
    selectedLabelsRef.current.forEach((l) => params.append("labels", l));
    prStatusFilterRef.current.forEach((s) => params.append("pr_status", s));
    return params.toString();
  }

  async function loadPage(newPage: number) {
    setLoadingPage(true);
    setError(null);
    try {
      const qs = buildQueryParams(newPage);
      const res = await fetch(`/api/projects/${project.id}/pulls?${qs}`);
      if (!res.ok) {
        setError("Failed to load pull requests");
        return;
      }
      const data: PaginatedPRs = await res.json();
      setPRs(data.items);
      setTotal(data.total);
      setPage(data.page);
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

  // Pagination helpers
  const totalPages = total > 0 ? Math.max(1, Math.ceil(total / perPage)) : page + (prs.length >= perPage ? 1 : 0);
  const startItem = (page - 1) * perPage + 1;
  const endItem = Math.min(page * perPage, (page - 1) * perPage + prs.length);

  function pageNumbers(): (number | "ellipsis")[] {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }
    const pages: (number | "ellipsis")[] = [1];
    if (page > 3) pages.push("ellipsis");
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
      pages.push(i);
    }
    if (page < totalPages - 2) pages.push("ellipsis");
    pages.push(totalPages);
    return pages;
  }

  return (
    <div>
      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/50 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Filter Bar */}
      <div className="mb-4 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          {/* State tabs */}
          <div className="inline-flex rounded-lg border border-zinc-200 dark:border-zinc-800 p-0.5">
            {(["open", "closed"] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => { setStateFilter(s); setTimeout(() => loadPage(1), 0); }}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  stateFilter === s
                    ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-700 dark:text-zinc-100"
                    : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                }`}
              >
                {s === "open" ? "Open" : "Closed"}
              </button>
            ))}
          </div>

          {/* Sort dropdown */}
          <select
            value={sortValue}
            onChange={(e) => { setSortValue(e.target.value); setTimeout(() => loadPage(1), 0); }}
            className="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 text-sm text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400"
          >
            {SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <svg
              className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-zinc-400"
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search PRs..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full rounded-lg border border-zinc-200 bg-white py-1.5 pl-9 pr-3 text-sm text-zinc-900 placeholder-zinc-400 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </div>

          {/* More filters toggle */}
          <button
            type="button"
            onClick={() => setShowMoreFilters(!showMoreFilters)}
            className={`inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm transition-colors ${
              showMoreFilters
                ? "border-indigo-300 bg-indigo-50 text-indigo-700 dark:border-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400"
                : "border-zinc-200 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-900"
            }`}
          >
            <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
            </svg>
            Filters
            {(author || selectedLabels.length > 0 || prStatusFilter.length > 0) && (
              <span className="ml-0.5 flex size-4 items-center justify-center rounded-full bg-indigo-600 text-[10px] text-white">
                {(author ? 1 : 0) + (selectedLabels.length > 0 ? 1 : 0) + (prStatusFilter.length > 0 ? 1 : 0)}
              </span>
            )}
          </button>
        </div>

        {/* Expandable filters */}
        {showMoreFilters && (
          <div className="flex flex-wrap items-center gap-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900/50">
            {/* Author filter */}
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">Author</label>
              <input
                type="text"
                placeholder="username"
                value={authorInput}
                onChange={(e) => setAuthorInput(e.target.value)}
                className="w-40 rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
              />
            </div>

            {/* Label filter */}
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">Labels</label>
              <input
                type="text"
                placeholder="bug, enhancement..."
                value={selectedLabels.join(", ")}
                onChange={(e) => {
                  const parts = e.target.value.split(",").map((s) => s.trim()).filter(Boolean);
                  setSelectedLabels(parts);
                }}
                onBlur={() => loadPage(1)}
                onKeyDown={(e) => { if (e.key === "Enter") loadPage(1); }}
                className="w-44 rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
              />
            </div>

            {/* PRism review status filter */}
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-500 dark:text-zinc-400">PRism Review</label>
              <div className="flex flex-wrap gap-1">
                {(["none", "queued", "running", "succeeded", "failed"] as const).map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => {
                      setPrStatusFilter((prev) =>
                        prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s]
                      );
                      setTimeout(() => loadPage(1), 0);
                    }}
                    className={`rounded-full px-2 py-0.5 text-xs font-medium transition-colors ${
                      prStatusFilter.includes(s)
                        ? STATUS_CONFIG[s].className + " ring-1 ring-zinc-400"
                        : "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
                    }`}
                  >
                    {STATUS_CONFIG[s].label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* PR List */}
      {prs.length === 0 ? (
        <p className="py-8 text-center text-sm text-zinc-500">
          No pull requests found.
        </p>
      ) : (
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800">
          <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {prs.map((pr) => {
              const status = STATUS_CONFIG[pr.review_status];
              const active = isReviewActive(pr.review_status);
              const triggering = triggeringPRs.has(pr.pr_number);
              const stage = reviewStages[pr.pr_number];
              const reviewError = reviewErrors[pr.pr_number];
              const stateIcon = prStateIcon(pr);

              const githubUrl = `https://github.com/${project.repo_owner}/${project.repo_name}/pull/${pr.pr_number}`;

              return (
                <li
                  key={pr.pr_number}
                  className="bg-white transition-colors hover:bg-zinc-50 dark:bg-zinc-950 dark:hover:bg-zinc-900"
                >
                  {/* Row 1 */}
                  <div className="flex items-center gap-2 px-4 pt-3">
                    {/* State icon for closed PRs */}
                    {stateIcon && (
                      <span
                        className={`inline-flex shrink-0 items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-medium ${
                          stateIcon === "merged"
                            ? "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400"
                            : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                        }`}
                      >
                        {stateIcon === "merged" ? (
                          <svg className="size-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 01.143 1.052l-8 10.5a.75.75 0 01-1.127.075l-4.5-4.5a.75.75 0 011.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 011.05-.143z" clipRule="evenodd" />
                          </svg>
                        ) : (
                          <svg className="size-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
                          </svg>
                        )}
                        {stateIcon}
                      </span>
                    )}
                    {/* Draft badge */}
                    {pr.is_draft && (
                      <span className="inline-flex shrink-0 rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                        Draft
                      </span>
                    )}
                    {/* Title */}
                    <span className="min-w-0 truncate text-sm font-medium text-zinc-900 dark:text-zinc-100">
                      {pr.title}
                    </span>
                    {/* Labels */}
                    {pr.labels.map((lb) => (
                      <span
                        key={lb.name}
                        className="shrink-0 rounded-full px-2 py-0.5 text-xs font-medium"
                        style={{
                          backgroundColor: `#${lb.color}`,
                          color: getContrastColor(lb.color),
                        }}
                      >
                        {lb.name}
                      </span>
                    ))}
                    {/* Spacer */}
                    <div className="flex-1" />
                    {/* Action buttons */}
                    <div className="flex shrink-0 items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() => triggerReview(pr.pr_number)}
                        disabled={active || triggering}
                        className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {triggering
                          ? "Starting..."
                          : active
                          ? "In Progress"
                          : pr.review_status === "failed"
                          ? "Retry"
                          : "Trigger Review"}
                      </button>
                      <a
                        href={githubUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center rounded-lg border border-zinc-200 p-1.5 text-zinc-400 transition-colors hover:border-zinc-300 hover:text-zinc-600 dark:border-zinc-800 dark:hover:border-zinc-700 dark:hover:text-zinc-300"
                        title="View on GitHub"
                      >
                        <svg className="size-3.5" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M11 3a1 1 0 100 2h2.586l-6.293 6.293a1 1 0 101.414 1.414L15 6.414V9a1 1 0 102 0V4a1 1 0 00-1-1h-5z" />
                          <path d="M5 5a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2v-3a1 1 0 10-2 0v3H5V7h3a1 1 0 000-2H5z" />
                        </svg>
                      </a>
                    </div>
                  </div>

                  {/* Row 2 */}
                  <div className="flex items-center gap-2 px-4 pb-3 pt-1 text-xs text-zinc-500 dark:text-zinc-400">
                    <span className="font-medium text-zinc-700 dark:text-zinc-300">
                      #{pr.pr_number}
                    </span>
                    <span>{pr.author}</span>
                    <span>·</span>
                    <span title={pr.created_at}>opened {relativeTime(pr.created_at)}</span>
                    <span>·</span>
                    <span className="min-w-0 max-w-[240px] truncate">{pr.head_branch}</span>
                    {/* Spacer */}
                    <div className="flex-1" />
                    {/* Review status */}
                    <div className="flex shrink-0 items-center gap-1">
                      <span
                        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${status.className}`}
                      >
                        {status.label}
                      </span>
                      {active && stage && (
                        <span className="animate-pulse text-zinc-400 dark:text-zinc-500">
                          {stageLabel(stage)}
                        </span>
                      )}
                      {reviewError && (
                        <span className="text-red-500 dark:text-red-400" title={reviewError}>
                          {reviewError.length > 40 ? reviewError.slice(0, 40) + "…" : reviewError}
                        </span>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Pagination */}
      <div className="mt-4 flex items-center justify-between">
        <span className="text-sm text-zinc-500">
          {prs.length > 0 ? `${startItem}–${endItem} of ${total > 0 ? total : "many"}` : ""}
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => loadPage(page - 1)}
            disabled={page <= 1 || loadingPage}
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 transition-colors hover:bg-zinc-100 disabled:opacity-50 disabled:cursor-not-allowed dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-900"
          >
            Previous
          </button>
          {pageNumbers().map((p, i) =>
            p === "ellipsis" ? (
              <span key={`e-${i}`} className="px-2 text-sm text-zinc-400">…</span>
            ) : (
              <button
                key={p}
                type="button"
                onClick={() => loadPage(p)}
                disabled={loadingPage}
                className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${
                  p === page
                    ? "bg-indigo-600 text-white"
                    : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-900"
                }`}
              >
                {p}
              </button>
            )
          )}
          <button
            type="button"
            onClick={() => loadPage(page + 1)}
            disabled={(prs.length < perPage && total <= page * perPage) || loadingPage}
            className="rounded-lg border border-zinc-200 px-3 py-1.5 text-sm text-zinc-600 transition-colors hover:bg-zinc-100 disabled:opacity-50 disabled:cursor-not-allowed dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-900"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
