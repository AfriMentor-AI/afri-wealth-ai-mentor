"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { createGoal, fetchGoals, fetchMilestonesByGoal } from "@/lib/api";
import type { Goal, Milestone } from "@/lib/types";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";

function nextMilestone(milestones: Milestone[] | undefined) {
  if (!milestones) return undefined;
  return milestones.find((m) => m.status === "in_progress") ?? milestones.find((m) => m.status === "upcoming");
}

function formatDeadline(deadline: string | undefined) {
  if (!deadline) return null;
  return new Date(deadline).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function GoalsOverviewPage() {
  const [goals, setGoals] = useState<Goal[] | null>(null);
  // Milestone is its own normalized collection per the contract, so it's
  // fetched separately per goal and joined here client-side — a real
  // backend might instead offer a batch/expand endpoint to avoid the
  // N+1 fetch pattern this causes once there are many goals.
  const [milestonesByGoal, setMilestonesByGoal] = useState<Record<string, Milestone[]>>({});
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newGoalTitle, setNewGoalTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function loadGoals() {
    const fetchedGoals = await fetchGoals();
    setGoals(fetchedGoals);
    const entries = await Promise.all(
      fetchedGoals.map(async (g) => [g.id, await fetchMilestonesByGoal(g.id)] as const)
    );
    setMilestonesByGoal(Object.fromEntries(entries));
  }

  useEffect(() => {
    loadGoals();
  }, []);

  async function handleCreateGoal() {
    const title = newGoalTitle.trim();
    if (!title) return;
    setCreating(true);
    setCreateError(null);
    try {
      await createGoal({ title });
      setNewGoalTitle("");
      setShowCreateForm(false);
      await loadGoals();
    } catch {
      setCreateError("Couldn't create that goal — check your connection and try again.");
    } finally {
      setCreating(false);
    }
  }

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
        ) : goals.length === 0 ? (
          <div className="rounded border border-dashed border-outline-variant p-lg text-center">
            <Icon name="flag" size={32} className="mx-auto mb-sm text-on-surface-variant" />
            <p className="font-title-md text-title-md text-on-surface">No goals yet</p>
            <p className="mt-xs font-body-md text-on-surface-variant">
              Start your first goal and CHIOMA will help you break it into milestones.
            </p>
          </div>
        ) : (
          goals.map((goal) => {
            const milestones = milestonesByGoal[goal.id];
            const upNext = nextMilestone(milestones);
            const deadlineLabel = formatDeadline(goal.deadline);
            return (
              <Link
                key={goal.id}
                href={`/goals/milestones/${goal.id}`}
                className="flex flex-col gap-md rounded border border-outline-variant bg-surface-container-low p-md"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-title-md text-title-md mb-xs text-primary">{goal.title}</h3>
                    {deadlineLabel && (
                      <p className="font-label-sm text-label-sm text-on-surface-variant">Deadline: {deadlineLabel}</p>
                    )}
                  </div>
                  <ProgressRing progressPct={goal.progressPct} size={64} />
                </div>
                {upNext && (
                  <div className="rounded-lg border-l-4 border-primary bg-surface-bright p-sm">
                    <p className="mb-xs font-label-sm text-label-sm uppercase text-on-surface-variant">Next Milestone</p>
                    <p className="font-body-md font-semibold text-on-surface">{upNext.title}</p>
                  </div>
                )}
              </Link>
            );
          })
        )}
      </div>

      {showCreateForm ? (
        <div className="flex flex-col gap-sm rounded border border-outline-variant bg-surface-container-low p-md">
          {createError && <p role="alert" className="font-label-sm text-label-sm text-error">{createError}</p>}
          <label className="flex flex-col gap-sm">
            <span className="font-label-sm text-label-sm text-on-surface-variant">Goal title</span>
            <input
              autoFocus
              value={newGoalTitle}
              onChange={(e) => setNewGoalTitle(e.target.value)}
              placeholder="e.g. Start a Poultry Business"
              className="w-full rounded border border-outline-variant bg-surface-container-lowest p-md font-body-md text-body-md text-on-surface outline-none focus-visible:outline-primary"
            />
          </label>
          <div className="flex gap-sm">
            <Button
              variant="primary"
              className="flex-1"
              disabled={!newGoalTitle.trim() || creating}
              onClick={handleCreateGoal}
            >
              {creating ? "Creating..." : "Create Goal"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => {
                setShowCreateForm(false);
                setCreateError(null);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setShowCreateForm(true)}
          className="flex w-full items-center justify-center gap-md rounded-full bg-primary px-lg py-md text-on-primary shadow-md transition-transform active:scale-95 hover:opacity-90"
        >
          <Icon name="add" />
          <span className="font-title-md text-title-md">Create New Goal</span>
        </button>
      )}
    </main>
  );
}