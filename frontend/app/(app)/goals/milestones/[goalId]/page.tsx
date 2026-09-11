"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import {
  completeMilestone,
  createMilestone,
  deleteMilestone,
  fetchCommitmentsByGoal,
  fetchGoalById,
  fetchMilestonesByGoal,
  updateMilestone,
} from "@/lib/api";
import type { Commitment, Goal, Milestone } from "@/lib/types";
import { MilestoneRoad } from "@/components/ui/MilestoneRoad";
import { Skeleton } from "@/components/ui/Skeleton";
import { EditGoalModal } from "@/components/EditGoalModal";

import { useAppDispatch } from "@/lib/store";
import { Fragment } from "react";

/** Strip markdown and render <br> as line breaks for commitment content. */
function sanitizeCommitmentContent(text: string): React.ReactNode {
  const cleaned = text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\*\*(.+?)\*\*/g, "$1")  // strip bold
    .replace(/\*(.+?)\*/g, "$1")       // strip italic
    .replace(/#{1,6}\s+/g, "")         // strip headings
    .replace(/\|[-:\s|]+\|/g, "")      // strip table dividers
    .trim();

  const segments = cleaned.split(/<br\s*\/?>/i);
  if (segments.length === 1) return cleaned;
  return (
    <>
      {segments.map((seg, i) => (
        <Fragment key={i}>
          {i > 0 && <br />}
          {seg}
        </Fragment>
      ))}
    </>
  );
}



export default function GoalMilestonePathPage({
  params,
}: {
  params: { goalId: string };
}) {
  const router = useRouter();
  const dispatch = useAppDispatch();

  const [goal, setGoal] = useState<Goal | null | undefined>(null);
  const [milestones, setMilestones] = useState<Milestone[] | null>(null);
  const [commitments, setCommitments] = useState<Commitment[] | null>(null);
  const [isEditGoalOpen, setIsEditGoalOpen] = useState(false);

  useEffect(() => {
    dispatch({ type: "SET_ACTIVE_GOAL_ID", goalId: params.goalId });
    fetchGoalById(params.goalId).then(setGoal);
    fetchMilestonesByGoal(params.goalId).then(setMilestones);
    fetchCommitmentsByGoal(params.goalId).then(setCommitments);
  }, [params.goalId, dispatch]);

  async function reloadData() {
    const [refreshedGoal, refreshedMilestones] = await Promise.all([
      fetchGoalById(params.goalId),
      fetchMilestonesByGoal(params.goalId),
    ]);
    setGoal(refreshedGoal);
    setMilestones(refreshedMilestones);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("goal-created", { detail: refreshedGoal }));
    }
  }

  async function handleCompleteMilestone(milestoneId: string) {
    await completeMilestone(milestoneId);
    await reloadData();
  }

  async function handleUpdateMilestone(
    milestoneId: string,
    updates: { title?: string; status?: Milestone["status"] }
  ) {
    await updateMilestone(milestoneId, updates);
    await reloadData();
  }

  async function handleDeleteMilestone(milestoneId: string) {
    await deleteMilestone(milestoneId);
    await reloadData();
  }

  async function handleCreateMilestone(input: {
    title: string;
    status?: Milestone["status"];
  }) {
    await createMilestone(params.goalId, input);
    await reloadData();
  }

  return (
    <div className="min-h-screen">
      <header className="flex items-center gap-sm px-margin-mobile py-md">
        <button
          onClick={() => router.back()}
          aria-label="Go back"
          className="tap-target flex items-center justify-center rounded-full text-primary"
        >
          <Icon name="arrow_back" />
        </button>

        <span className="font-title-md text-title-md">
          AfriMentor AI
        </span>
      </header>

      <main className="px-margin-mobile pb-24">
        {goal === null ? (
          <div className="flex flex-col gap-md">
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-64 w-full" />
          </div>
        ) : goal === undefined ? (
          <p className="font-body-md text-on-surface-variant">
            This goal couldn&rsquo;t be found.
          </p>
        ) : (
          <>
            <p className="font-label-sm text-label-sm uppercase text-on-surface-variant">
              Active Goal
            </p>

            <div className="mt-xs flex items-start justify-between gap-sm">
              <div>
                <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-on-background">
                  {goal.title}
                </h2>
                {goal.description && (
                  <p className="mt-xs font-body-md text-body-md text-on-surface-variant">
                    {goal.description}
                  </p>
                )}
                {goal.deadline && (
                  <p className="mt-xs font-label-sm text-label-sm text-on-surface-variant">
                    Target:{" "}
                    {new Date(goal.deadline).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })}
                  </p>
                )}
              </div>

              <button
                type="button"
                onClick={() => setIsEditGoalOpen(true)}
                className="flex items-center gap-xs rounded-full border border-outline-variant bg-surface-container-low px-md py-xs text-xs font-semibold text-on-surface hover:bg-surface-variant active:scale-95 transition-all shrink-0"
              >
                <Icon name="edit" size={16} />
                <span>Edit Goal</span>
              </button>
            </div>

            <div className="mt-xl">
              {milestones === null ? (
                <Skeleton className="h-64 w-full" />
              ) : (
                <MilestoneRoad
                  milestones={milestones}
                  onCompleteMilestone={handleCompleteMilestone}
                  onUpdateMilestone={handleUpdateMilestone}
                  onDeleteMilestone={handleDeleteMilestone}
                  onCreateMilestone={handleCreateMilestone}
                />
              )}
            </div>

            <section className="mt-xl">
              <h3 className="font-title-md text-title-md mb-md text-on-surface">
                Tagged Commitments
              </h3>

              <div className="flex flex-col gap-sm">
                {commitments === null
                  ? Array.from({ length: 3 }).map((_, i) => (
                      <Skeleton
                        key={i}
                        className="h-16 w-full rounded"
                      />
                    ))
                  : commitments.map((c) => (
                      <div
                        key={c.id}
                        className="rounded border border-outline-variant bg-surface-container-low p-md"
                      >
                        <div className="flex items-start gap-sm">
                          <Icon
                            name="bookmark"
                            filled
                            className="mt-[2px] shrink-0 text-secondary"
                          />
                          <span className="font-body-md text-body-md text-on-surface">
                            {sanitizeCommitmentContent(c.title)}
                          </span>
                        </div>
                        <p className="mt-xs font-label-sm text-[11px] text-on-surface-variant">
                          Tagged {new Date(c.createdAt).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })}
                        </p>
                      </div>
                    ))}
              </div>
            </section>

            <EditGoalModal
              goal={goal || null}
              isOpen={isEditGoalOpen}
              onClose={() => setIsEditGoalOpen(false)}
              onGoalUpdated={(updated) => {
                setGoal(updated);
                if (typeof window !== "undefined") {
                  window.dispatchEvent(new CustomEvent("goal-created", { detail: updated }));
                }
              }}
              onGoalDeleted={() => {
                if (typeof window !== "undefined") {
                  window.dispatchEvent(new CustomEvent("goal-created", { detail: null }));
                }
                router.replace("/goals");
              }}
            />
          </>
        )}
      </main>
    </div>
  );
}