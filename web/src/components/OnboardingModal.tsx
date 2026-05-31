"use client";

import { useCallback, useEffect, useState } from "react";
import type { Settings } from "@/types";

const STORAGE_KEY = "prism_onboarding_dismissed";

export function isOnboardingDismissed(): boolean {
  if (typeof window === "undefined") return true;
  return localStorage.getItem(STORAGE_KEY) === "1";
}

interface Props {
  open: boolean;
  onOpenSettings: () => void;
  onClose: () => void;
}

export default function OnboardingModal({ open, onOpenSettings, onClose }: Props) {
  const [settings, setSettings] = useState<Settings | null>(null);

  useEffect(() => {
    if (!open) return;
    fetch("/api/settings")
      .then((res) => res.json())
      .then((data: Settings) => setSettings(data))
      .catch(() => {});
  }, [open]);

  const handleSkip = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, "1");
    onClose();
  }, [onClose]);

  const handleOpenSettings = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, "1");
    onClose();
    // Small delay so the modal close animation doesn't conflict
    setTimeout(() => onOpenSettings(), 150);
  }, [onClose, onOpenSettings]);

  if (!open) return null;

  const hasPat = settings?.has_pat ?? false;
  const hasCustomLlm = settings?.llm?.has_api_key ?? false;
  const reviewCount = settings?.review_count ?? 0;
  const maxFree = settings?.max_free_reviews ?? 0;
  const freeRemaining = Math.max(0, maxFree - reviewCount);
  const allConfigured = hasPat && hasCustomLlm;
  const anyConfigured = hasPat || hasCustomLlm;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50">
      <div className="relative w-full max-w-lg rounded-xl border border-zinc-200 bg-white p-6 shadow-2xl dark:border-zinc-800 dark:bg-zinc-900">
        {/* Header */}
        <div className="text-center">
          <span className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-600 text-xl font-bold text-white">
            P
          </span>
          <h2 className="mt-3 text-xl font-semibold text-zinc-900 dark:text-zinc-100">
            Welcome to PRism
          </h2>
          <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
            AI-powered pull request review assistant
          </p>
        </div>

        {/* Status cards */}
        <div className="mt-6 grid grid-cols-2 gap-3">
          {/* LLM Card */}
          <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
            <div className="flex items-center gap-2">
              <span className="text-lg">🤖</span>
              <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">LLM API</span>
            </div>
            {hasCustomLlm ? (
              <p className="mt-2 text-xs text-green-600 dark:text-green-400">
                Configured ✓
              </p>
            ) : (
              <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                {freeRemaining > 0
                  ? `Free: ${freeRemaining}/${maxFree} reviews left`
                  : "Free quota exhausted"}
              </p>
            )}
          </div>

          {/* PAT Card */}
          <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
            <div className="flex items-center gap-2">
              <span className="text-lg">🔑</span>
              <span className="text-sm font-medium text-zinc-800 dark:text-zinc-200">GitHub PAT</span>
            </div>
            {hasPat ? (
              <p className="mt-2 text-xs text-green-600 dark:text-green-400">
                Configured ✓
              </p>
            ) : (
              <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                Not configured — public repos only
              </p>
            )}
          </div>
        </div>

        {/* What's needed */}
        <div className="mt-4 rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-xs text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-400">
          {!allConfigured && (
            <div className="space-y-2">
              {!hasCustomLlm && (
                <div>
                  <p className="font-medium text-zinc-700 dark:text-zinc-300">
                    Configure LLM API to get started:
                  </p>
                  <p className="mt-0.5">
                    PRism includes {maxFree} free reviews. After that, bring your own
                    API key (any OpenAI-compatible provider).
                  </p>
                </div>
              )}
              {!hasPat && (
                <div>
                  <p className="font-medium text-zinc-700 dark:text-zinc-300">
                    GitHub PAT is optional:
                  </p>
                  <p className="mt-0.5">
                    Public repositories work without a token. Add a PAT to access private
                    repos, search PRs, and post review comments.
                  </p>
                </div>
              )}
            </div>
          )}
          {allConfigured && (
            <p className="text-green-600 dark:text-green-400">
              All set! LLM and GitHub PAT are both configured.
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="mt-5 flex gap-3">
          <button
            type="button"
            onClick={handleSkip}
            className="flex-1 rounded-lg border border-zinc-300 px-4 py-2.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 transition-colors dark:border-zinc-600 dark:text-zinc-300 dark:hover:bg-zinc-800"
          >
            {anyConfigured ? "Got it" : "Skip for now"}
          </button>
          <button
            type="button"
            onClick={handleOpenSettings}
            className="flex-1 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
          >
            Open Settings
          </button>
        </div>
      </div>
    </div>
  );
}
