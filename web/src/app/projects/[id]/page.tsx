import Link from "next/link";
import type { PaginatedPRs, Project } from "@/types";
import PRList from "@/components/PRList";
import ProjectStatsBar from "@/components/ProjectStatsBar";

const BACKEND = "http://localhost:8000";

async function getProject(id: string): Promise<Project | null> {
  try {
    const res = await fetch(`${BACKEND}/api/projects/${id}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function getPRs(
  id: string,
  page: number,
  perPage: number,
  state: string,
  sort: string,
  direction: string,
): Promise<PaginatedPRs> {
  try {
    const params = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
      state,
      sort,
      direction,
    });
    const res = await fetch(
      `${BACKEND}/api/projects/${id}/pulls?${params}`,
      { cache: "no-store" }
    );
    if (!res.ok) return { items: [], total: 0, page, per_page: perPage, review_stats: null };
    return res.json();
  } catch {
    return { items: [], total: 0, page, per_page: perPage, review_stats: null };
  }
}

export const dynamic = "force-dynamic";

interface Props {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ state?: string; sort?: string; search?: string; author?: string }>;
}

export default async function ProjectDetailPage({ params, searchParams }: Props) {
  const { id } = await params;
  const sp = await searchParams;
  const page = 1;
  const perPage = 30;
  const state = sp.state || "open";
  const [sortField, direction] = (sp.sort || "created-desc").split("-");

  const [project, prData] = await Promise.all([
    getProject(id),
    getPRs(id, page, perPage, state, sortField, direction || "desc"),
  ]);

  if (!project) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-16 text-center">
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          Project Not Found
        </h1>
        <p className="mt-2 text-zinc-500">
          The project you&apos;re looking for doesn&apos;t exist.
        </p>
        <Link
          href="/"
          className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400"
        >
          Back to Projects
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className="size-4"
        >
          <path
            fillRule="evenodd"
            d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z"
            clipRule="evenodd"
          />
        </svg>
        Back
      </Link>

      <div className="mt-4 flex items-start justify-between gap-8">
        <div className="min-w-0">
          <h1 className="text-3xl font-semibold text-zinc-900 dark:text-zinc-100">
            {project.name}
          </h1>
          <div className="mt-1 flex items-center gap-3">
            <span className="text-sm text-zinc-500 dark:text-zinc-400">
              {project.repo_owner}/{project.repo_name}
            </span>
            {project.description && (
              <>
                <span className="text-zinc-300 dark:text-zinc-700">·</span>
                <span className="text-sm text-zinc-500 dark:text-zinc-400">
                  {project.description}
                </span>
              </>
            )}
          </div>
        </div>
        <ProjectStatsBar projectId={project.id} initialStats={prData.review_stats} />
      </div>

      <div className="mt-8">
        <PRList
          project={project}
          initialPRs={prData.items}
          initialTotal={prData.total}
          initialPage={page}
          perPage={perPage}
        />
      </div>
    </div>
  );
}
