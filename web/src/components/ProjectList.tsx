"use client";

import { useCallback, useMemo, useState } from "react";
import ProjectCard from "@/components/ProjectCard";
import AddProjectModal from "@/components/AddProjectModal";
import AddRepoModal from "@/components/AddRepoModal";
import type { Project } from "@/types";

export default function ProjectList({
  initialProjects,
  initialTotal,
}: {
  initialProjects: Project[];
  initialTotal: number;
}) {
  const [projects, setProjects] = useState<Project[]>(initialProjects);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [addRepoOpen, setAddRepoOpen] = useState(false);
  const [fetchError, setFetchError] = useState("");
  const [selectedTag, setSelectedTag] = useState("");

  const handleRefresh = useCallback(async () => {
    try {
      const res = await fetch("/api/projects?per_page=100");
      if (!res.ok) throw new Error("Failed");
      const data = await res.json();
      setProjects(data.items ?? []);
      setFetchError("");
    } catch {
      setFetchError("Could not load projects. Is the backend running?");
    }
  }, []);

  // Extract unique tags across all projects
  const allTags = useMemo(() => {
    const tagSet = new Set<string>();
    projects.forEach((p) => (p.tags ?? []).forEach((t) => tagSet.add(t)));
    return Array.from(tagSet).sort();
  }, [projects]);

  const filteredProjects = selectedTag
    ? projects.filter((p) => (p.tags ?? []).includes(selectedTag))
    : projects;

  const openEditModal = (project: Project) => {
    setEditingProject(project);
    setEditModalOpen(true);
  };

  const closeEditModal = () => {
    setEditModalOpen(false);
    setEditingProject(null);
    handleRefresh();
  };

  const closeAddRepo = () => {
    setAddRepoOpen(false);
    handleRefresh();
  };

  const hasProjects = projects.length > 0;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Projects
        </h1>
        <button
          type="button"
          onClick={() => setAddRepoOpen(true)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
        >
          Add Repository
        </button>
      </div>

      {/* Tag filter bar */}
      {allTags.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-xs text-zinc-400 dark:text-zinc-500">Tags:</span>
          {allTags.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setSelectedTag(selectedTag === t ? "" : t)}
              className={`rounded-md px-2 py-0.5 text-xs font-medium transition-colors ${
                selectedTag === t
                  ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300"
                  : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
              }`}
            >
              {t}
            </button>
          ))}
          {selectedTag && (
            <button
              type="button"
              onClick={() => setSelectedTag("")}
              className="text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
            >
              clear
            </button>
          )}
        </div>
      )}

      {fetchError && (
        <p className="mt-4 text-sm text-red-600 dark:text-red-400">{fetchError}</p>
      )}

      {!fetchError && !hasProjects && (
        <div className="mt-16 flex flex-col items-center gap-3 text-center">
          <p className="text-lg text-zinc-500 dark:text-zinc-400">
            No projects configured yet.
          </p>
          <button
            type="button"
            onClick={() => setAddRepoOpen(true)}
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800 transition-colors"
          >
            Add your first repository
          </button>
        </div>
      )}

      {hasProjects && filteredProjects.length === 0 && (
        <p className="mt-8 text-center text-sm text-zinc-400">
          No projects match the selected tag.
        </p>
      )}

      {hasProjects && filteredProjects.length > 0 && (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredProjects.map((project) => (
            <ProjectCard
              key={project.id}
              project={project}
              onEdit={openEditModal}
              onChange={handleRefresh}
            />
          ))}
        </div>
      )}

      <AddProjectModal
        open={editModalOpen}
        onClose={closeEditModal}
        project={editingProject}
      />
      <AddRepoModal
        open={addRepoOpen}
        initialTab="personal"
        onClose={closeAddRepo}
        existingRepos={new Set(projects.map((p) => `${p.repo_owner}/${p.repo_name}`))}
      />
    </div>
  );
}
