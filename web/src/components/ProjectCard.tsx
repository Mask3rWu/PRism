import Link from "next/link";
import type { Project } from "@/types";

export default function ProjectCard({ project }: { project: Project }) {
  const created = new Date(project.created_at).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <Link
      href={`/projects/${project.id}`}
      className="group block rounded-xl border border-zinc-200 bg-white p-5 transition-shadow hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
    >
      <h2 className="text-lg font-semibold text-zinc-900 group-hover:text-indigo-600 dark:text-zinc-100 dark:group-hover:text-indigo-400">
        {project.name}
      </h2>
      <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
        {project.repo_owner}/{project.repo_name}
      </p>
      {project.description && (
        <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400 line-clamp-2">
          {project.description}
        </p>
      )}
      <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">
        Created {created}
      </p>
    </Link>
  );
}
