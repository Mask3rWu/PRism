import ProjectList from "@/components/ProjectList";
import type { Project } from "@/types";

async function getProjects(): Promise<Project[]> {
  try {
    const res = await fetch("http://localhost:8000/api/projects", {
      cache: "no-store",
    });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function Home() {
  const projects = await getProjects();
  return <ProjectList initialProjects={projects} />;
}
