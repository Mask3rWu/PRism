import Link from "next/link";
import type { Project } from "@/types";

interface Props {
  project: Project;
  onEdit: (project: Project) => void;
}

export default function ProjectCard({ project, onEdit }: Props) {
  const created = new Date(project.created_at).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="group relative rounded-xl border border-zinc-200 bg-white p-5 transition-shadow hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900">
      <Link href={`/projects/${project.id}`} className="block">
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
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          onEdit(project);
        }}
        className="absolute right-3 top-3 rounded-lg p-1.5 text-zinc-400 opacity-0 transition-opacity hover:bg-zinc-100 hover:text-zinc-600 group-hover:opacity-100 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
        title="Edit project"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-4">
          <path d="M2.695 14.762l-1.262 3.155a.5.5 0 00.65.65l3.155-1.262a4 4 0 001.343-.885L17.5 5.5a2.121 2.121 0 00-3-3L3.58 13.42a4 4 0 00-.885 1.342z" />
        </svg>
      </button>
    </div>
  );
}
