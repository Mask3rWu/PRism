"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Project, ProjectCreatePayload, ProjectUpdatePayload } from "@/types";

interface Props {
  open: boolean;
  onClose: () => void;
  project?: Project | null;
}

export default function AddProjectModal({ open, onClose, project }: Props) {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const isEdit = !!project;

  useEffect(() => {
    if (!open) {
      setError("");
      setLoading(false);
    }
  }, [open]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent<HTMLFormElement>) => {
      e.preventDefault();
      setLoading(true);
      setError("");

      const form = e.currentTarget;
      const data = new FormData(form);

      try {
        if (isEdit && project) {
          const payload: ProjectUpdatePayload = {};
          const desc = (data.get("description") as string).trim();
          const pat = (data.get("pat") as string).trim();
          if (desc !== (project.description ?? "")) {
            payload.description = desc;
          }
          if (pat) {
            payload.pat = pat;
          }
          if (!payload.description && !payload.pat) {
            setError("No changes to save");
            setLoading(false);
            return;
          }

          const res = await fetch(`/api/projects/${project.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });

          if (!res.ok) {
            const body = await res.json();
            setError(body.detail || "Failed to update project");
          } else {
            onClose();
            router.refresh();
          }
        } else {
          const payload: ProjectCreatePayload = {
            name: data.get("name") as string,
            repo_owner: data.get("repo_owner") as string,
            repo_name: data.get("repo_name") as string,
            pat: data.get("pat") as string,
            description: data.get("description") as string,
          };

          const res = await fetch("/api/projects", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });

          if (!res.ok) {
            const body = await res.json();
            setError(body.detail || "Failed to create project");
          } else {
            form.reset();
            onClose();
            router.refresh();
          }
        }
      } catch {
        setError("Network error. Is the backend running?");
      } finally {
        setLoading(false);
      }
    },
    [isEdit, onClose, project, router],
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
          {isEdit ? "Edit Project" : "Add Project"}
        </h2>
        <form ref={formRef} onSubmit={handleSubmit} className="mt-4 space-y-3">
          {isEdit ? (
            <>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Project Name
                </label>
                <p className="mt-1 text-sm text-zinc-900 dark:text-zinc-100">
                  {project!.name}
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Repository
                </label>
                <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                  {project!.repo_owner}/{project!.repo_name}
                </p>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  GitHub PAT
                </label>
                <input
                  name="pat"
                  type="password"
                  className="mt-1 w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                  placeholder="Leave blank to keep current"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Description
                </label>
                <textarea
                  name="description"
                  rows={2}
                  defaultValue={project!.description}
                  className="mt-1 w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                  placeholder="Brief project description (optional)"
                />
              </div>
            </>
          ) : (
            <>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Project Name
                </label>
                <input
                  name="name"
                  required
                  className="mt-1 w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                  placeholder="My Project"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Owner
                  </label>
                  <input
                    name="repo_owner"
                    required
                    className="mt-1 w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                    placeholder="owner"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                    Repo
                  </label>
                  <input
                    name="repo_name"
                    required
                    className="mt-1 w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                    placeholder="repo"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  GitHub PAT
                </label>
                <input
                  name="pat"
                  type="password"
                  required
                  className="mt-1 w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                  placeholder="ghp_..."
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Description
                </label>
                <textarea
                  name="description"
                  rows={2}
                  className="mt-1 w-full rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                  placeholder="Brief project description (optional)"
                />
              </div>
            </>
          )}
          {error && (
            <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {loading
              ? isEdit
                ? "Saving..."
                : "Creating..."
              : isEdit
                ? "Save Changes"
                : "Create Project"}
          </button>
        </form>
      </div>
    </div>
  );
}
