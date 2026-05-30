"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { GitHubRepoItem } from "@/types";

interface Props {
  open: boolean;
  initialTab: "personal" | "public";
  onClose: () => void;
  existingRepos: Set<string>;
}

type Step = "select" | "confirm";

export default function AddRepoModal({ open, initialTab, onClose, existingRepos }: Props) {
  const router = useRouter();
  const [tab, setTab] = useState<"personal" | "public">(initialTab);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Personal repo state
  const [repos, setRepos] = useState<GitHubRepoItem[]>([]);
  const [reposLoading, setReposLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedRepo, setSelectedRepo] = useState<GitHubRepoItem | null>(null);

  // Public repo state
  const [url, setUrl] = useState("");
  const [validating, setValidating] = useState(false);
  const [validatedRepo, setValidatedRepo] = useState<{ owner: string; repo_name: string } | null>(null);

  // Confirm form state
  const [step, setStep] = useState<Step>("select");
  const [projectName, setProjectName] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    if (!open) {
      setError("");
      setLoading(false);
      setSelectedRepo(null);
      setValidatedRepo(null);
      setUrl("");
      setSearch("");
      setStep("select");
      return;
    }
    setTab(initialTab);
  }, [open, initialTab]);

  // Fetch repos when personal tab opens
  useEffect(() => {
    if (!open || tab !== "personal") return;
    setReposLoading(true);
    setError("");
    fetch("/api/github/repos")
      .then((res) => {
        if (!res.ok) return res.json().then((d) => Promise.reject(d.detail));
        return res.json();
      })
      .then((data: GitHubRepoItem[]) => setRepos(data))
      .catch((e) => setError(typeof e === "string" ? e : "Failed to load repositories"))
      .finally(() => setReposLoading(false));
  }, [open, tab]);

  const filteredRepos = repos.filter(
    (r) =>
      r.name.toLowerCase().includes(search.toLowerCase()) ||
      r.full_name.toLowerCase().includes(search.toLowerCase()),
  );

  const handleSelectRepo = (repo: GitHubRepoItem) => {
    setSelectedRepo(repo);
    setProjectName(repo.name);
    setDescription(repo.description || "");
    setStep("confirm");
  };

  const handleValidateUrl = useCallback(async () => {
    if (!url.trim()) {
      setError("Please enter a GitHub URL");
      return;
    }
    setValidating(true);
    setError("");
    try {
      const res = await fetch("/api/github/validate-repo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      });
      if (res.ok) {
        const data = await res.json();
        setValidatedRepo(data);
        setProjectName(data.repo_name);
        setStep("confirm");
      } else {
        const body = await res.json();
        setError(body.detail || "Validation failed");
      }
    } catch {
      setError("Network error. Is the backend running?");
    } finally {
      setValidating(false);
    }
  }, [url]);

  const handleCreate = useCallback(async () => {
    setLoading(true);
    setError("");

    const owner =
      tab === "personal"
        ? selectedRepo!.owner
        : validatedRepo!.owner;
    const repoName =
      tab === "personal"
        ? selectedRepo!.name
        : validatedRepo!.repo_name;

    try {
      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: projectName || repoName,
          repo_owner: owner,
          repo_name: repoName,
          description,
        }),
      });

      if (res.ok) {
        onClose();
        router.refresh();
      } else {
        const body = await res.json();
        setError(body.detail || "Failed to create project");
      }
    } catch {
      setError("Network error. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [tab, selectedRepo, validatedRepo, projectName, description, onClose, router]);

  const handleBack = () => {
    setStep("select");
    setError("");
    setSelectedRepo(null);
    setValidatedRepo(null);
  };

  // Reset when switching tabs
  const switchTab = (t: "personal" | "public") => {
    setTab(t);
    setStep("select");
    setError("");
    setSelectedRepo(null);
    setValidatedRepo(null);
    setUrl("");
    setSearch("");
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="relative w-full max-w-lg rounded-xl border border-zinc-200 bg-white p-6 shadow-xl dark:border-zinc-800 dark:bg-zinc-900 max-h-[80vh] flex flex-col">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
        >
          ✕
        </button>
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
          Add Repository
        </h2>

        {/* Tabs */}
        <div className="mt-3 flex gap-1 rounded-lg bg-zinc-100 p-1 dark:bg-zinc-800">
          <button
            type="button"
            onClick={() => switchTab("personal")}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              tab === "personal"
                ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-700 dark:text-zinc-100"
                : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
            }`}
          >
            Personal Repos
          </button>
          <button
            type="button"
            onClick={() => switchTab("public")}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              tab === "public"
                ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-700 dark:text-zinc-100"
                : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-200"
            }`}
          >
            Public Repo URL
          </button>
        </div>

        {/* Personal Tab */}
        {tab === "personal" && step === "select" && (
          <div className="mt-3 flex-1 flex flex-col min-h-0">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search repositories..."
              className="w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
            />
            {reposLoading ? (
              <p className="mt-4 text-center text-sm text-zinc-400">Loading repositories...</p>
            ) : filteredRepos.length === 0 ? (
              <p className="mt-4 text-center text-sm text-zinc-400">
                {repos.length === 0 ? "No repositories found." : "No matching repositories."}
              </p>
            ) : (
              <ul className="mt-2 flex-1 overflow-y-auto space-y-1">
                {filteredRepos.map((repo) => {
                  const alreadyAdded = existingRepos.has(repo.full_name);
                  return (
                    <li key={repo.full_name}>
                      <button
                        type="button"
                        onClick={() => !alreadyAdded && handleSelectRepo(repo)}
                        disabled={alreadyAdded}
                        className={`w-full rounded-lg px-3 py-2 text-left transition-colors ${
                          alreadyAdded
                            ? "cursor-not-allowed bg-zinc-100 dark:bg-zinc-800/50"
                            : "hover:bg-zinc-100 dark:hover:bg-zinc-800"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span className={`text-sm font-medium ${
                            alreadyAdded
                              ? "text-zinc-400 dark:text-zinc-500"
                              : "text-zinc-900 dark:text-zinc-100"
                          }`}>
                            {repo.full_name}
                          </span>
                          {alreadyAdded && (
                            <span className="rounded bg-zinc-200 px-1 py-0 text-[10px] text-zinc-500 dark:bg-zinc-700 dark:text-zinc-400">
                              added
                            </span>
                          )}
                          {!alreadyAdded && repo.private && (
                            <span className="rounded border border-zinc-300 px-1 py-0 text-[10px] text-zinc-500 dark:border-zinc-600 dark:text-zinc-400">
                              private
                            </span>
                          )}
                        </div>
                        {repo.description && (
                          <p className={`mt-0.5 text-xs line-clamp-1 ${
                            alreadyAdded
                              ? "text-zinc-400 dark:text-zinc-500"
                              : "text-zinc-500 dark:text-zinc-400"
                          }`}>
                            {repo.description}
                          </p>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}

        {/* Public Tab */}
        {tab === "public" && step === "select" && (
          <div className="mt-3 space-y-3">
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                GitHub Repository URL
              </label>
              <div className="mt-1 flex gap-2">
                <input
                  type="text"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://github.com/owner/repo"
                  className="flex-1 rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                />
                <button
                  type="button"
                  onClick={handleValidateUrl}
                  disabled={validating}
                  className="rounded-lg border border-indigo-300 px-3 py-2 text-sm font-medium text-indigo-600 hover:bg-indigo-50 disabled:opacity-50 transition-colors dark:border-indigo-700 dark:text-indigo-400 dark:hover:bg-indigo-950"
                >
                  {validating ? "Checking..." : "Validate"}
                </button>
              </div>
              <p className="mt-1 text-xs text-zinc-400">
                Only public repositories can be added via URL. Private repos must be added via the Personal tab.
              </p>
            </div>
          </div>
        )}

        {/* Confirm Step (shared) */}
        {step === "confirm" && (
          <div className="mt-3 space-y-3">
            <button
              type="button"
              onClick={handleBack}
              className="text-sm text-indigo-600 hover:text-indigo-500 dark:text-indigo-400"
            >
              &larr; Back
            </button>
            {tab === "personal" && selectedRepo && (
              <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm dark:border-green-800 dark:bg-green-950">
                <p className="font-medium text-green-800 dark:text-green-200">
                  {selectedRepo.full_name}
                </p>
                {selectedRepo.description && (
                  <p className="mt-0.5 text-green-700 dark:text-green-300">
                    {selectedRepo.description}
                  </p>
                )}
              </div>
            )}
            {tab === "public" && validatedRepo && (
              <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm dark:border-green-800 dark:bg-green-950">
                <p className="font-medium text-green-800 dark:text-green-200">
                  {validatedRepo.owner}/{validatedRepo.repo_name}
                </p>
                <p className="mt-0.5 text-green-700 dark:text-green-300">
                  Public repository — validated
                </p>
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Project Name
              </label>
              <input
                type="text"
                value={projectName}
                onChange={(e) => setProjectName(e.target.value)}
                className="mt-1 w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Description
              </label>
              <textarea
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="mt-1 w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
              />
            </div>
          </div>
        )}

        {error && (
          <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
        )}

        {step === "confirm" && (
          <button
            type="button"
            onClick={handleCreate}
            disabled={loading}
            className="mt-3 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Creating..." : "Create Project"}
          </button>
        )}
      </div>
    </div>
  );
}
