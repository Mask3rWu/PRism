"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Settings } from "@/types";

interface Props {
  onClose: () => void;
}

type Tab = "general" | "pat" | "llm";

export default function SettingsModal({ onClose }: Props) {
  const formRef = useRef<HTMLFormElement>(null);
  const llmFormRef = useRef<HTMLFormElement>(null);
  const [activeTab, setActiveTab] = useState<Tab>("general");
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [llmVerifying, setLlmVerifying] = useState(false);
  const [statusLoading, setStatusLoading] = useState(true);
  const [error, setError] = useState("");
  const [settings, setSettings] = useState<Settings | null>(null);
  const [verifiedPat, setVerifiedPat] = useState("");
  const [verifiedLlm, setVerifiedLlm] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  useEffect(() => {
    fetch("/api/settings")
      .then((res) => res.json())
      .then((data: Settings) => setSettings(data))
      .catch(() => setError("Failed to load settings"))
      .finally(() => setStatusLoading(false));
  }, []);

  // ── PAT handlers ──

  const handleVerifyPat = useCallback(async () => {
    const form = formRef.current;
    if (!form) return;
    const data = new FormData(form);
    const pat = (data.get("pat") as string).trim();

    if (!pat) {
      setError("Please enter a PAT first");
      return;
    }

    setVerifying(true);
    setError("");

    try {
      const res = await fetch("/api/settings/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pat }),
      });

      if (res.ok) {
        setVerifiedPat(pat);
        setError("");
      } else {
        const body = await res.json();
        setError(body.detail || "Verification failed");
        setVerifiedPat("");
      }
    } catch {
      setError("Network error. Is the backend running?");
    } finally {
      setVerifying(false);
    }
  }, []);

  const handlePatSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      if (!verifiedPat) return;

      setLoading(true);
      setError("");

      try {
        const res = await fetch("/api/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pat: verifiedPat }),
        });

        if (!res.ok) {
          const body = await res.json();
          setError(body.detail || "Failed to save PAT");
        } else {
          const data = await res.json();
          setSettings(data);
          formRef.current?.reset();
          setVerifiedPat("");
          onClose();
        }
      } catch {
        setError("Network error. Is the backend running?");
      } finally {
        setLoading(false);
      }
    },
    [onClose, verifiedPat],
  );

  const handleClearPat = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/settings/clear-pat", { method: "POST" });
      if (!res.ok) {
        const body = await res.json();
        setError(body.detail || "Failed to clear PAT");
      } else {
        const data = await res.json();
        setSettings(data);
        setVerifiedPat("");
        formRef.current?.reset();
        onClose();
      }
    } catch {
      setError("Network error. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [onClose]);

  // ── LLM handlers ──

  const handleVerifyLlm = useCallback(async () => {
    const form = llmFormRef.current;
    if (!form) return;
    const data = new FormData(form);
    const apiKey = (data.get("llm_api_key") as string).trim();
    const endpoint = (data.get("llm_endpoint") as string).trim();
    const model = (data.get("llm_model") as string).trim();

    if (!apiKey || !endpoint || !model) {
      setError("Please fill in all fields");
      return;
    }

    setLlmVerifying(true);
    setError("");
    setVerifiedLlm(false);

    try {
      const res = await fetch("/api/settings/verify-llm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: apiKey, endpoint, model }),
      });

      if (res.ok) {
        setVerifiedLlm(true);
        setError("");
      } else {
        const body = await res.json();
        setError(body.detail || "LLM verification failed");
      }
    } catch {
      setError("Network error. Is the backend running?");
    } finally {
      setLlmVerifying(false);
    }
  }, []);

  const handleLlmSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      if (!verifiedLlm) return;

      const form = llmFormRef.current;
      if (!form) return;
      const data = new FormData(form);
      const apiKey = (data.get("llm_api_key") as string).trim();
      const endpoint = (data.get("llm_endpoint") as string).trim();
      const model = (data.get("llm_model") as string).trim();

      setLoading(true);
      setError("");

      try {
        const res = await fetch("/api/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            llm: {
              provider: "pat",
              endpoint,
              model,
              api_key: apiKey,
            },
          }),
        });

        if (!res.ok) {
          const body = await res.json();
          setError(body.detail || "Failed to save LLM config");
        } else {
          const newSettings = await res.json();
          setSettings(newSettings);
          setVerifiedLlm(false);
          llmFormRef.current?.reset();
          onClose();
        }
      } catch {
        setError("Network error. Is the backend running?");
      } finally {
        setLoading(false);
      }
    },
    [onClose, verifiedLlm],
  );

  const handleClearLlm = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/settings/clear-llm", { method: "POST" });
      if (!res.ok) {
        const body = await res.json();
        setError(body.detail || "Failed to clear LLM config");
      } else {
        const data = await res.json();
        setSettings(data);
        setVerifiedLlm(false);
        llmFormRef.current?.reset();
        onClose();
      }
    } catch {
      setError("Network error. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [onClose]);

  const handleLlmFieldChange = useCallback(() => {
    setVerifiedLlm(false);
  }, []);

  const handleLanguageSave = useCallback(async (lang: "zh" | "en") => {
    setLoading(true);
    try {
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_language: lang }),
      });
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  const hasCustomLlm = settings?.llm?.has_api_key;
  const reviewCount = settings?.review_count ?? 0;
  const maxFree = settings?.max_free_reviews ?? 0;
  const freeRemaining = Math.max(0, maxFree - reviewCount);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="relative w-full max-w-md rounded-xl border border-zinc-200 bg-white p-6 shadow-xl dark:border-zinc-800 dark:bg-zinc-900">
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
        >
          ✕
        </button>
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
          Settings
        </h2>

        {/* Tabs */}
        <div className="mt-4 flex border-b border-zinc-200 dark:border-zinc-700">
          <button
            type="button"
            onClick={() => { setActiveTab("general"); setError(""); }}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "general"
                ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
                : "border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            }`}
          >
            General
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab("pat"); setError(""); }}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "pat"
                ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
                : "border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            }`}
          >
            GitHub PAT
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab("llm"); setError(""); }}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === "llm"
                ? "border-indigo-600 text-indigo-600 dark:border-indigo-400 dark:text-indigo-400"
                : "border-transparent text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
            }`}
          >
            LLM API
          </button>
        </div>

        {/* General Tab */}
        {activeTab === "general" && (
          <div className="mt-4 space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Language</h3>
              <div className="mt-2 flex items-center justify-between">
                <label className="text-sm text-zinc-600 dark:text-zinc-400">
                  Output Language
                </label>
                <select
                  value={settings?.agent_language || "zh"}
                  onChange={(e) => handleLanguageSave(e.target.value as "zh" | "en")}
                  disabled={loading}
                  className="rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                >
                  <option value="zh">中文</option>
                  <option value="en">English</option>
                </select>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Review Agents</h3>
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                Select which agents to run during review. Summary and Comment Compose are always on.
              </p>
              <div className="mt-3 space-y-2">
                {([
                  { key: "risk_analysis", label: "Reliability Review", desc: "Identify operational, concurrency, and error-handling risks" },
                  { key: "issue_detection", label: "Issue Detection", desc: "Detect bugs, logic errors, and code smells" },
                  { key: "test_suggestions", label: "Test Suggestions", desc: "Suggest test cases for the changes" },
                  { key: "security_review", label: "Security Review", desc: "Review authorization, secrets, and untrusted input changes" },
                  { key: "performance_review", label: "Performance Review", desc: "Review database, I/O, and resource-use risks" },
                  { key: "business_compliance_review", label: "Business & Compliance", desc: "Review business rules, privacy, and auditability" },
                ] as const).map((agent) => (
                  <label key={agent.key} className="flex items-start gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={(settings?.enabled_agents || []).includes(agent.key)}
                      onChange={async (e) => {
                        const current = settings?.enabled_agents?.length
                          ? settings.enabled_agents
                          : ["risk_analysis", "issue_detection", "test_suggestions", "security_review", "performance_review", "business_compliance_review"];
                        const updated = e.target.checked
                          ? [...current, agent.key]
                          : current.filter((a) => a !== agent.key);
                        setSettings((prev) => prev ? { ...prev, enabled_agents: updated } : prev);
                        try {
                          await fetch("/api/settings", {
                            method: "PUT",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ enabled_agents: updated }),
                          });
                        } catch { /* ignore */ }
                      }}
                      className="mt-0.5 h-4 w-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500 dark:border-zinc-700 dark:bg-zinc-800"
                    />
                    <div>
                      <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{agent.label}</span>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">{agent.desc}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* PAT Tab */}
        {activeTab === "pat" && (
          <form ref={formRef} onSubmit={handlePatSubmit} className="mt-4 space-y-3">
            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                GitHub Personal Access Token
              </label>
              {statusLoading ? (
                <p className="mt-1 text-sm text-zinc-400">Loading...</p>
              ) : settings?.has_pat ? (
                <p className="mt-1 text-sm text-green-600 dark:text-green-400">
                  A PAT is configured. Enter a new one to update.
                </p>
              ) : (
                <div className="mt-1 space-y-1 text-sm text-zinc-500 dark:text-zinc-400">
                  <p>No PAT configured.</p>
                  <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs dark:border-amber-800 dark:bg-amber-950">
                    <p className="font-medium text-amber-800 dark:text-amber-300 mb-1">
                      Without a PAT:
                    </p>
                    <ul className="list-disc list-inside space-y-0.5 text-amber-700 dark:text-amber-400">
                      <li>Public repositories work normally (view PRs, run reviews)</li>
                      <li>Search &amp; filter on PR lists are unavailable</li>
                      <li>Personal repo listing is unavailable</li>
                      <li>Review comments cannot be posted to GitHub</li>
                      <li>Rate limited to 60 requests/hour by GitHub</li>
                    </ul>
                    <p className="mt-2 font-medium text-green-800 dark:text-green-300">
                      With a PAT (classic, <code className="text-xs bg-amber-100 dark:bg-amber-900 px-1 rounded">repo</code> scope):
                    </p>
                    <ul className="list-disc list-inside space-y-0.5 text-green-700 dark:text-green-400">
                      <li>Access private repositories</li>
                      <li>Full search &amp; filter support</li>
                      <li>Post review comments to GitHub PRs</li>
                      <li>5,000 requests/hour rate limit</li>
                    </ul>
                  </div>
                </div>
              )}
              <div className="mt-1 flex gap-2">
                <input
                  name="pat"
                  type="password"
                  required
                  onChange={() => setVerifiedPat("")}
                  className="flex-1 rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                  placeholder="ghp_..."
                />
                <button
                  type="button"
                  onClick={handleVerifyPat}
                  disabled={verifying}
                  className="rounded-lg border border-indigo-300 px-3 py-2 text-sm font-medium text-indigo-600 hover:bg-indigo-50 disabled:opacity-50 transition-colors dark:border-indigo-700 dark:text-indigo-400 dark:hover:bg-indigo-950"
                >
                  {verifying ? "Verifying..." : "Verify"}
                </button>
              </div>
              {verifiedPat && (
                <p className="mt-1 text-xs text-green-600 dark:text-green-400">
                  Token verified successfully.
                </p>
              )}
              <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-400">
                <p className="font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                  How to get a token:
                </p>
                <ol className="list-decimal list-inside space-y-1">
                  <li>
                    Go to{" "}
                    <a
                      href="https://github.com/settings/tokens/new"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-indigo-600 hover:text-indigo-500 dark:text-indigo-400 underline"
                    >
                      GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
                    </a>
                  </li>
                  <li>Click &quot;Generate new token&quot; → &quot;Generate new token (classic)&quot;</li>
                  <li>Set an expiration date and select the following scopes:</li>
                </ol>
                <ul className="list-disc list-inside mt-1 space-y-0.5">
                  <li>
                    <code className="text-xs bg-zinc-200 dark:bg-zinc-700 px-1 rounded">repo</code> — access public and private repositories
                  </li>
                  <li>
                    <code className="text-xs bg-zinc-200 dark:bg-zinc-700 px-1 rounded">read:org</code> — read organization membership (optional, for org repos)
                  </li>
                </ul>
              </div>
            </div>
            {error && activeTab === "pat" && (
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            )}
            <button
              type="submit"
              disabled={loading || !verifiedPat}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              title={!verifiedPat ? "Please verify your token first" : ""}
            >
              {loading ? "Saving..." : "Save"}
            </button>

            {settings?.has_pat && (
              <button
                type="button"
                onClick={handleClearPat}
                disabled={loading}
                className="w-full rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950"
              >
                {loading ? "Clearing..." : "Clear PAT"}
              </button>
            )}
          </form>
        )}

        {/* LLM API Tab */}
        {activeTab === "llm" && (
          <form ref={llmFormRef} onSubmit={handleLlmSubmit} className="mt-4 space-y-3">
            {/* Status banner */}
            <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs dark:border-zinc-700 dark:bg-zinc-800/50">
              {statusLoading ? (
                <p className="text-zinc-400">Loading...</p>
              ) : hasCustomLlm ? (
                <p className="text-green-600 dark:text-green-400">
                  Using custom LLM (unlimited reviews)
                </p>
              ) : freeRemaining > 0 ? (
                <p className="text-zinc-600 dark:text-zinc-400">
                  Using free LLM —{" "}
                  <span className="font-medium text-zinc-800 dark:text-zinc-200">{freeRemaining}</span>
                  {" "}of{" "}
                  <span className="font-medium text-zinc-800 dark:text-zinc-200">{maxFree}</span>
                  {" "}free reviews remaining.
                </p>
              ) : (
                <p className="text-red-600 dark:text-red-400">
                  Free reviews exhausted. Please configure your own LLM API below.
                </p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Base URL
              </label>
              <input
                name="llm_endpoint"
                type="text"
                required
                onChange={handleLlmFieldChange}
                defaultValue={settings?.llm?.endpoint || ""}
                className="mt-1 w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                placeholder="https://api.deepseek.com/v1"
              />
              <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                Supports any OpenAI-compatible provider.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                Model
              </label>
              <input
                name="llm_model"
                type="text"
                required
                onChange={handleLlmFieldChange}
                defaultValue={settings?.llm?.model || ""}
                className="mt-1 w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                placeholder="deepseek-v4-pro"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                API Key
              </label>
              {settings?.llm?.has_api_key && (
                <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                  A key is configured. Enter a new one to replace it.
                </p>
              )}
              <div className="mt-1 flex gap-2">
                <div className="relative flex-1">
                  <input
                    name="llm_api_key"
                    type={showApiKey ? "text" : "password"}
                    required
                    onChange={handleLlmFieldChange}
                    className="w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 pr-10 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                    placeholder="sk-..."
                  />
                  <button
                    type="button"
                    onClick={() => setShowApiKey(!showApiKey)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
                  >
                    {showApiKey ? "Hide" : "Show"}
                  </button>
                </div>
                <button
                  type="button"
                  onClick={handleVerifyLlm}
                  disabled={llmVerifying}
                  className="rounded-lg border border-indigo-300 px-3 py-2 text-sm font-medium text-indigo-600 hover:bg-indigo-50 disabled:opacity-50 transition-colors dark:border-indigo-700 dark:text-indigo-400 dark:hover:bg-indigo-950"
                >
                  {llmVerifying ? "Verifying..." : "Verify"}
                </button>
              </div>
              {verifiedLlm && (
                <p className="mt-1 text-xs text-green-600 dark:text-green-400">
                  API key verified successfully.
                </p>
              )}
            </div>

            {error && activeTab === "llm" && (
              <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
            )}
            <button
              type="submit"
              disabled={loading || !verifiedLlm}
              className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              title={!verifiedLlm ? "Please verify your API key first" : ""}
            >
              {loading ? "Saving..." : "Save"}
            </button>

            {hasCustomLlm && (
              <button
                type="button"
                onClick={handleClearLlm}
                disabled={loading}
                className="w-full rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950"
              >
                {loading ? "Clearing..." : "Clear Custom LLM"}
              </button>
            )}
          </form>
        )}
      </div>
    </div>
  );
}
