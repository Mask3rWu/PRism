"use client";

import { useState } from "react";
import Link from "next/link";
import type { Project } from "@/types";

interface Props {
  project: Project;
  onEdit: (project: Project) => void;
  onChange: () => void;
}

export default function ProjectCard({ project, onEdit, onChange }: Props) {
  const [favLoading, setFavLoading] = useState(false);
  const created = new Date(project.created_at).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  const tags: string[] = project.tags ?? [];
  const visibleTags = tags.slice(0, 2);
  const overflow = tags.length - 2;

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
      <Link href={`/projects/${project.id}`} className="block">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-zinc-900 group-hover:text-indigo-600 dark:text-zinc-100 dark:group-hover:text-indigo-400">
            {project.name}
          </h2>
          {project.is_favorite && (
            <span className="text-amber-500 text-sm">&#9733;</span>
          )}
        </div>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          {project.repo_owner}/{project.repo_name}
        </p>
        {project.description && (
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400 line-clamp-2">
            {project.description}
          </p>
        )}
        {tags.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1">
            {visibleTags.map((t) => (
              <span
                key={t}
                className="rounded-md bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
              >
                {t}
              </span>
            ))}
            {overflow > 0 && (
              <span
                className="rounded-md bg-zinc-100 px-2 py-0.5 text-xs text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500"
                title={tags.join(", ")}
              >
                +{overflow}
              </span>
            )}
          </div>
        )}
        <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">
          Created {created}
        </p>
      </Link>

      {/* Action buttons */}
      <div className="absolute right-3 top-3 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          type="button"
          onClick={handleFavorite}
          disabled={favLoading}
          className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-amber-500 dark:hover:bg-zinc-800 dark:hover:text-amber-400"
          title={project.is_favorite ? "Remove from favorites" : "Add to favorites"}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-4">
            {project.is_favorite ? (
              <path fillRule="evenodd" d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" clipRule="evenodd" />
            ) : (
              <path fillRule="evenodd" d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" clipRule="evenodd" opacity="0.3" />
            )}
          </svg>
        </button>
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            onEdit(project);
          }}
          className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
          title="Edit project"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-4">
            <path d="M2.695 14.762l-1.262 3.155a.5.5 0 00.65.65l3.155-1.262a4 4 0 001.343-.885L17.5 5.5a2.121 2.121 0 00-3-3L3.58 13.42a4 4 0 00-.885 1.342z" />
          </svg>
        </button>
      </div>
    </div>
  );
}
