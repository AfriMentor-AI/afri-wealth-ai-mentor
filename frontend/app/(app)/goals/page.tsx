"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { fetchGoals } from "@/lib/api";
import type { Goal } from "@/lib/types";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { Skeleton } from "@/components/ui/Skeleton";

function nextMilestone(goal: Goal) {
  return goal.milestones.find((m) => m.status === "in_progress") ?? goal.milestones.find((m) => m.status === "upcoming");
}

export default function GoalsOverviewPage() {
  const [goals, setGoals] = useState<Goal[] | null>(null);

  useEffect(() => {
    fetchGoals().then(setGoals);
  }, []);

  return (
    <main className="relative px-margin-mobile pb-xl pt-lg">
      <section className="relative z-10 mb-lg">
        <div className="flex items-center justify-between">
          <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-on-background">Your Journey</h2>
          <Link
            href="/goals/action"
            className="tap-target flex items-center gap-xs rounded-full bg-primary-container px-md py-sm font-label-sm text-label-sm text-on-primary-container"
          >
            <Icon name="today" size={16} />
            Today
          </Link>
        </div>
        <p className="font-body-md text-on-surface-variant">Honoring the past while building your future wealth.</p>
      </section>

      <div className="relative z-10 mb-lg grid grid-cols-1 gap-md">
        {goals === null ? (
          Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-28 w-full rounded" />)
        ) : (
          <>
            {/* Business Launch — flat card + next milestone banner */}
            <Link
              href={`/goals/milestones/${goals[0].id}`}
              className="flex flex-col gap-md rounded border border-outline-variant bg-surface-container-low p-md"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-title-md text-title-md mb-xs text-primary">{goals[0].title}</h3>
                  <p className="font-label-sm text-label-sm text-on-surface-variant">Deadline: Oct 24, 2026</p>
                </div>
                <ProgressRing progressPct={goals[0].progressPct} size={64} />
              </div>
              <div className="rounded-lg border-l-4 border-primary bg-surface-bright p-sm">
                <p className="mb-xs font-label-sm text-label-sm uppercase text-on-surface-variant">Next Milestone</p>
                <p className="font-body-md font-semibold text-on-surface">{nextMilestone(goals[0])?.title}</p>
              </div>
            </Link>

            {/* Debt Reduction — filled secondary-container card */}
            <Link
              href={`/goals/milestones/${goals[1].id}`}
              className="flex items-center gap-md rounded border border-secondary/20 bg-secondary-container p-md"
            >
              <div className="flex-1">
                <h3 className="font-title-md text-title-md mb-xs text-on-secondary-container">{goals[1].title}</h3>
                <p className="mb-md font-label-sm text-label-sm text-on-secondary-container opacity-80">
                  Deadline: Dec 12, 2026
                </p>
                <div className="flex items-center gap-sm">
                  <Icon name="workspace_premium" filled className="text-on-secondary-container" />
                  <p className="font-body-md font-semibold text-on-secondary-container">
                    {nextMilestone(goals[1])?.title}
                  </p>
                </div>
              </div>
              <div className="flex h-20 w-20 items-center justify-center rounded-full bg-surface-container-lowest shadow-sm">
                <ProgressRing progressPct={goals[1].progressPct} size={64} />
              </div>
            </Link>

            {/* Skill Acquisition — linear progress card */}
            <Link
              href={`/goals/milestones/${goals[2].id}`}
              className="flex flex-col gap-md rounded border border-outline-variant bg-surface-container-low p-md"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-title-md text-title-md text-primary">{goals[2].title}</h3>
                <span className="rounded-full bg-primary-container px-sm py-xs font-label-sm text-label-sm text-on-primary-container">
                  {goals[2].progressPct}% Complete
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-surface-variant">
                <div className="h-full bg-primary" style={{ width: `${goals[2].progressPct}%` }} />
              </div>
              <div className="flex items-center justify-between text-on-surface-variant">
                <div className="flex items-center gap-xs">
                  <Icon name="flag" size={18} />
                  <span className="font-label-sm text-label-sm">{nextMilestone(goals[2])?.title}</span>
                </div>
                <span className="font-label-sm text-label-sm italic">Jan 2027</span>
              </div>
            </Link>
          </>
        )}
      </div>

      <button className="flex w-full items-center justify-center gap-md rounded-full bg-primary px-lg py-md text-on-primary shadow-md transition-transform active:scale-95 hover:opacity-90">
        <Icon name="add" />
        <span className="font-title-md text-title-md">Create New Goal</span>
      </button>
    </main>
  );
}
