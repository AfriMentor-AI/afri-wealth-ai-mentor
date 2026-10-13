"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { AppFrame, KenteStrip } from "@/components/shell/AppSidebar";
import { fetchGoals, fetchMilestonesByGoal, fetchProgressSummary, recordAction } from "@/lib/api";
import type { BadgeWithStatus, Goal, Milestone, StreakStat } from "@/lib/types";
import { useAppDispatch, useAppState } from "@/lib/store";
import { mentorFor } from "@/lib/mentors";

const HEAT = ["bg-surface-container-high", "bg-primary/25", "bg-primary/50", "bg-primary/75", "bg-primary"];


interface HeatmapCell {
  date: string;
  intensity: number;
  count: number;
}

const EXPANDED_BADGE_CATALOG: BadgeWithStatus[] = [
  {
    id: "early_bird",
    label: "Early Bird",
    description: "8 Sessions before 8 AM",
    iconName: "workspace_premium",
    earnedAt: null,
  },
  {
    id: "community_pillar",
    label: "Community Pillar",
    description: "Helped 5 new members",
    iconName: "groups",
    earnedAt: null,
  },
  {
    id: "bookworm",
    label: "Bookworm",
    description: "Read 10 modules in Library",
    iconName: "auto_stories",
    earnedAt: null,
  },
  {
    id: "certified_expert",
    label: "Certified Expert",
    description: "Passed Advanced Exam",
    iconName: "verified",
    earnedAt: null,
  },
  {
    id: "consistency_master",
    label: "Consistency Master",
    description: "30 Day Streak (24/30)",
    iconName: "local_fire_department",
    earnedAt: null,
  },
  {
    id: "legacy_giver",
    label: "Legacy Giver",
    description: "Unlock after 50 sessions",
    iconName: "military_tech",
    earnedAt: null,
  },
  {
    id: "smart_saver",
    label: "Smart Saver",
    description: "Hit a weekly savings goal",
    iconName: "savings",
    earnedAt: null,
  },
  {
    id: "scholar_spirit",
    label: "Scholar Spirit",
    description: "Finished 5 lessons in Library",
    iconName: "school",
    earnedAt: null,
  },
  {
    id: "visionary_founder",
    label: "Visionary Founder",
    description: "Created first business milestone",
    iconName: "emoji_objects",
    earnedAt: null,
  },
  {
    id: "communal_investor",
    label: "Communal Investor",
    description: "Collaborated on a venture goal",
    iconName: "handshake",
    earnedAt: null,
  },
  {
    id: "action_pioneer",
    label: "Action Pioneer",
    description: "Logged 10 daily actions",
    iconName: "bolt",
    earnedAt: null,
  },
  {
    id: "wealth_architect",
    label: "Wealth Architect",
    description: "Completed 100% of a strategic goal",
    iconName: "diamond",
    earnedAt: null,
  },
];


function BadgeRow({ b }: { b: BadgeWithStatus }) {
  const earned = b.earnedAt !== null;
  return (
    <div className={`flex items-center gap-3 rounded-2xl p-3 ${earned ? "bg-surface-container-low" : "opacity-60"}`}>
      <span className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full ${earned ? "border-2 border-dashed border-sunburst-gold bg-gold-mist text-sunburst-gold" : "border border-dashed border-outline-variant text-on-surface-variant"}`}>
        <Icon name={earned ? b.iconName ?? "workspace_premium" : "lock"} filled={earned} size={24} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2"><p className="truncate font-label-sm text-[14px] font-bold text-on-surface">{b.label}</p><span className={`font-eyebrow text-[9px] uppercase ${earned ? "text-primary" : "text-on-surface-variant"}`}>{earned ? "Earned" : "Locked"}</span></div>
        <p className="line-clamp-1 font-caption text-caption text-on-surface-variant">{b.description}</p>
      </div>
    </div>
  );
}

export default function ProgressPage() {
  const dispatch = useAppDispatch();
  const { profile, activeGoalId, selectedPersona } = useAppState();
  const mentor = mentorFor(selectedPersona);
  const [streak, setStreak] = useState<StreakStat | null>(null);
  const [badges, setBadges] = useState<BadgeWithStatus[] | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapCell[][] | null>(null);
  const [pathGoal, setPathGoal] = useState<Goal | null>(null);
  const [milestones, setMilestones] = useState<Milestone[] | null>(null);
  const [recordingAction, setRecordingAction] = useState(false);
  const [awardNotice, setAwardNotice] = useState<string | null>(null);
  const [showBadges, setShowBadges] = useState(false);
  const [badgeFilter, setBadgeFilter] = useState<"all" | "earned" | "locked">("all");
  const [loadError, setLoadError] = useState(false);

  async function loadData() {
    let summary;
    try {
      summary = await fetchProgressSummary();
      setLoadError(false);
    } catch {
      setLoadError(true);
      setStreak((s) => s ?? { userId: "", currentStreakDays: 0, longestStreakDays: 0, actionsCompletedTotal: 0, updatedAt: new Date().toISOString() });
      setBadges((b) => b ?? EXPANDED_BADGE_CATALOG);
      return;
    }
    setStreak(summary.streak);

    // Merge backend badges with rich catalog — strictly user's actual earnedAt dates
    const backendBadges = summary.badges || [];
    const merged = EXPANDED_BADGE_CATALOG.map((def) => {
      const match = backendBadges.find(
        (b) => b.id === def.id || b.label.toLowerCase() === def.label.toLowerCase()
      );
      return {
        ...def,
        earnedAt: match?.earnedAt ?? null,
      };
    });
    setBadges(merged);

    // Build 52-week activity heatmap based strictly on real recorded actions
    const activityMap = new Map<string, number>();
    if (summary.heatmap && summary.heatmap.length > 0) {
      for (const d of summary.heatmap) {
        activityMap.set(d.date, d.count);
      }
    }

    const WEEKS_COUNT = 52;
    const now = new Date();
    const currentDayOfWeek = (now.getDay() + 6) % 7; // Mon=0, Sun=6
    const endOfCurrentWeek = new Date(now);
    endOfCurrentWeek.setDate(now.getDate() + (6 - currentDayOfWeek));

    // Ensure active streak days reflect directly on the heatmap
    if (summary.streak && summary.streak.currentStreakDays > 0) {
      const streakDays = summary.streak.currentStreakDays;
      const todayIso = now.toISOString().split("T")[0];
      const hasToday = (activityMap.get(todayIso) ?? 0) > 0;
      const startOffset = hasToday ? 0 : 1;

      for (let i = 0; i < streakDays; i++) {
        const streakDate = new Date(now);
        streakDate.setDate(now.getDate() - (startOffset + i));
        const iso = streakDate.toISOString().split("T")[0];
        if (!activityMap.has(iso) || (activityMap.get(iso) ?? 0) === 0) {
          activityMap.set(iso, 1);
        }
      }
    }

    const startDate = new Date(endOfCurrentWeek);
    startDate.setDate(startDate.getDate() - (WEEKS_COUNT * 7 - 1));

    const weeks: HeatmapCell[][] = [];
    const cursor = new Date(startDate);

    for (let w = 0; w < WEEKS_COUNT; w++) {
      const week: HeatmapCell[] = [];
      for (let d = 0; d < 7; d++) {
        const iso = cursor.toISOString().split("T")[0];
        const count = activityMap.get(iso) ?? 0;
        const intensity = count > 0 ? Math.min(4, count) : 0;

        week.push({ date: iso, intensity, count });
        cursor.setDate(cursor.getDate() + 1);
      }
      weeks.push(week);
    }
    setHeatmap(weeks);

    try {
      const fetchedGoals = await fetchGoals();
      if (fetchedGoals && fetchedGoals.length > 0) {
        const targetGoal =
          (activeGoalId ? fetchedGoals.find((g) => g.id === activeGoalId) : null) ??
          fetchedGoals.find((g) => g.progressPct < 100) ??
          fetchedGoals[0];
        setPathGoal(targetGoal);
        const ms = await fetchMilestonesByGoal(targetGoal.id);
        setMilestones([...ms].sort((a, b) => a.order - b.order));
      } else {
        setPathGoal(null);
        setMilestones([]);
      }
    } catch (err) {
      console.warn("Failed to load path milestones:", err);
      setPathGoal(null);
      setMilestones([]);
    }
  }

  useEffect(() => {
    loadData();
    const handleGoalCreated = () => {
      loadData();
    };
    window.addEventListener("goal-created", handleGoalCreated);
    return () => {
      window.removeEventListener("goal-created", handleGoalCreated);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeGoalId]);
  async function handleRecordAction() {
    setRecordingAction(true);
    setAwardNotice(null);
    try {
      const res = await recordAction("daily_action");
      setStreak(res.streak);
      await loadData();
      if (res.newlyEarnedBadges && res.newlyEarnedBadges.length > 0) {
        setAwardNotice(`🎉 Congratulations! You earned: ${res.newlyEarnedBadges[0].label}!`);
      } else {
        setAwardNotice("✨ Action recorded! Your streak has been updated.");
      }
    } catch (err) {
      console.error("Failed to record action:", err);
    } finally {
      setRecordingAction(false);
    }
  }


  const earnedCount = badges?.filter((b) => b.earnedAt !== null).length ?? 0;
  const first = profile?.name?.split(" ")[0] ?? "Entrepreneur";
  const doneMs = milestones?.filter((m) => m.status === "done").length ?? 0;
  const shownBadges = (badges ?? []).filter((b) => (badgeFilter === "earned" ? b.earnedAt !== null : badgeFilter === "locked" ? b.earnedAt === null : true));
  const preview = [...(badges ?? [])].sort((a, b) => Number(b.earnedAt !== null) - Number(a.earnedAt !== null)).slice(0, 5);

  const logBtn = (
    <button type="button" onClick={handleRecordAction} disabled={recordingAction} className="flex h-12 items-center justify-center gap-2 rounded-full bg-primary px-6 font-label-sm text-[15px] font-bold text-on-primary shadow-md transition-all hover:opacity-90 active:scale-[0.98] disabled:opacity-50">
      <Icon name="check_circle" size={20} /> {recordingAction ? "Recording..." : "Log today’s action"}
    </button>
  );

  const stats = [
    { label: "Current streak", value: streak ? `${streak.currentStreakDays}` : "—", unit: "days", icon: "local_fire_department", note: "Daily check-ins" },
    { label: "Longest streak", value: streak ? `${streak.longestStreakDays}` : "—", unit: "days", icon: "military_tech", note: "Your personal best" },
    { label: "Actions completed", value: streak ? `${streak.actionsCompletedTotal}` : "—", unit: "total", icon: "task_alt", note: "Across all your sessions" },
    { label: "Badges earned", value: badges ? `${earnedCount}` : "—", unit: `of ${badges?.length ?? 0}`, icon: "workspace_premium", note: "Guild medallions" },
  ];

  return (
    <AppFrame title="Progress">
      <KenteStrip />
      <div className="mx-auto max-w-6xl px-5 pb-16 pt-6 md:px-10 md:pt-10">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="font-eyebrow text-eyebrow uppercase text-on-surface-variant"><span className="text-sunburst-gold">●</span> Sovereign trajectory</p>
            <h1 className="mt-2 font-headline-xl-mobile text-headline-xl-mobile text-on-surface md:font-headline-xl md:text-[52px] md:leading-[58px]">Your growth</h1>
            <p className="mt-2 max-w-xl font-body-lg text-body-lg text-on-surface-variant">Consistent action builds lasting wealth, {first}.</p>
          </div>
          {logBtn}
        </header>

        {awardNotice && <div role="status" className="mt-6 rounded-2xl border border-sunburst-gold/60 bg-gold-mist px-5 py-3 font-label-sm text-label-sm text-on-surface">{awardNotice}</div>}
        {loadError && <p role="alert" className="mt-6 rounded-xl bg-error-container px-4 py-3 font-label-sm text-label-sm text-on-error-container">Couldn’t load your progress. <button className="underline" onClick={() => loadData()}>Try again</button></p>}

        <div className="mt-8 grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
          {stats.map((s) => (
            <div key={s.label} className="rounded-3xl border border-outline-variant bg-surface-container-lowest p-5 shadow-sm">
              <div className="flex items-start justify-between gap-2"><p className="font-eyebrow text-[10px] uppercase text-on-surface-variant">{s.label}</p><span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-gold-mist text-sunburst-gold"><Icon name={s.icon} size={20} /></span></div>
              <p className="mt-4 font-title-md text-[40px] leading-[44px] text-on-surface">{s.value} <span className="font-label-sm text-label-sm font-normal text-on-surface-variant">{s.unit}</span></p>
              <p className="mt-1 font-caption text-caption text-on-surface-variant">{s.note}</p>
            </div>
          ))}
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_380px]">
          <div className="flex min-w-0 flex-col gap-6">
            <section className="rounded-3xl border border-outline-variant bg-surface-container-lowest p-6 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0"><h2 className="font-title-md text-[24px] leading-8 text-on-surface">Milestone trajectory</h2>{pathGoal && <p className="truncate font-caption text-caption text-on-surface-variant" title={pathGoal.title}>{pathGoal.title}</p>}</div>
                {pathGoal && <Link href={`/goals/milestones/${pathGoal.id}`} className="flex shrink-0 items-center gap-1 font-label-sm text-label-sm text-primary hover:underline">Open roadmap <Icon name="arrow_forward" size={16} /></Link>}
              </div>
              {pathGoal && <div className="mt-4"><div className="flex justify-between font-caption text-caption text-on-surface-variant"><span>{milestones ? `${doneMs} of ${milestones.length} milestones done` : "Loading…"}</span><span className="text-primary">{pathGoal.progressPct}% achieved</span></div><div className="mt-1.5 h-2.5 rounded-full bg-outline-variant/60"><div className="h-2.5 rounded-full bg-sunburst-gold" style={{ width: `${pathGoal.progressPct}%` }} /></div></div>}
              {milestones === null ? (
                <div className="mt-5 h-24 animate-pulse rounded-2xl bg-surface-container-low" />
              ) : milestones.length === 0 ? (
                <div className="mt-5 rounded-2xl border border-dashed border-outline-variant p-6 text-center">
                  <p className="font-label-sm text-[15px] font-bold text-on-surface">{pathGoal ? "No milestones added yet" : "No active goal roadmap"}</p>
                  <p className="mt-1 font-body-md text-[14px] text-on-surface-variant">{pathGoal ? "Define milestones for this goal to visualize your pathway." : "Set a goal to visualize your milestones path."}</p>
                  <Link href={pathGoal ? `/goals/milestones/${pathGoal.id}` : "/goals"} className="mt-3 inline-flex items-center gap-1 rounded-full bg-primary px-4 py-2 font-label-sm text-label-sm text-on-primary"><Icon name="add" size={16} /> {pathGoal ? "Add milestones" : "Create a goal"}</Link>
                </div>
              ) : (
                <ol className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                  {milestones.map((m, i) => (
                    <li key={m.id} className={`rounded-2xl p-4 ${m.status === "in_progress" ? "bg-gold-mist ring-1 ring-sunburst-gold/50" : m.status === "blocked" ? "bg-error-container/40" : "bg-surface-container-low"}`}>
                      <div className="flex items-center gap-2"><Icon name={m.status === "done" ? "check_circle" : m.status === "blocked" ? "report" : m.status === "in_progress" ? "flag" : "radio_button_unchecked"} filled={m.status === "done"} size={20} className={m.status === "done" ? "text-primary" : m.status === "blocked" ? "text-error" : m.status === "in_progress" ? "text-sunburst-gold" : "text-on-surface-variant"} /><span className="font-eyebrow text-[10px] uppercase text-on-surface-variant">M{i + 1} · {m.status.replace("_", " ")}</span></div>
                      <p className="mt-2 font-label-sm text-[15px] text-on-surface">{m.title}</p>
                    </li>
                  ))}
                </ol>
              )}
            </section>

            <section className="rounded-3xl border border-outline-variant bg-surface-container-lowest p-6 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div><h2 className="font-title-md text-[24px] leading-8 text-on-surface">Activity heatmap</h2><p className="font-caption text-caption text-on-surface-variant">52 weeks of your daily actions</p></div>
                <div className="flex items-center gap-1 font-caption text-[11px] text-on-surface-variant">Less {HEAT.map((c) => <span key={c} className={`h-3 w-3 rounded-sm ${c}`} />)} More</div>
              </div>
              {heatmap === null ? (
                <div className="mt-5 h-32 animate-pulse rounded-2xl bg-surface-container-low" />
              ) : (
                <div className="mt-5 overflow-x-auto rounded-2xl bg-surface-container-low p-4">
                  <div className="flex w-max gap-1" role="img" aria-label="Activity heatmap for the past 52 weeks">
                    {heatmap.map((week, wi) => (
                      <div key={wi} className="flex flex-col gap-1">
                        {week.map((c) => <span key={c.date} title={`${c.date}: ${c.count} action${c.count === 1 ? "" : "s"}`} className={`h-3.5 w-3.5 rounded-sm ${HEAT[c.intensity]}`} />)}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>

            <section className="rounded-3xl border-l-4 border-sunburst-gold bg-surface-container-low p-6">
              <p className="font-label-sm text-label-sm text-primary">{mentor.name} <span className="font-normal text-on-surface-variant">· {mentor.role}</span></p>
              <p className="mt-2 font-quote text-[20px] italic leading-8 text-on-surface">“{streak && streak.currentStreakDays > 0 ? `${streak.currentStreakDays} unbroken day${streak.currentStreakDays === 1 ? "" : "s"} hold more weight than a one-time wind of chance.` : "The river fills droplet by droplet. Log one small action today and begin your streak."}”</p>
            </section>
          </div>

          <aside className="flex min-w-0 flex-col gap-6">
            <section className="rounded-3xl border border-outline-variant bg-surface-container-lowest p-6 shadow-sm">
              <div className="flex items-start justify-between gap-3"><div><h2 className="font-title-md text-[24px] leading-8 text-on-surface">Achievement badges</h2><p className="font-caption text-caption text-on-surface-variant">Medallions earned through disciplined trials</p></div><span className="rounded-full bg-primary/10 px-3 py-1 font-eyebrow text-[10px] uppercase text-primary">{earnedCount} / {badges?.length ?? 0}</span></div>
              <div className="mt-4 flex flex-col gap-2">{badges === null ? <div className="h-40 animate-pulse rounded-2xl bg-surface-container-low" /> : preview.map((b) => <BadgeRow key={b.id} b={b} />)}</div>
              <button type="button" onClick={() => setShowBadges(true)} className="mt-4 w-full rounded-full border border-outline-variant py-2.5 font-label-sm text-label-sm text-on-surface hover:bg-surface-container-low">View all badges</button>
            </section>

            <section className="relative overflow-hidden rounded-3xl border border-outline-variant bg-surface-container-lowest p-6 shadow-sm">
              <span className="kente-band absolute inset-x-0 top-0 h-1.5" />
              <p className="mt-1 font-eyebrow text-[10px] uppercase text-on-surface-variant">Accountability protocol</p>
              <h2 className="font-title-md text-[24px] leading-8 text-on-surface">Share weekly summary</h2>
              <p className="mt-2 font-body-md text-[14px] leading-5 text-on-surface-variant">Print or save your progress for partners, co-founders or your own records.</p>
              <div className="mt-4 grid grid-cols-2 gap-2">
                <button type="button" onClick={() => window.print()} className="flex items-center justify-center gap-1.5 rounded-full bg-primary py-2.5 font-label-sm text-label-sm text-on-primary"><Icon name="download" size={16} /> Export</button>
                <button type="button" onClick={() => dispatch({ type: "OPEN_FEEDBACK_MODAL" })} className="flex items-center justify-center gap-1.5 rounded-full bg-surface-container-low py-2.5 font-label-sm text-label-sm text-on-surface"><Icon name="rate_review" size={16} /> Give feedback</button>
              </div>
            </section>
          </aside>
        </div>
      </div>

      {showBadges && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 backdrop-blur-sm sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-label="All badges" onMouseDown={(e) => e.target === e.currentTarget && setShowBadges(false)}>
          <div className="flex max-h-[88vh] w-full max-w-2xl flex-col rounded-t-3xl border border-outline-variant bg-surface-container-lowest shadow-2xl sm:rounded-3xl">
            <div className="flex items-start justify-between gap-3 border-b border-outline-variant/50 p-6">
              <div><h2 className="font-title-md text-[24px] leading-8 text-on-surface">All badges</h2><p className="font-caption text-caption text-on-surface-variant">{earnedCount} of {badges?.length ?? 0} unlocked. Consistent actions unlock new milestones.</p></div>
              <button type="button" aria-label="Close" onClick={() => setShowBadges(false)} className="flex h-9 w-9 items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container-low"><Icon name="close" /></button>
            </div>
            <div className="flex gap-2 px-6 pt-4">{(["all", "earned", "locked"] as const).map((t) => <button key={t} type="button" onClick={() => setBadgeFilter(t)} className={`rounded-full px-4 py-1.5 font-label-sm text-label-sm capitalize ${badgeFilter === t ? "bg-primary text-on-primary" : "bg-surface-container-low text-on-surface"}`}>{t}</button>)}</div>
            <div className="grid flex-1 gap-2 overflow-y-auto p-6 sm:grid-cols-2">{shownBadges.map((b) => <BadgeRow key={b.id} b={b} />)}</div>
          </div>
        </div>
      )}
    </AppFrame>
  );
}
