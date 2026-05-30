import ProjectList from "@/components/ProjectList";
import type { PaginatedProjects, Project } from "@/types";

async function getProjects(): Promise<{ projects: Project[]; total: number }> {
  try {
    const res = await fetch("http://localhost:8000/api/projects?per_page=100", {
      cache: "no-store",
    });
    if (!res.ok) return { projects: [], total: 0 };
    const data: PaginatedProjects = await res.json();
    return { projects: data.items, total: data.total };
  } catch {
    return { projects: [], total: 0 };
  }
}

export default async function Home() {
  const { projects, total } = await getProjects();
  return <ProjectList initialProjects={projects} initialTotal={total} />;
}
