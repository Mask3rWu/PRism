"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Settings } from "@/types";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function SettingsModal({ open, onClose }: Props) {
  const formRef = useRef<HTMLFormElement>(null);
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [statusLoading, setStatusLoading] = useState(false);
  const [error, setError] = useState("");
  const [hasPat, setHasPat] = useState(false);
  const [verifiedPat, setVerifiedPat] = useState("");

  useEffect(() => {
    if (!open) {
      setError("");
      setLoading(false);
      setVerifying(false);
      setVerifiedPat("");
      return;
    }

    setStatusLoading(true);
    fetch("/api/settings")
      .then((res) => res.json())
      .then((data: Settings) => setHasPat(data.has_pat))
      .catch(() => setError("Failed to load settings"))
      .finally(() => setStatusLoading(false));
  }, [open]);

  const handleVerify = useCallback(async () => {
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

  const handleSubmit = useCallback(
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
          setHasPat(true);
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

  if (!open) return null;

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
        <form ref={formRef} onSubmit={handleSubmit} className="mt-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
              GitHub Personal Access Token
            </label>
            {statusLoading ? (
              <p className="mt-1 text-sm text-zinc-400">Loading...</p>
            ) : (
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                {hasPat
                  ? "A PAT is configured. Enter a new one to update."
                  : "No PAT configured. A token is required to access GitHub repositories."}
              </p>
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
                onClick={handleVerify}
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
                    GitHub &rarr; Settings &rarr; Developer settings &rarr; Personal access tokens &rarr; Tokens (classic)
                  </a>
                </li>
                <li>Click "Generate new token" &rarr; "Generate new token (classic)"</li>
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
          {error && (
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
        </form>
      </div>
    </div>
  );
}
