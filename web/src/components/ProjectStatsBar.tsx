"use client";

import { useEffect, useRef, useState } from "react";
import type { ReviewStats } from "@/types";

interface Props {
  projectId: number;
  initialStats: ReviewStats | null;
}

const STAT_COLUMNS = [
  { key: "total", label: "Total", color: "bg-zinc-400", textColor: "text-zinc-900 dark:text-zinc-100" },
  { key: "succeeded", label: "Succeeded", color: "bg-green-500", textColor: "text-green-700 dark:text-green-400" },
  { key: "failed", label: "Failed", color: "bg-red-500", textColor: "text-red-700 dark:text-red-400" },
  { key: "in_progress", label: "In Progress", color: "bg-blue-500", textColor: "text-blue-700 dark:text-blue-400" },
] as const;

export default function ProjectStatsBar({ projectId, initialStats }: Props) {
  const [stats, setStats] = useState<ReviewStats | null>(initialStats);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const hasInProgress = stats && stats.in_progress > 0;

  useEffect(() => {
    if (!hasInProgress) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    if (intervalRef.current) return; // already polling

    intervalRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/projects/${projectId}/review-stats`);
        if (res.ok) {
          const data: ReviewStats = await res.json();
          setStats(data);
          if (data.in_progress === 0 && intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
        }
      } catch {
        // ignore
      }
    }, 3000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [hasInProgress, projectId]);

  if (!stats) return null;

  return (
    <div className="shrink-0">
      <div className="flex items-stretch divide-x divide-zinc-300 dark:divide-zinc-700">
        {STAT_COLUMNS.map((col) => (
          <div key={col.label} className="flex flex-col items-center gap-0.5 px-3 first:pl-0 last:pr-0">
            <span className="flex items-center gap-1">
              <span className={`size-2 shrink-0 rounded-full ${col.color}`} />
              <span className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
                {col.label}
              </span>
            </span>
            <span className={`text-lg font-semibold tabular-nums ${col.textColor}`}>
              {stats[col.key]}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
