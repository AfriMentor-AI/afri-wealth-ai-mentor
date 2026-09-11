"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { createGoal, fetchGoals, fetchMilestonesByGoal } from "@/lib/api";
import type { Goal, Milestone } from "@/lib/types";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { useAppDispatch } from "@/lib/store";
import { EditGoalModal } from "@/components/EditGoalModal";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function activeGoalCount(goals: Goal[]): number {
  return goals.filter((g) => g.progressPct < 100).length;
}

function formatDeadline(deadline: string | undefined) {
  if (!deadline) return null;
  return new Date(deadline).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** Derive tag chips from available data — priority/category not in model yet,
 *  so we surface "Deadline Near" and "Blocked" from milestone state. */
function goalChips(
  goal: Goal,
  milestones: Milestone[] | undefined
): { label: string; variant: "priority" | "neutral" | "blocked" }[] {
  const chips: { label: string; variant: "priority" | "neutral" | "blocked" }[] = [];

  const hasBlocked = milestones?.some((m) => m.status === "blocked");
  if (hasBlocked) chips.push({ label: "Blocked", variant: "blocked" });

  if (goal.deadline) {
    const daysLeft =
      (new Date(goal.deadline).getTime() - Date.now()) / (1000 * 60 * 60 * 24);
    if (daysLeft >= 0 && daysLeft <= 14) {
      chips.push({ label: "Deadline Near", variant: "priority" });
    }
  }

  return chips;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ChipBadge({
  label,
  variant,
}: {
  label: string;
  variant: "priority" | "neutral" | "blocked";
}) {
  const cls =
    variant === "priority"
      ? "bg-secondary-container text-on-secondary-container"
      : variant === "blocked"
      ? "bg-error-container text-on-error-container"
      : "bg-surface-variant text-on-surface-variant";
  return (
    <span
      className={`px-sm py-xs text-label-sm font-label-sm rounded-full ${cls}`}
    >
      {label}
    </span>
  );
}

/** Milestone card used in the right-side roadmap panel. */
function MilestoneNode({
  milestone,
  isLast,
}: {
  milestone: Milestone;
  isLast: boolean;
}) {
  const statusStyles = {
    done: {
      node: "bg-secondary text-on-secondary",
      card: "bg-surface border border-outline-variant shadow-sm",
      label: "text-secondary",
      labelText: "Done",
    },
    in_progress: {
      node: "bg-primary text-on-primary animate-pulse-subtle",
      card: "bg-surface border-2 border-primary shadow-md",
      label: "text-primary",
      labelText: "Active",
    },
    blocked: {
      node: "bg-error text-on-error",
      card: "bg-error-container border border-error",
      label: "text-error",
      labelText: "Blocked",
    },
    upcoming: {
      node: "bg-surface-container border-2 border-outline-variant text-on-surface-variant",
      card: "bg-surface border border-outline-variant opacity-60",
      label: "text-on-surface-variant",
      labelText: "Upcoming",
    },
  };

  const s = statusStyles[milestone.status];

  return (
    <div className="relative">
      {/* Dashed connector line */}
      {!isLast && (
        <div
          aria-hidden
          className="absolute left-[-17px] top-6 h-[calc(100%+48px)] w-0.5"
          style={{
            backgroundImage:
              "linear-gradient(to bottom, var(--primary) 50%, rgba(255,255,255,0) 0%)",
            backgroundPosition: "right",
            backgroundSize: "2px 10px",
            backgroundRepeat: "repeat-y",
          }}
        />
      )}

      {/* Node dot */}
      <div
        className={`absolute left-[-26px] top-0 z-10 flex h-6 w-6 items-center justify-center rounded-full ${s.node}`}
      >
        {milestone.status === "done" ? (
          <Icon name="check" size={14} />
        ) : milestone.status === "in_progress" ? (
          <div className="h-2 w-2 rounded-full bg-white" />
        ) : milestone.status === "blocked" ? (
          <Icon name="priority_high" size={14} />
        ) : null}
      </div>

      {/* Card */}
      <div className={`rounded-lg p-md ${s.card}`}>
        <div className="flex items-start justify-between mb-xs">
          <h5 className="font-title-md text-title-md text-on-surface pr-sm">
            {milestone.title}
          </h5>
          <span className={`font-label-sm text-label-sm shrink-0 ${s.label}`}>
            {s.labelText}
          </span>
        </div>
        {milestone.status === "blocked" && (
          <button className="mt-sm flex items-center gap-xs font-label-sm text-label-sm text-on-error-container underline">
            <Icon name="auto_fix" size={14} />
            Ask AI for solution
          </button>
        )}
      </div>
    </div>
  );
}

/** Inline right-side roadmap panel (desktop only). */
function GoalRoadmapPanel({
  goal,
  milestones,
  onClose,
  onEdit,
}: {
  goal: Goal;
  milestones: Milestone[] | undefined;
  onClose: () => void;
  onEdit: () => void;
}) {
  const nextSuggestedStep = milestones?.find(
    (m) => m.status === "in_progress" || m.status === "blocked"
  );

  return (
    <aside className="hidden lg:flex w-[420px] shrink-0 flex-col border-l border-outline-variant bg-surface-container-low overflow-hidden">
      {/* Panel header */}
      <header className="border-b border-outline-variant bg-surface p-lg">
        <div className="flex items-center justify-between mb-sm">
          <span className="font-label-sm text-label-sm uppercase tracking-widest text-primary">
            Active Roadmap
          </span>
          <div className="flex items-center gap-xs">
            <button
              type="button"
              onClick={onEdit}
              aria-label="Edit goal"
              className="flex items-center gap-1 rounded-full border border-outline-variant px-sm py-0.5 text-xs font-semibold text-on-surface hover:bg-surface-variant transition-colors"
            >
              <Icon name="edit" size={14} />
              Edit
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close roadmap panel"
              title="Close roadmap panel"
              className="text-on-surface-variant hover:text-on-surface transition-colors p-1"
            >
              <Icon name="close" size={20} />
            </button>
          </div>
        </div>
        <h3 className="font-headline-lg text-headline-lg text-on-surface">
          {goal.title}
        </h3>
        {goal.description && (
          <p className="mt-xs text-xs text-on-surface-variant line-clamp-2">{goal.description}</p>
        )}
      </header>

      {/* Milestone path */}
      <div className="flex-grow overflow-y-auto p-lg">
        {milestones === undefined ? (
          <div className="flex flex-col gap-md">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full rounded-lg" />
            ))}
          </div>
        ) : milestones.length === 0 ? (
          <p className="font-body-md text-on-surface-variant">
            No milestones yet for this goal.
          </p>
        ) : (
          <div className="relative pl-8 flex flex-col gap-xl">
            {milestones.map((m, i) => (
              <MilestoneNode
                key={m.id}
                milestone={m}
                isLast={i === milestones.length - 1}
              />
            ))}
          </div>
        )}
      </div>

      {/* Panel footer */}
      <footer className="border-t border-outline-variant bg-surface-container p-lg flex flex-col gap-md">
        <div className="flex items-center justify-between">
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            Next suggested step
          </span>
          <Icon name="lightbulb" className="text-primary" size={20} />
        </div>
        <div className="rounded-lg border border-primary-fixed-dim bg-primary-fixed p-md">
          {nextSuggestedStep ? (
            <p className="font-label-sm text-label-sm text-on-primary-fixed-variant">
              &ldquo;Focus on completing &lsquo;{nextSuggestedStep.title}&rsquo; to keep
              your goal on track.&rdquo;
            </p>
          ) : (
            <p className="font-label-sm text-label-sm text-on-primary-fixed-variant">
              &ldquo;Great progress! Keep the momentum going.&rdquo;
            </p>
          )}
        </div>
        <Link
          href={`/goals/milestones/${goal.id}`}
          className="block w-full rounded-full bg-secondary py-md text-center font-title-md text-title-md text-on-secondary transition-all hover:opacity-90 active:scale-95"
        >
          Update Goal Progress
        </Link>
      </footer>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function GoalsOverviewPage() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [milestonesByGoal, setMilestonesByGoal] = useState<
    Record<string, Milestone[]>
  >({});
  const [activeGoalId, setActiveGoalId] = useState<string | null>(null);
  const [isRoadmapCollapsed, setIsRoadmapCollapsed] = useState(false);
  const [editingGoal, setEditingGoal] = useState<Goal | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newGoalTitle, setNewGoalTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const loadGoals = useCallback(async () => {
    const fetchedGoals = await fetchGoals();
    setGoals(fetchedGoals);
    const entries = await Promise.all(
      fetchedGoals.map(
        async (g) => [g.id, await fetchMilestonesByGoal(g.id)] as const
      )
    );
    setMilestonesByGoal(Object.fromEntries(entries));
    // Auto-open first goal's panel if none selected
    if (!activeGoalId && fetchedGoals.length > 0) {
      setActiveGoalId(fetchedGoals[0].id);
    }
  }, [activeGoalId]);

  useEffect(() => {
    loadGoals();
    const handleGoalCreated = () => {
      loadGoals();
    };
    window.addEventListener("goal-created", handleGoalCreated);
    return () => {
      window.removeEventListener("goal-created", handleGoalCreated);
    };
  }, [loadGoals]);

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
      setCreateError(
        "Couldn't create that goal — check your connection and try again."
      );
    } finally {
      setCreating(false);
    }
  }

  const activeGoal =
    activeGoalId && goals ? goals.find((g) => g.id === activeGoalId) : null;
  const activeMilestones = activeGoalId
    ? milestonesByGoal[activeGoalId]
    : undefined;

  return (
    <div className="flex h-full min-h-screen">
      {/* ------------------------------------------------------------------ */}
      {/* Main content area                                                   */}
      {/* ------------------------------------------------------------------ */}
      <main className="flex-grow overflow-y-auto px-margin-mobile pb-xl pt-lg lg:px-xl lg:pt-xl">
        <div className="mx-auto max-w-4xl">
          {/* Header */}
          <header className="mb-xl flex items-end justify-between">
            <div>
              <h2 className="font-headline-xl text-headline-xl text-on-background mb-sm">
                Your Aspirations
              </h2>
              <p className="font-body-lg text-body-lg text-on-surface-variant">
                Guided steps towards communal and personal prosperity.
              </p>
            </div>
            {goals !== null && goals.length > 0 && (
              <div className="flex shrink-0 items-center gap-sm">
                <div className="flex shrink-0 items-center gap-sm rounded-lg border border-outline-variant bg-surface-container px-md py-sm">
                  <Icon name="emoji_events" className="text-primary" size={20} />
                  <span className="font-label-sm text-label-sm text-on-surface">
                    {activeGoalCount(goals)} Active Goal
                    {activeGoalCount(goals) !== 1 ? "s" : ""}
                  </span>
                </div>
                {activeGoal && (
                  <button
                    type="button"
                    onClick={() => setIsRoadmapCollapsed((prev) => !prev)}
                    className="hidden lg:flex items-center gap-xs rounded-lg border border-outline-variant bg-surface-container px-md py-sm text-xs font-semibold text-on-surface hover:bg-surface-variant transition-colors"
                    title={isRoadmapCollapsed ? "Show active roadmap" : "Hide active roadmap"}
                  >
                    <Icon
                      name={isRoadmapCollapsed ? "view_sidebar" : "dock_to_right"}
                      size={18}
                      className="text-primary"
                    />
                    <span>{isRoadmapCollapsed ? "Show Roadmap" : "Hide Roadmap"}</span>
                  </button>
                )}
              </div>
            )}
          </header>

          {/* Goal grid */}
          <div className="grid grid-cols-1 gap-lg md:grid-cols-2">
            {goals === null ? (
              Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-52 w-full rounded-xl" />
              ))
            ) : goals.length === 0 ? (
              <>
                {/* Empty state */}
                <div className="col-span-full rounded-xl border border-dashed border-outline-variant p-lg text-center">
                  <Icon
                    name="flag"
                    size={32}
                    className="mx-auto mb-sm text-on-surface-variant"
                  />
                  <p className="font-title-md text-title-md text-on-surface">
                    No goals yet
                  </p>
                  <p className="mt-xs font-body-md text-on-surface-variant">
                    Start your first goal and CHIOMA will help you break it into
                    milestones.
                  </p>
                  <button
                    type="button"
                    onClick={() => dispatch({ type: "OPEN_NEW_GOAL_MODAL" })}
                    className="mt-md inline-flex items-center gap-xs rounded-full bg-primary px-lg py-sm font-title-md text-title-md text-on-primary transition-opacity hover:opacity-90 active:scale-95"
                  >
                    <Icon name="add" size={18} />
                    Create Your First Goal
                  </button>
                </div>
              </>
            ) : (
              <>
                {goals.map((goal) => {
                  const milestones = milestonesByGoal[goal.id];
                  const deadlineLabel = formatDeadline(goal.deadline);
                  const chips = goalChips(goal, milestones);
                  const isActive = goal.id === activeGoalId;

                  return (
                    <div
                      key={goal.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => {
                        router.push(`/goals/milestones/${goal.id}`);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          router.push(`/goals/milestones/${goal.id}`);
                        }
                      }}
                      className="flex cursor-pointer flex-col gap-md rounded-xl border border-outline-variant bg-surface-container-low p-lg transition-all hover:bg-surface-container-high hover:shadow-md focus-visible:outline-2 focus-visible:outline-primary"
                    >
                      {/* Top row: icon + edit button + progress ring */}
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-sm">
                          <div
                            className={`rounded-lg p-sm ${
                              isActive ? "bg-primary-fixed" : "bg-surface-variant"
                            }`}
                          >
                            <Icon
                              name="ads_click"
                              size={24}
                              className={
                                isActive
                                  ? "text-primary"
                                  : "text-on-surface-variant"
                              }
                            />
                          </div>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setEditingGoal(goal);
                            }}
                            title="Edit goal"
                            className="flex h-8 w-8 items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-variant hover:text-on-surface transition-colors"
                          >
                            <Icon name="edit" size={16} />
                          </button>
                        </div>
                        <ProgressRing progressPct={goal.progressPct} size={64} />
                      </div>

                      {/* Title + description */}
                      <div>
                        <h3 className="font-headline-lg text-headline-lg text-on-surface">
                          {goal.title}
                        </h3>
                        {goal.description && (
                          <p className="mt-sm font-body-md text-body-md text-on-surface-variant">
                            {goal.description}
                          </p>
                        )}
                        {!goal.description && deadlineLabel && (
                          <p className="mt-sm font-body-md text-body-md text-on-surface-variant">
                            Target: {deadlineLabel}
                          </p>
                        )}
                      </div>

                      {/* Tag chips */}
                      {chips.length > 0 && (
                        <div className="mt-auto flex flex-wrap gap-xs">
                          {chips.map((chip) => (
                            <ChipBadge
                              key={chip.label}
                              label={chip.label}
                              variant={chip.variant}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* "Define New Purpose" dashed card */}
                <button
                  type="button"
                  onClick={() => dispatch({ type: "OPEN_NEW_GOAL_MODAL" })}
                  className="group flex flex-col items-center justify-center gap-md rounded-xl border-2 border-dashed border-outline-variant p-xl transition-all hover:border-primary"
                >
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-surface-container transition-colors group-hover:bg-primary-fixed">
                    <Icon
                      name="add_circle"
                      size={24}
                      className="text-on-surface-variant group-hover:text-primary"
                    />
                  </div>
                  <span className="font-title-md text-title-md text-on-surface-variant">
                    Define New Purpose
                  </span>
                </button>
              </>
            )}
          </div>

          {/* Create form (shown inline, spans full grid width) */}
          {showCreateForm && (
            <div className="mt-lg flex flex-col gap-sm rounded-xl border border-outline-variant bg-surface-container-low p-lg">
              {createError && (
                <p role="alert" className="font-label-sm text-label-sm text-error">
                  {createError}
                </p>
              )}
              <label className="flex flex-col gap-sm">
                <span className="font-label-sm text-label-sm text-on-surface-variant">
                  Goal title
                </span>
                <input
                  autoFocus
                  value={newGoalTitle}
                  onChange={(e) => setNewGoalTitle(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleCreateGoal();
                  }}
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
          )}

          {/* ---------------------------------------------------------------- */}
          {/* Mentor Insight — Sankofa Banner                                  */}
          {/* ---------------------------------------------------------------- */}
          <div className="relative mt-xl overflow-hidden rounded-xl border border-outline-variant bg-surface-container p-lg">
            <div className="relative z-10">
              <h4 className="flex items-center gap-sm font-title-md text-title-md text-primary">
                <Icon name="menu_book" size={20} />
                Mentor Insight: Sankofa
              </h4>
              <p className="mt-sm max-w-2xl font-body-md text-body-md text-on-surface-variant">
                &ldquo;Remember that to move forward, we must look to the wisdom of
                our past. Your goals today draw from a heritage of resilience and
                trade excellence.&rdquo;
              </p>
            </div>
            {/* Decorative background icon */}
            <div className="pointer-events-none absolute bottom-[-20px] right-[-20px] opacity-10">
              <Icon name="psychology" size={120} className="text-primary" />
            </div>
          </div>
        </div>
      </main>

      {/* ------------------------------------------------------------------ */}
      {/* Right-side roadmap panel (desktop only)                             */}
      {/* ------------------------------------------------------------------ */}
      {activeGoal && !isRoadmapCollapsed && (
        <GoalRoadmapPanel
          goal={activeGoal}
          milestones={activeMilestones}
          onClose={() => setIsRoadmapCollapsed(true)}
          onEdit={() => setEditingGoal(activeGoal)}
        />
      )}


      {/* ------------------------------------------------------------------ */}
      {/* FAB — new goal (mobile)                                             */}
      {/* ------------------------------------------------------------------ */}
      {goals !== null && (
        <button
          onClick={() => dispatch({ type: "OPEN_NEW_GOAL_MODAL" })}
          aria-label="New goal"
          className="fixed bottom-lg right-lg z-30 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-on-primary shadow-lg transition-all hover:scale-105 active:scale-95 lg:hidden"
        >
          <Icon name="add" filled size={24} />
        </button>
      )}

      {/* Edit Goal Modal */}
      <EditGoalModal
        goal={editingGoal}
        isOpen={!!editingGoal}
        onClose={() => setEditingGoal(null)}
        onGoalUpdated={() => {
          loadGoals();
        }}
        onGoalDeleted={() => {
          setActiveGoalId(null);
          loadGoals();
        }}
      />
    </div>
  );
}