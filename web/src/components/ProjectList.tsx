"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ProjectCard from "@/components/ProjectCard";
import AddProjectModal from "@/components/AddProjectModal";
import AddRepoModal from "@/components/AddRepoModal";
import type { Project } from "@/types";

function projectTags(projects: Project[]): string[] {
  return Array.from(new Set(projects.flatMap((project) => project.tags ?? []))).sort();
}

export default function ProjectList({
  initialProjects,
  initialTotal,
}: {
  initialProjects: Project[];
  initialTotal: number;
}) {
  const [projects, setProjects] = useState<Project[]>(initialProjects);
  const [total, setTotal] = useState(initialTotal);
  const [knownTags, setKnownTags] = useState<string[]>(() => projectTags(initialProjects));
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [addRepoOpen, setAddRepoOpen] = useState(false);
  const [fetchError, setFetchError] = useState("");
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [page, setPage] = useState(1);
  const perPage = 12;

  // Delete state
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [confirmBatchDelete, setConfirmBatchDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const filtersInitialized = useRef(false);

  const fetchProjects = useCallback(
    async (searchTerm: string, tagFilters: string[], favOnly: boolean, currentPage: number) => {
      try {
        const params = new URLSearchParams();
        if (searchTerm) params.set("search", searchTerm);
        tagFilters.forEach((t) => params.append("tag", t));
        if (favOnly) params.set("favorite", "true");
        params.set("page", String(currentPage));
        params.set("per_page", String(perPage));

        const res = await fetch(`/api/projects?${params}`);
        if (!res.ok) throw new Error("Failed");
        const data = await res.json();
        setProjects(data.items ?? []);
        setTotal(data.total ?? 0);
        setKnownTags((current) => Array.from(new Set([...current, ...projectTags(data.items ?? [])])).sort());
        setFetchError("");
      } catch {
        setFetchError("Could not load projects. Is the backend running?");
      }
    },
    [],
  );

  // Debounced search and filter requests.
  useEffect(() => {
    if (!filtersInitialized.current) {
      filtersInitialized.current = true;
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setPage(1);
      fetchProjects(search, selectedTags, favoriteOnly, 1);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [search, selectedTags, favoriteOnly, fetchProjects]);

  const allTags = knownTags;

  const openEditModal = (project: Project) => {
    setEditingProject(project);
    setEditModalOpen(true);
  };

  const closeEditModal = () => {
    setEditModalOpen(false);
    setEditingProject(null);
    fetchProjects(search, selectedTags, favoriteOnly, page);
  };

  const closeAddRepo = () => {
    setAddRepoOpen(false);
    fetchProjects(search, selectedTags, favoriteOnly, page);
  };

  const changePage = (nextPage: number) => {
    setPage(nextPage);
    fetchProjects(search, selectedTags, favoriteOnly, nextPage);
  };

  const handleSingleDelete = async () => {
    if (confirmDeleteId === null) return;
    setDeleting(true);
    try {
      await fetch(`/api/projects/${confirmDeleteId}`, { method: "DELETE" });
      setConfirmDeleteId(null);
      fetchProjects(search, selectedTags, favoriteOnly, page);
    } catch {
      setFetchError("Failed to delete project.");
    } finally {
      setDeleting(false);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    setDeleting(true);
    try {
      const res = await fetch("/api/projects/batch-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: Array.from(selectedIds) }),
      });
      if (!res.ok) throw new Error("Failed");
      setSelectedIds(new Set());
      setSelectMode(false);
      setConfirmBatchDelete(false);
      fetchProjects(search, selectedTags, favoriteOnly, page);
    } catch {
      setFetchError("Failed to delete projects.");
    } finally {
      setDeleting(false);
    }
  };

  const handleSelectToggle = (id: number, checked: boolean) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  };

  const handleSelectModeOff = () => {
    setSelectMode(false);
    setSelectedIds(new Set());
    setConfirmBatchDelete(false);
  };

  const totalPages = Math.max(1, Math.ceil(total / perPage));

  const hasAnyProjects = initialTotal > 0;
  const deleteConfirmProject = confirmDeleteId !== null
    ? projects.find((p) => p.id === confirmDeleteId)
    : null;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Projects
        </h1>
        <div className="flex items-center gap-2">
          {hasAnyProjects && !selectMode && (
            <button
              type="button"
              onClick={() => setSelectMode(true)}
              className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800 transition-colors"
            >
              Select
            </button>
          )}
          {selectMode && (
            <>
              <button
                type="button"
                onClick={handleSelectModeOff}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => setConfirmBatchDelete(true)}
                disabled={selectedIds.size === 0}
                className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
              >
                Delete Selected ({selectedIds.size})
              </button>
            </>
          )}
          {!selectMode && (
            <button
              type="button"
              onClick={() => setAddRepoOpen(true)}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
            >
              Add Repository
            </button>
          )}
        </div>
      </div>

      {/* Search + filter row */}
      {hasAnyProjects && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search..."
            className="w-full max-w-[180px] rounded-lg border border-zinc-300 bg-zinc-50 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
          <span className="text-xs text-zinc-400 dark:text-zinc-500">Tags:</span>
          <button
            type="button"
            onClick={() => { setFavoriteOnly(!favoriteOnly); }}
            className={`rounded-md px-2 py-1.5 text-sm font-medium transition-colors ${
              favoriteOnly
                ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
                : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
            }`}
          >
            ⭐ 收藏
          </button>
          {allTags.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => { setSelectedTags((prev: string[]) => prev.includes(t) ? prev.filter((x: string) => x !== t) : [...prev, t]); }}
              className={`rounded-md px-2 py-1.5 text-sm font-medium transition-colors ${
                selectedTags.includes(t)
                  ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300"
                  : "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
              }`}
            >
              {t}
            </button>
          ))}
          {(selectedTags.length > 0 || favoriteOnly) && (
            <button
              type="button"
              onClick={() => { setSelectedTags([]); setFavoriteOnly(false); }}
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

      {!fetchError && !hasAnyProjects && (
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

      {hasAnyProjects && projects.length === 0 && (
        <p className="mt-8 text-center text-sm text-zinc-400">
          没有符合的项目
        </p>
      )}

      {projects.length > 0 && (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                onEdit={openEditModal}
                onChange={() => fetchProjects(search, selectedTags, favoriteOnly, page)}
                onDelete={(id) => setConfirmDeleteId(id)}
                selectMode={selectMode}
                selected={selectedIds.has(project.id)}
                onSelect={handleSelectToggle}
              />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="mt-6 flex items-center justify-center gap-2">
              <button
                type="button"
                onClick={() => changePage(Math.max(1, page - 1))}
                disabled={page <= 1}
                className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800 transition-colors"
              >
                Previous
              </button>
              <span className="text-sm text-zinc-500 dark:text-zinc-400">
                Page {page} of {totalPages} ({total} projects)
              </span>
              <button
                type="button"
                onClick={() => changePage(Math.min(totalPages, page + 1))}
                disabled={page >= totalPages}
                className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

      {/* Single delete confirmation modal */}
      {confirmDeleteId !== null && deleteConfirmProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-xl border border-zinc-200 bg-white p-6 shadow-xl dark:border-zinc-800 dark:bg-zinc-900">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              Delete Project
            </h3>
            <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
              Are you sure you want to delete <strong>{deleteConfirmProject.name}</strong>?
              This will also remove all associated reviews and cannot be undone.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmDeleteId(null)}
                disabled={deleting}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSingleDelete}
                disabled={deleting}
                className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Batch delete confirmation modal */}
      {confirmBatchDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-sm rounded-xl border border-zinc-200 bg-white p-6 shadow-xl dark:border-zinc-800 dark:bg-zinc-900">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              Delete Projects
            </h3>
            <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
              Are you sure you want to delete <strong>{selectedIds.size}</strong> selected projects?
              This will also remove all associated reviews and cannot be undone.
            </p>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmBatchDelete(false)}
                disabled={deleting}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleBatchDelete}
                disabled={deleting}
                className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? "Deleting..." : `Delete ${selectedIds.size}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {editModalOpen && (
        <AddProjectModal
          open
          onClose={closeEditModal}
          project={editingProject}
        />
      )}
      {addRepoOpen && (
        <AddRepoModal
          open
          initialTab="personal"
          onClose={closeAddRepo}
          existingRepos={new Set(projects.map((p) => `${p.repo_owner}/${p.repo_name}`))}
        />
      )}
    </div>
  );
}
