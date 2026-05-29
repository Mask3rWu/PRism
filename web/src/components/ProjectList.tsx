"use client";

import { useState } from "react";
import ProjectCard from "@/components/ProjectCard";
import AddProjectModal from "@/components/AddProjectModal";
import type { Project } from "@/types";

export default function ProjectList({ initialProjects }: { initialProjects: Project[] }) {
  const [projects, setProjects] = useState<Project[]>(initialProjects);
  const [modalOpen, setModalOpen] = useState(false);
  const [fetchError, setFetchError] = useState("");

  const handleRefresh = async () => {
    try {
      const res = await fetch("/api/projects");
      if (!res.ok) throw new Error("Failed");
      setProjects(await res.json());
      setFetchError("");
    } catch {
      setFetchError("Could not load projects. Is the backend running?");
    }
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
          onClick={() => setModalOpen(true)}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
        >
          Add Project
        </button>
      </div>

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
            onClick={() => setModalOpen(true)}
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800 transition-colors"
          >
            Add your first project
          </button>
        </div>
      )}

      {hasProjects && (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <ProjectCard key={project.id} project={project} />
          ))}
        </div>
      )}

      <AddProjectModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          handleRefresh();
        }}
      />
    </div>
  );
}
