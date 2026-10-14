"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { AppFrame, KenteStrip } from "@/components/shell/AppSidebar";
import { ProgressRing } from "@/components/goals/ProgressRing";
import { EditGoalModal } from "@/components/goals/GoalModals";
import { fetchGoals, fetchMilestonesByGoal } from "@/lib/api";
import type { Goal, Milestone } from "@/lib/types";
import { useAppDispatch, useAppState } from "@/lib/store";
import { mentorFor } from "@/lib/mentors";

const fmt = (d?: string) => (d ? new Date(d).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : null);
const daysLeft = (d?: string) => (d ? Math.ceil((new Date(d).getTime() - Date.now()) / 86400000) : null);

function chips(goal: Goal, ms?: Milestone[]) {
  const out: { label: string; cls: string }[] = [];
  if (ms?.some((m) => m.status === "blocked")) out.push({ label: "Blocked", cls: "bg-error-container text-on-error-container" });
  const dl = daysLeft(goal.deadline);
  if (dl !== null && dl >= 0 && dl <= 14) out.push({ label: "Deadline near", cls: "bg-gold-mist text-sunburst-gold" });
  if (goal.progressPct >= 100) out.push({ label: "Complete", cls: "bg-primary/15 text-primary" });
  return out;
}

const nextStep = (ms?: Milestone[]) => ms?.find((m) => m.status === "in_progress" || m.status === "blocked") ?? ms?.find((m) => m.status === "upcoming");

function Pathway({ ms }: { ms: Milestone[] }) {
  return (
    <ol className="relative">
      {ms.map((m, i) => (
        <li key={m.id} className="relative flex gap-3 pb-5 last:pb-0">
          {i < ms.length - 1 && <span aria-hidden className={`absolute left-[13px] top-7 h-[calc(100%-1.25rem)] w-0.5 ${m.status === "done" ? "bg-primary" : "border-l-2 border-dashed border-outline-variant"}`} />}
          <span className={`z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${m.status === "done" ? "bg-primary text-on-primary" : m.status === "in_progress" ? "bg-sunburst-gold text-ink ring-4 ring-sunburst-gold/30" : m.status === "blocked" ? "bg-error text-on-error" : "border-2 border-outline-variant bg-surface-container-low"}`}>
            {m.status === "done" ? <Icon name="check" size={16} /> : m.status === "in_progress" ? <Icon name="hourglass_top" size={14} /> : m.status === "blocked" ? <Icon name="priority_high" size={16} /> : null}
          </span>
          <div className="min-w-0">
            <p className={`font-label-sm text-[15px] ${m.status === "done" ? "text-on-surface-variant line-through" : m.status === "upcoming" ? "text-on-surface-variant" : "font-bold text-on-surface"}`}>
              {m.title}
              {m.status === "in_progress" && <span className="ml-2 rounded bg-gold-mist px-1.5 py-0.5 font-eyebrow text-[9px] uppercase text-sunburst-gold">Current</span>}
              {m.status === "blocked" && <span className="ml-2 rounded bg-error-container px-1.5 py-0.5 font-eyebrow text-[9px] uppercase text-on-error-container">Blocked</span>}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}

export default function GoalsPage() {
  const dispatch = useAppDispatch();
  const { selectedPersona: persona } = useAppState();
  const mentor = mentorFor(persona);
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [byGoal, setByGoal] = useState<Record<string, Milestone[]>>({});
  const [activeId, setActiveId] = useState<string | null>(null);
  const [editing, setEditing] = useState<Goal | null>(null);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(async () => {
    try {
      const gs = await fetchGoals();
      setGoals(gs);
      setLoadError(false);
      const entries = await Promise.all(gs.map(async (g) => [g.id, await fetchMilestonesByGoal(g.id).catch(() => [] as Milestone[])] as const));
      setByGoal(Object.fromEntries(entries));
      setActiveId((cur) => (cur && gs.some((g) => g.id === cur) ? cur : gs[0]?.id ?? null));
    } catch {
      setGoals((g) => g ?? []);
      setLoadError(true);
    }
  }, []);

  useEffect(() => {
    load();
    const h = () => load();
    window.addEventListener("goal-created", h);
    return () => window.removeEventListener("goal-created", h);
  }, [load]);

  const openNew = () => dispatch({ type: "OPEN_NEW_GOAL_MODAL" });
  const active = goals?.find((g) => g.id === activeId) ?? null;
  const activeMs = activeId ? byGoal[activeId] : undefined;
  const open = goals?.filter((g) => g.progressPct < 100) ?? [];
  const avg = goals && goals.length ? Math.round(goals.reduce((s, g) => s + g.progressPct, 0) / goals.length) : 0;
  const soonest = open.filter((g) => g.deadline).sort((a, b) => +new Date(a.deadline!) - +new Date(b.deadline!))[0];
  const sd = soonest ? daysLeft(soonest.deadline) : null;

  const newBtn = (
    <button type="button" onClick={openNew} className="flex h-11 shrink-0 items-center gap-2 whitespace-nowrap rounded-full bg-primary px-5 font-label-sm text-[15px] font-bold text-on-primary shadow-md transition-all hover:opacity-90 active:scale-[0.98]">
      <Icon name="add" size={20} /> New goal
    </button>
  );

  return (
    <AppFrame title="Goals" mobileRight={undefined}>
      <KenteStrip />
      <div className="mx-auto flex max-w-[1280px] flex-col gap-8 px-5 pb-16 pt-6 md:px-10 md:pt-10 xl:flex-row">
        <main className="min-w-0 flex-1">
          <header className="flex items-end justify-between gap-4">
            <div className="min-w-0">
              <p className="font-eyebrow text-eyebrow uppercase text-on-surface-variant"><span className="text-sunburst-gold">●</span> Financial fortitude · Milestone tracker</p>
              <h1 className="mt-2 font-headline-xl-mobile text-headline-xl-mobile text-on-surface md:font-headline-xl md:text-[52px] md:leading-[58px]">Goals</h1>
              <p className="mt-2 max-w-xl font-quote text-[18px] italic leading-7 text-on-surface-variant">Anchor your enterprise ambitions in ancestral milestones and steady, verified progress.</p>
            </div>
            <div className="hidden sm:block">{newBtn}</div>
          </header>

          {goals !== null && goals.length > 0 && (
            <div className="mt-6 flex gap-3 overflow-x-auto pb-1 md:grid md:grid-cols-3 md:overflow-visible">
              {[
                { icon: "track_changes", label: "Active portfolio", value: `${open.length} strategic goal${open.length === 1 ? "" : "s"}` },
                { icon: "trending_up", label: "Average progress", value: `${avg}% complete` },
                { icon: "alarm", label: "Imminent deadline", value: soonest && sd !== null ? (sd < 0 ? `${soonest.title} · overdue` : sd === 0 ? "Due today" : `Due in ${sd} day${sd === 1 ? "" : "s"}`) : "None set", warn: sd !== null && sd <= 7 },
              ].map((s) => (
                <div key={s.label} className="flex min-w-[220px] shrink-0 items-center gap-3 rounded-2xl border border-outline-variant bg-surface-container-lowest px-4 py-3 md:min-w-0">
                  <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${s.warn ? "bg-error-container text-error" : "bg-gold-mist text-sunburst-gold"}`}><Icon name={s.icon} size={22} /></span>
                  <div className="min-w-0"><p className="font-eyebrow text-[10px] uppercase text-on-surface-variant">{s.label}</p><p className={`truncate font-label-sm text-[14px] ${s.warn ? "text-error" : "text-on-surface"}`}>{s.value}</p></div>
                </div>
              ))}
            </div>
          )}

          {loadError && <p role="alert" className="mt-6 rounded-xl bg-error-container px-4 py-3 font-label-sm text-label-sm text-on-error-container">Couldn’t load your goals. <button className="underline" onClick={load}>Try again</button></p>}

          <div className="mt-8 flex flex-col gap-6">
            {goals === null ? (
              Array.from({ length: 2 }).map((_, i) => <div key={i} className="h-64 animate-pulse rounded-3xl bg-surface-container-low" />)
            ) : goals.length === 0 && !loadError ? (
              <div className="rounded-3xl border-2 border-dashed border-outline-variant p-10 text-center">
                <Icon name="flag" size={36} className="text-on-surface-variant" />
                <p className="mt-2 font-title-md text-title-md text-on-surface">No goals yet</p>
                <p className="mx-auto mt-1 max-w-sm font-body-md text-body-md text-on-surface-variant">Start your first goal and {mentor.name.split(" ")[0]} will help you break it into milestones.</p>
                <div className="mt-5 inline-block">{newBtn}</div>
              </div>
            ) : (
              <>
                {goals.map((g) => {
                  const ms = byGoal[g.id];
                  const isActive = g.id === activeId;
                  const step = nextStep(ms);
                  const dl = fmt(g.deadline);
                  return (
                    <article key={g.id} className={`relative overflow-hidden rounded-3xl border bg-surface-container-lowest p-5 shadow-sm transition-shadow hover:shadow-md md:p-6 ${isActive ? "border-sunburst-gold ring-2 ring-sunburst-gold/40" : "border-outline-variant"}`}>
                      <span className="kente-band absolute inset-x-0 top-0 h-1.5" />
                      <div className="mt-1 flex items-start justify-between gap-3">
                        <div className="flex flex-wrap items-center gap-2">
                          {isActive && <span className="rounded-full bg-gold-mist px-2.5 py-1 font-eyebrow text-[10px] uppercase text-sunburst-gold">★ Active focus</span>}
                          {chips(g, ms).map((c) => <span key={c.label} className={`rounded-full px-2.5 py-1 font-eyebrow text-[10px] uppercase ${c.cls}`}>{c.label}</span>)}
                        </div>
                        <button type="button" onClick={() => setEditing(g)} aria-label={`Edit ${g.title}`} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-surface-container-low text-on-surface-variant hover:text-on-surface"><Icon name="edit" size={18} /></button>
                      </div>
                      <h2 className="mt-3 font-title-md text-[24px] leading-8 text-on-surface">{g.title}</h2>
                      {g.description && <p className="mt-1 line-clamp-2 font-body-md text-[15px] text-on-surface-variant">{g.description}</p>}

                      <div className="mt-4 flex items-center gap-5 rounded-2xl bg-surface-container-low p-4">
                        <ProgressRing progressPct={g.progressPct} size={84} caption="complete" />
                        <div className="min-w-0 flex-1">
                          <p className="font-eyebrow text-[10px] uppercase text-on-surface-variant">Progress</p>
                          <p className="font-title-md text-[18px] text-on-surface">{ms ? `${ms.filter((m) => m.status === "done").length} of ${ms.length} milestones done` : "Loading milestones…"}</p>
                          {dl && <p className="mt-0.5 font-caption text-caption text-on-surface-variant">Target date: {dl}</p>}
                        </div>
                      </div>

                      {step && (
                        <div className="mt-3 flex items-center gap-3 rounded-2xl bg-surface-container-low p-4">
                          <Icon name={step.status === "blocked" ? "report" : "event_available"} className={step.status === "blocked" ? "text-error" : "text-primary"} />
                          <div className="min-w-0"><p className="font-eyebrow text-[10px] uppercase text-on-surface-variant">{step.status === "blocked" ? "Blocked step" : step.status === "upcoming" ? "Next up" : "Immediate milestone step"}</p><p className="truncate font-label-sm text-[15px] text-on-surface">{step.title}</p></div>
                        </div>
                      )}

                      <div className="mt-4 flex items-center justify-between border-t border-outline-variant/50 pt-3">
                        <button type="button" onClick={() => setActiveId(g.id)} className={`font-caption text-caption ${isActive ? "text-sunburst-gold" : "text-on-surface-variant hover:text-primary"}`}>{isActive ? "● Viewed in roadmap" : "Preview in roadmap"}</button>
                        <Link href={`/goals/milestones/${g.id}`} className="flex items-center gap-1 font-label-sm text-label-sm text-primary hover:underline">View roadmap <Icon name="arrow_forward" size={16} /></Link>
                      </div>
                    </article>
                  );
                })}
                <button type="button" onClick={openNew} className="group flex flex-col items-center justify-center gap-2 rounded-3xl border-2 border-dashed border-outline-variant p-8 transition-colors hover:border-primary">
                  <span className="flex h-12 w-12 items-center justify-center rounded-full bg-surface-container-low text-on-surface-variant group-hover:text-primary"><Icon name="add_circle" /></span>
                  <span className="font-title-md text-title-md text-on-surface-variant">Define new purpose</span>
                </button>
              </>
            )}
          </div>

          <div className="relative mt-8 overflow-hidden rounded-3xl border border-outline-variant bg-surface-container-low p-6">
            <p className="flex items-center gap-2 font-title-md text-title-md text-primary"><Icon name="menu_book" size={20} /> Mentor insight · Sankofa</p>
            <p className="mt-2 max-w-2xl font-quote text-[18px] italic leading-7 text-on-surface-variant">“To move forward, look to the wisdom of the past. Your goals today draw from a heritage of resilience and trade excellence.”</p>
          </div>
        </main>

        {active && (
          <aside className="hidden w-[380px] shrink-0 xl:block">
            <div className="sticky top-6 overflow-hidden rounded-3xl border border-outline-variant bg-surface-container-lowest p-6 shadow-sm">
              <div className="flex items-center justify-between"><p className="font-eyebrow text-eyebrow uppercase text-primary">Active roadmap</p>{active.deadline && <span className="rounded-full bg-gold-mist px-2.5 py-1 font-eyebrow text-[10px] uppercase text-sunburst-gold">Target: {fmt(active.deadline)}</span>}</div>
              <h2 className="mt-3 font-title-md text-[26px] leading-8 text-on-surface">{active.title}</h2>
              <div className="mt-4"><div className="flex justify-between font-caption text-caption text-on-surface-variant"><span>Trajectory completion</span><span className="text-primary">{active.progressPct}% completed</span></div><div className="mt-1.5 h-2 rounded-full bg-outline-variant/60"><div className="h-2 rounded-full bg-sunburst-gold" style={{ width: `${active.progressPct}%` }} /></div></div>
              <p className="mb-4 mt-6 font-eyebrow text-eyebrow uppercase text-on-surface-variant">Milestone pathway{activeMs ? ` (${activeMs.length} stages)` : ""}</p>
              {activeMs === undefined ? <div className="h-32 animate-pulse rounded-xl bg-surface-container-low" /> : activeMs.length === 0 ? <p className="font-body-md text-[14px] text-on-surface-variant">No milestones yet for this goal.</p> : <Pathway ms={activeMs} />}
              {nextStep(activeMs) && (
                <div className="mt-6 rounded-2xl border border-sunburst-gold/50 bg-gold-mist p-4">
                  <p className="font-eyebrow text-[10px] uppercase text-sunburst-gold"><Icon name="bolt" size={12} className="mr-1 align-[-2px]" />Mentor action trigger</p>
                  <p className="mt-1 font-label-sm text-[15px] text-on-surface">{nextStep(activeMs)!.title}</p>
                  <Link href="/goals/action" className="mt-3 flex h-11 items-center justify-center gap-2 rounded-full bg-sunburst-gold font-label-sm text-[15px] font-bold text-ink shadow-md">Execute next action <Icon name="arrow_forward" size={18} /></Link>
                </div>
              )}
              <div className="mt-4 grid grid-cols-2 gap-2">
                <Link href={`/goals/milestones/${active.id}`} className="flex items-center justify-center gap-1.5 rounded-xl bg-surface-container-low py-2.5 font-label-sm text-label-sm text-on-surface hover:bg-surface-container"><Icon name="add_circle" size={16} /> Add milestone</Link>
                <button type="button" onClick={() => setEditing(active)} className="flex items-center justify-center gap-1.5 rounded-xl bg-surface-container-low py-2.5 font-label-sm text-label-sm text-on-surface hover:bg-surface-container"><Icon name="tune" size={16} /> Edit parameters</button>
              </div>
            </div>
          </aside>
        )}
      </div>

      {goals !== null && goals.length > 0 && (
        <button type="button" onClick={openNew} aria-label="New goal" className="fixed bottom-24 right-5 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-on-primary shadow-lg active:scale-95 sm:hidden"><Icon name="add" size={26} /></button>
      )}

      <EditGoalModal
        goal={editing}
        isOpen={!!editing}
        onClose={() => setEditing(null)}
        onGoalUpdated={() => load()}
        onGoalDeleted={() => { setActiveId(null); load(); }}
      />
    </AppFrame>
  );
}
