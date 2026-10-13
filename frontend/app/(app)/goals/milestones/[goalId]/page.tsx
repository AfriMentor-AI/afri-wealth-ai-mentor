"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { AppFrame, KenteStrip } from "@/components/shell/AppSidebar";
import { MilestoneTimeline } from "@/components/goals/MilestoneTimeline";
import { EditGoalModal } from "@/components/goals/GoalModals";
import { ProgressRing } from "@/components/goals/ProgressRing";
import { completeMilestone, createMilestone, deleteMilestone, fetchCommitmentsByGoal, fetchGoalById, fetchMilestonesByGoal, updateMilestone } from "@/lib/api";
import type { Commitment, Goal, Milestone } from "@/lib/types";
import { useAppDispatch } from "@/lib/store";

/** Strip markdown and render <br> as line breaks for commitment content. */
function cleanCommitment(text: string): React.ReactNode {
  const cleaned = text
    .replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'")
    .replace(/\*\*(.+?)\*\*/g, "$1").replace(/\*(.+?)\*/g, "$1").replace(/#{1,6}\s+/g, "").replace(/\|[-:\s|]+\|/g, "").trim();
  const parts = cleaned.split(/<br\s*\/?>/i);
  if (parts.length === 1) return cleaned;
  return <>{parts.map((s, i) => <Fragment key={i}>{i > 0 && <br />}{s}</Fragment>)}</>;
}

const fmt = (d: string, long = false) => new Date(d).toLocaleDateString(undefined, { year: "numeric", month: long ? "long" : "short", day: "numeric" });

export default function GoalMilestonePathPage({ params }: { params: { goalId: string } }) {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const [goal, setGoal] = useState<Goal | null | undefined>(null);
  const [milestones, setMilestones] = useState<Milestone[] | null>(null);
  const [commitments, setCommitments] = useState<Commitment[] | null>(null);
  const [editOpen, setEditOpen] = useState(false);

  useEffect(() => {
    dispatch({ type: "SET_ACTIVE_GOAL_ID", goalId: params.goalId });
    fetchGoalById(params.goalId).then(setGoal).catch(() => setGoal(undefined));
    fetchMilestonesByGoal(params.goalId).then(setMilestones).catch(() => setMilestones([]));
    fetchCommitmentsByGoal(params.goalId).then(setCommitments).catch(() => setCommitments([]));
  }, [params.goalId, dispatch]);

  const reload = useCallback(async () => {
    const [g, m] = await Promise.all([fetchGoalById(params.goalId), fetchMilestonesByGoal(params.goalId)]);
    setGoal(g);
    setMilestones(m);
    window.dispatchEvent(new CustomEvent("goal-created", { detail: g }));
  }, [params.goalId]);

  const active = milestones?.find((m) => m.status === "in_progress" || m.status === "blocked");

  return (
    <AppFrame title="Milestones">
      <KenteStrip />
      <main className="mx-auto max-w-4xl px-5 pb-16 pt-6 md:px-10 md:pt-10">
        <nav className="mb-5 flex items-center gap-2 font-caption text-caption text-on-surface-variant" aria-label="Breadcrumb">
          <Link href="/goals" className="flex items-center gap-1 hover:text-primary"><Icon name="arrow_back" size={16} /> Goals</Link>
          <span>/</span><span className="max-w-[40vw] truncate">{goal ? goal.title : "…"}</span><span>/</span><span className="text-primary">Milestones roadmap</span>
        </nav>

        {goal === null ? (
          <div className="h-48 animate-pulse rounded-3xl bg-surface-container-low" />
        ) : goal === undefined ? (
          <p className="font-body-md text-on-surface-variant">This goal couldn’t be found.</p>
        ) : (
          <>
            <section className="flex flex-col gap-5 rounded-3xl border border-outline-variant bg-surface-container-lowest p-6 shadow-sm md:flex-row md:items-center md:justify-between md:p-8">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  {goal.deadline && <span className="rounded-full bg-gold-mist px-3 py-1 font-eyebrow text-eyebrow uppercase text-sunburst-gold">Target: {fmt(goal.deadline, true)}</span>}
                  <span className="font-caption text-caption text-on-surface-variant">Updated {fmt(goal.updatedAt)}</span>
                </div>
                <h1 className="mt-3 font-headline-lg-mobile text-headline-lg-mobile text-on-surface md:font-headline-lg md:text-headline-lg">{goal.title}</h1>
                {goal.description && <p className="mt-2 max-w-xl font-body-md text-body-md text-on-surface-variant">{goal.description}</p>}
                <button type="button" onClick={() => setEditOpen(true)} className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-outline-variant px-4 py-1.5 font-label-sm text-label-sm text-on-surface hover:bg-surface-container-low"><Icon name="edit" size={16} /> Edit goal</button>
              </div>
              <ProgressRing progressPct={goal.progressPct} size={104} caption="complete" />
            </section>

            <section className="mt-10">
              <h2 className="mb-5 font-title-md text-title-md text-on-surface">Milestone pathway</h2>
              {milestones === null ? (
                <div className="h-64 animate-pulse rounded-3xl bg-surface-container-low" />
              ) : (
                <MilestoneTimeline
                  milestones={milestones}
                  onComplete={async (id) => { await completeMilestone(id); await reload(); }}
                  onUpdate={async (id, u) => { await updateMilestone(id, u); await reload(); }}
                  onDelete={async (id) => { await deleteMilestone(id); await reload(); }}
                  onCreate={async (i) => { await createMilestone(params.goalId, i); await reload(); }}
                />
              )}
            </section>

            {active && (
              <Link href="/goals/action" className="mt-8 flex items-center justify-between gap-4 rounded-2xl border border-sunburst-gold/60 bg-gold-mist p-5">
                <div><p className="font-eyebrow text-eyebrow uppercase text-sunburst-gold">Next step</p><p className="mt-1 font-title-md text-[18px] text-on-surface">{active.title}</p></div>
                <Icon name="arrow_forward" className="text-on-surface" />
              </Link>
            )}

            <section className="mt-10">
              <h2 className="mb-4 font-title-md text-title-md text-on-surface">Tagged commitments</h2>
              <div className="flex flex-col gap-3">
                {commitments === null ? (
                  Array.from({ length: 2 }).map((_, i) => <div key={i} className="h-16 animate-pulse rounded-2xl bg-surface-container-low" />)
                ) : commitments.length === 0 ? (
                  <p className="rounded-2xl border border-dashed border-outline-variant p-5 font-body-md text-body-md text-on-surface-variant">No commitments tagged yet. Tag one in a conversation with your mentor and it will appear here.</p>
                ) : (
                  commitments.map((c) => (
                    <div key={c.id} className="rounded-2xl border-l-4 border-sunburst-gold bg-surface-container-low p-4">
                      <div className="flex items-start gap-3"><Icon name="bookmark" filled className="mt-0.5 shrink-0 text-sunburst-gold" size={20} /><span className="font-quote text-[17px] italic leading-6 text-on-surface">{cleanCommitment(c.title)}</span></div>
                      <p className="mt-2 font-caption text-caption text-on-surface-variant">Tagged {fmt(c.createdAt)}</p>
                    </div>
                  ))
                )}
              </div>
            </section>

            <EditGoalModal
              goal={goal}
              isOpen={editOpen}
              onClose={() => setEditOpen(false)}
              onGoalUpdated={(u) => { setGoal(u); window.dispatchEvent(new CustomEvent("goal-created", { detail: u })); }}
              onGoalDeleted={() => { window.dispatchEvent(new CustomEvent("goal-created", { detail: null })); router.replace("/goals"); }}
            />
          </>
        )}
      </main>
    </AppFrame>
  );
}
