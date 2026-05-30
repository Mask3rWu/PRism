"use client";

import { useState } from "react";
import Link from "next/link";
import type { Project } from "@/types";

interface Props {
  project: Project;
  onEdit: (project: Project) => void;
  onChange: () => void;
  onDelete: (id: number) => void;
  selectMode: boolean;
  selected: boolean;
  onSelect: (id: number, checked: boolean) => void;
}

const PERMISSION_COLORS: Record<string, string> = {
  Owner: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  Maintainer: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  Collaborator: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  Viewer: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
};

export default function ProjectCard({
  project,
  onEdit,
  onChange,
  onDelete,
  selectMode,
  selected,
  onSelect,
}: Props) {
  const [favLoading, setFavLoading] = useState(false);
  const created = new Date(project.created_at).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  const tags: string[] = project.tags ?? [];
  const visibleTags = tags.slice(0, 3);
  const overflow = tags.length - 3;

  const handleFavorite = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setFavLoading(true);
    try {
      await fetch(`/api/projects/${project.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_favorite: !project.is_favorite }),
      });
      onChange();
    } catch {
      // ignore
    } finally {
      setFavLoading(false);
    }
  };

  return (
    <div className="group relative rounded-xl border border-zinc-200 bg-white p-5 transition-shadow hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900">
      {/* Select checkbox */}
      {selectMode && (
        <div className="absolute left-3 top-3 z-10">
          <input
            type="checkbox"
            checked={selected}
            onChange={(e) => onSelect(project.id, e.target.checked)}
            className="size-4 rounded border-zinc-300 text-indigo-600 focus:ring-indigo-500"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}

      {/* Top row: star + name + permission + action buttons */}
      <div className={`flex items-center justify-between ${selectMode ? "ml-6" : ""}`}>
        <div className="flex items-center gap-2 min-w-0">
          <button
            type="button"
            onClick={handleFavorite}
            disabled={favLoading}
            className="shrink-0 text-lg transition-colors"
            title={project.is_favorite ? "Remove from favorites" : "Add to favorites"}
          >
            {project.is_favorite ? (
              <span className="text-amber-500">&#9733;</span>
            ) : (
              <span className="text-zinc-300 hover:text-amber-400 dark:text-zinc-600">&#9734;</span>
            )}
          </button>
          <h2 className="text-lg font-semibold text-zinc-900 truncate dark:text-zinc-100">
            <Link href={`/projects/${project.id}`} className="hover:text-indigo-600 dark:hover:text-indigo-400">
              {project.name}
            </Link>
          </h2>
          <span
            className={`shrink-0 rounded-md px-1.5 py-0.5 text-[11px] font-medium ${
              PERMISSION_COLORS[project.permission] ?? PERMISSION_COLORS.Viewer
            }`}
          >
            {project.permission}
          </span>
        </div>

        {/* Action buttons — always visible */}
        <div className="flex items-center gap-1 shrink-0 ml-2">
          <button
            type="button"
            onClick={() => onEdit(project)}
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
            title="Edit project"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-4">
              <path d="M2.695 14.762l-1.262 3.155a.5.5 0 00.65.65l3.155-1.262a4 4 0 001.343-.885L17.5 5.5a2.121 2.121 0 00-3-3L3.58 13.42a4 4 0 00-.885 1.342z" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => onDelete(project.id)}
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-red-500 dark:hover:bg-zinc-800 dark:hover:text-red-400"
            title="Delete project"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-4">
              <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193v-.443A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075v-.325c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clipRule="evenodd" />
            </svg>
          </button>
        </div>
      </div>

      {/* Repo path + tags */}
      <div className={`mt-1.5 flex flex-wrap items-center gap-2 ${selectMode ? "ml-6" : ""}`}>
        <Link
          href={`/projects/${project.id}`}
          className="text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
        >
          {project.repo_owner}/{project.repo_name}
        </Link>
        {tags.length > 0 && (
          <span className="inline-flex items-center gap-1">
            {visibleTags.map((t) => (
              <span
                key={t}
                className="rounded-md bg-green-100 px-1.5 py-0.5 text-[11px] text-green-700 dark:bg-green-900/30 dark:text-green-300"
              >
                {t}
              </span>
            ))}
            {overflow > 0 && (
              <span
                className="rounded-md bg-zinc-100 px-1.5 py-0.5 text-[11px] text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
                title={tags.join(", ")}
              >
                +{overflow}
              </span>
            )}
          </span>
        )}
      </div>

      {/* Description */}
      {project.description && (
        <p className={`mt-2 text-sm text-zinc-600 dark:text-zinc-400 line-clamp-2 ${selectMode ? "ml-6" : ""}`}>
          {project.description}
        </p>
      )}

      {/* Created date */}
      <p className={`mt-3 text-xs text-zinc-400 dark:text-zinc-500 ${selectMode ? "ml-6" : ""}`}>
        Created {created}
      </p>
    </div>
  );
}
