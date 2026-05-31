import Link from "next/link";
import type { ReviewDetail } from "@/types";
import ReviewResult from "@/components/ReviewResult";
import BackToProjectLink from "@/components/BackToProjectLink";

const BACKEND = "http://localhost:8000";

async function getReview(id: string): Promise<ReviewDetail | null> {
  try {
    const res = await fetch(`${BACKEND}/api/reviews/${id}`, {
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function getProject(projectId: number): Promise<{ permission: string } | null> {
  try {
    const res = await fetch(`${BACKEND}/api/projects/${projectId}`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

interface Props {
  params: Promise<{ id: string }>;
}

export default async function ReviewDetailPage({ params }: Props) {
  const { id } = await params;
  const review = await getReview(id);
  const project = review ? await getProject(review.project_id) : null;

  if (!review) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-16 text-center">
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">
          Review Not Found
        </h1>
        <p className="mt-2 text-zinc-500">
          The review you&apos;re looking for doesn&apos;t exist.
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
      <BackToProjectLink
        projectId={review.project_id}
        className="inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200 transition-colors"
      />

      <ReviewResult review={review} projectPermission={project?.permission} />
    </div>
  );
}
