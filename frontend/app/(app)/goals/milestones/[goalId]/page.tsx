"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import {
  completeMilestone,
  fetchCommitmentsByGoal,
  fetchGoalById,
  fetchMilestonesByGoal,
} from "@/lib/api";
import type { Commitment, Goal, Milestone } from "@/lib/types";
import { MilestoneRoad } from "@/components/ui/MilestoneRoad";
import { Skeleton } from "@/components/ui/Skeleton";

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

const commitmentStyles: Record<
  string,
  {
    icon: string;
    badge: string;
    card: string;
    label: string;
  }
> = {
  done: {
    icon: "check_circle",
    badge: "bg-secondary-container text-on-secondary-container",
    card: "border-outline-variant bg-surface-container-low",
    label: "Done",
  },
  in_progress: {
    icon: "pending",
    badge: "bg-primary-container text-on-primary-container",
    card: "border-outline-variant bg-surface-container-low",
    label: "In Progress",
  },
  blocked: {
    icon: "block",
    badge: "bg-error-container text-on-error-container",
    card: "border-error/40 bg-error-container/20",
    label: "Blocked",
  },
};

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

  useEffect(() => {
    dispatch({ type: "SET_ACTIVE_GOAL_ID", goalId: params.goalId });
    fetchGoalById(params.goalId).then(setGoal);
    fetchMilestonesByGoal(params.goalId).then(setMilestones);
    fetchCommitmentsByGoal(params.goalId).then(setCommitments);
  }, [params.goalId, dispatch]);

  async function handleCompleteMilestone(milestoneId: string) {
    await completeMilestone(milestoneId);

    const [refreshedGoal, refreshedMilestones] = await Promise.all([
      fetchGoalById(params.goalId),
      fetchMilestonesByGoal(params.goalId),
    ]);

    setGoal(refreshedGoal);
    setMilestones(refreshedMilestones);
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

            <h2 className="font-headline-lg-mobile text-headline-lg-mobile mt-xs text-on-background">
              {goal.title}
            </h2>

            {goal.deadline && (
              <p className="mt-xs font-body-md text-body-md text-on-surface-variant">
                Target:{" "}
                {new Date(goal.deadline).toLocaleDateString(undefined, {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </p>
            )}

            <div className="mt-xl">
              {milestones === null ? (
                <Skeleton className="h-64 w-full" />
              ) : (
                <MilestoneRoad
                  milestones={milestones}
                  onCompleteMilestone={handleCompleteMilestone}
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
                  : commitments.map((c) => {
                      const style = commitmentStyles[c.status];

                      if (!style) {
                        return null;
                      }

                      return (
                        <div
                          key={c.id}
                          className={`rounded border p-md ${style.card}`}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-sm">
                              <Icon
                                name={style.icon}
                                filled={c.status !== "blocked"}
                                className={
                                  c.status === "blocked"
                                    ? "text-error"
                                    : "text-secondary"
                                }
                              />

                              <span className="font-body-md text-body-md text-on-surface">
                                {sanitizeCommitmentContent(c.title)}
                              </span>
                            </div>

                            <span
                              className={`rounded-full px-sm py-xs font-label-sm text-[11px] font-bold ${style.badge}`}
                            >
                              {style.label}
                            </span>
                          </div>

                          {c.status === "blocked" && c.mentorHelpNote && (
                            <>
                              <button className="tap-target mt-md flex w-full items-center justify-center gap-xs rounded-full bg-primary py-sm font-label-sm text-label-sm text-on-primary transition-transform active:scale-95">
                                <Icon
                                  name="smart_toy"
                                  filled
                                  size={18}
                                />
                                CHIOMA CAN HELP
                              </button>

                              <p className="mt-xs text-center text-[12px] italic text-on-surface-variant">
                                &ldquo;{c.mentorHelpNote}&rdquo;
                              </p>
                            </>
                          )}
                        </div>
                      );
                    })}
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}