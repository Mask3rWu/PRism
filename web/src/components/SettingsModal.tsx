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
  const [statusLoading, setStatusLoading] = useState(false);
  const [error, setError] = useState("");
  const [hasPat, setHasPat] = useState(false);

  useEffect(() => {
    if (!open) {
      setError("");
      setLoading(false);
      return;
    }

    setStatusLoading(true);
    fetch("/api/settings")
      .then((res) => res.json())
      .then((data: Settings) => setHasPat(data.has_pat))
      .catch(() => setError("Failed to load settings"))
      .finally(() => setStatusLoading(false));
  }, [open]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      setLoading(true);
      setError("");

      const form = e.currentTarget;
      const data = new FormData(form);
      const pat = (data.get("pat") as string).trim();

      if (!pat) {
        setError("PAT is required");
        setLoading(false);
        return;
      }

      try {
        const res = await fetch("/api/settings", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pat }),
        });

        if (!res.ok) {
          const body = await res.json();
          setError(body.detail || "Failed to save PAT");
        } else {
          setHasPat(true);
          form.reset();
          onClose();
        }
      } catch {
        setError("Network error. Is the backend running?");
      } finally {
        setLoading(false);
      }
    },
    [onClose],
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
            <input
              name="pat"
              type="password"
              required
              className="mt-1 w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
              placeholder="ghp_..."
            />
            <p className="mt-1 text-xs text-zinc-400">
              Used for all projects. Needs <code>repo</code> scope for private repositories.
            </p>
          </div>
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading ? "Saving..." : "Save"}
          </button>
        </form>
      </div>
    </div>
  );
}
