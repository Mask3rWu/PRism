import Link from "next/link";
import type { Project, PullRequestItem } from "@/types";
import PRList from "@/components/PRList";

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
  perPage: number
): Promise<PullRequestItem[]> {
  try {
    const res = await fetch(
      `${BACKEND}/api/projects/${id}/pulls?page=${page}&per_page=${perPage}`,
      { cache: "no-store" }
    );
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

interface Props {
  params: Promise<{ id: string }>;
}

export default async function ProjectDetailPage({ params }: Props) {
  const { id } = await params;
  const page = 1;
  const perPage = 30;

  const [project, prs] = await Promise.all([
    getProject(id),
    getPRs(id, page, perPage),
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
          ← Back to Projects
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

      <div className="mt-4">
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
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

      <div className="mt-8">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
          Open Pull Requests
        </h2>
        <div className="mt-3">
          <PRList
            project={project}
            initialPRs={prs}
            initialPage={page}
            perPage={perPage}
          />
        </div>
      </div>
    </div>
  );
}
