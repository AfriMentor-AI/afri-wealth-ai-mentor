"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { fetchGoals, fetchMilestonesByGoal, fetchProgressSummary, recordAction } from "@/lib/api";
import type { BadgeWithStatus, Goal, Milestone, StreakStat } from "@/lib/types";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAppDispatch, useAppState } from "@/lib/store";
import { NotificationPopover } from "@/components/NotificationPopover";

const WEEKDAY_BARS = [40, 60, 55, 85, 100, 95, 98]; // % height, matches reference chart shape
const HEATMAP_INTENSITIES = [
  "bg-surface-container",
  "bg-primary-container/30",
  "bg-primary-container/60",
  "bg-primary-container",
  "bg-primary",
];

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

interface HeatmapCell {
  date: string;
  intensity: number;
  count: number;
}

export const EXPANDED_BADGE_CATALOG: BadgeWithStatus[] = [
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

function BadgeTile({ badge }: { badge: BadgeWithStatus }) {
  const earned = badge.earnedAt !== null;
  return (
    <div
      className={`group flex flex-col items-center gap-sm rounded-xl p-md text-center transition-all ${
        earned
          ? "border border-outline-variant/30 bg-surface hover:border-primary/50 hover:shadow-md"
          : "border border-dashed border-outline-variant bg-surface/50 opacity-60 grayscale hover:opacity-80"
      }`}
    >
      <div
        className={`mb-xs flex h-16 w-16 shrink-0 items-center justify-center rounded-full transition-transform group-hover:scale-105 ${
          earned
            ? "bg-primary-container/20 text-primary"
            : "bg-surface-container text-on-surface-variant"
        }`}
      >
        <Icon
          name={earned ? badge.iconName ?? "workspace_premium" : "lock"}
          filled={earned}
          size={32}
        />
      </div>
      <div className="flex flex-col gap-0.5">
        <span className="font-label-sm font-bold text-on-surface transition-colors group-hover:text-primary">
          {badge.label}
        </span>
        <span className="text-[11px] text-on-surface-variant line-clamp-2">
          {badge.description}
        </span>
      </div>
      {earned && (
        <span className="mt-auto text-[9px] font-semibold text-primary uppercase tracking-wider">
          Earned
        </span>
      )}
    </div>
  );
}

export default function ProgressBoardPage() {
  const dispatch = useAppDispatch();
  const { profile, activeGoalId } = useAppState();
  const [streak, setStreak] = useState<StreakStat | null>(null);
  const [badges, setBadges] = useState<BadgeWithStatus[] | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapCell[][] | null>(null);
  const [pathGoal, setPathGoal] = useState<Goal | null>(null);
  const [milestones, setMilestones] = useState<Milestone[] | null>(null);
  const [recordingAction, setRecordingAction] = useState(false);
  const [awardNotice, setAwardNotice] = useState<string | null>(null);
  const [showBadgesModal, setShowBadgesModal] = useState(false);
  const [badgeFilter, setBadgeFilter] = useState<"all" | "earned" | "locked">("all");

  async function loadData() {
    const summary = await fetchProgressSummary();
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

  const earnedCount = badges?.filter((b) => b.earnedAt !== null).length ?? null;
  const lockedCount = badges ? badges.length - (earnedCount ?? 0) : null;

  return (
    <main
      className="min-h-full bg-surface pb-24 pt-md md:pb-lg md:pt-0"
      style={{ backgroundImage: "radial-gradient(circle, rgba(126,87,0,0.035) 2px, transparent 2px)", backgroundSize: "60px 60px" }}
    >
      <header className="hidden h-16 items-center justify-between border-b border-outline-variant bg-surface px-lg lg:flex">
        <h1 className="font-title-md text-title-md text-primary">Progress Board</h1>
        <div className="flex items-center gap-md">
          <label className="relative w-48 xl:w-64">
            <span className="sr-only">Search analytics</span>
            <Icon name="search" size={18} className="absolute left-sm top-1/2 -translate-y-1/2 text-on-surface-variant" />
            <input placeholder="Search analytics..." className="h-9 w-full rounded-full border-0 bg-surface-container-low pl-9 pr-md text-xs focus:ring-2 focus:ring-primary" />
          </label>
          <NotificationPopover />
          <button type="button" onClick={handleRecordAction} disabled={recordingAction} className="flex items-center gap-xs rounded-full bg-secondary px-md py-sm text-xs font-semibold text-on-secondary shadow transition-opacity hover:opacity-90 disabled:opacity-50">
            <Icon name="check_circle" size={16} /> {recordingAction ? "Recording..." : "Log Today's Action"}
          </button>
          <button type="button" onClick={() => dispatch({ type: "OPEN_FEEDBACK_MODAL" })} className="flex items-center gap-xs rounded-full bg-surface-container-high px-md py-sm text-xs text-primary">
            <Icon name="share" size={16} /> Share
          </button>
          <button type="button" onClick={() => window.print()} className="flex items-center gap-xs rounded-full border border-outline-variant px-md py-sm text-xs text-on-surface-variant">
            <Icon name="ios_share" size={16} /> Export
          </button>
        </div>
      </header>

      <div className="mx-auto flex max-w-6xl flex-col gap-lg px-margin-mobile py-md md:gap-lg md:p-lg xl:p-xl">
        <section className="flex flex-col gap-sm md:flex-row md:items-end md:justify-between lg:hidden">
          <div>
            <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface">Your Growth</h2>
            <p className="font-body-md text-on-surface-variant">Consistent action builds lasting wealth, {profile?.name ?? "Entrepreneur"}.</p>
          </div>
          <button type="button" onClick={handleRecordAction} disabled={recordingAction} className="tap-target inline-flex items-center justify-center gap-xs rounded-full bg-secondary px-lg py-sm font-label-sm text-label-sm font-semibold text-on-secondary shadow disabled:opacity-50">
            <Icon name="check_circle" size={18} /> {recordingAction ? "Recording..." : "Log Today's Action"}
          </button>
        </section>

        {awardNotice && <div className="rounded-xl border border-secondary bg-secondary-container p-md text-sm font-medium text-on-secondary-container shadow-sm">{awardNotice}</div>}

        <section className="grid gap-md md:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-sm rounded-xl border border-primary/10 bg-primary-container/20 p-lg">
            <span className="font-label-sm text-[11px] uppercase tracking-widest text-on-surface-variant">Longest Streak</span>
            <span className="font-headline-xl text-headline-xl text-primary">{streak?.longestStreakDays ?? "—"} <span className="font-title-md text-title-md">days</span></span>
            <span className="flex items-center gap-xs text-xs font-bold text-secondary"><Icon name="trending_up" size={16} /> Personal best</span>
          </div>
          <div className="flex flex-col gap-sm rounded-xl bg-secondary-container p-lg">
            <span className="font-label-sm text-[11px] uppercase tracking-widest text-on-secondary-container">Active Streak</span>
            <div className="flex items-baseline gap-sm"><span className="font-headline-xl text-headline-xl text-on-secondary-container">{streak?.currentStreakDays ?? "—"}</span><span className="font-title-md text-title-md text-on-secondary-container/80">Days</span></div>
            <div className="h-2 overflow-hidden rounded-full bg-surface/30"><div className="h-full bg-secondary" style={{ width: `${Math.min(100, ((streak?.currentStreakDays ?? 0) / 30) * 100)}%` }} /></div>
          </div>
          <div className="flex flex-col gap-sm rounded-xl border border-outline-variant/30 bg-surface-container-high p-lg">
            <span className="font-label-sm text-[11px] uppercase tracking-widest text-on-surface-variant">Badges Earned</span>
            <span className="font-headline-xl text-headline-xl text-on-surface">{earnedCount ?? "—"}</span>
            <span className="font-label-sm text-[11px] text-on-surface-variant">{lockedCount ?? "—"} available to unlock</span>
          </div>
          <div className="flex flex-col gap-sm rounded-xl border border-outline-variant/30 bg-surface-container-high p-lg">
            <span className="font-label-sm text-[11px] uppercase tracking-widest text-on-surface-variant">Actions Completed</span>
            <span className="font-headline-xl text-headline-xl text-on-surface">{streak?.actionsCompletedTotal ?? "—"}</span>
            <span className="font-label-sm text-[11px] text-on-surface-variant">Keep building your rhythm</span>
          </div>
        </section>

      {streak === null ? (
        <Skeleton className="h-40 w-full rounded md:hidden" />
      ) : (
        <div className="rounded border border-outline-variant bg-surface-container-low p-md shadow-sm md:hidden">
          <div className="mb-md flex items-end justify-between">
            <div>
              <p className="font-label-sm text-label-sm uppercase text-secondary">Current Streak</p>
              <p className="font-headline-xl text-headline-xl text-primary">{streak.currentStreakDays} Days</p>
            </div>
            <p className="font-label-sm text-label-sm text-on-surface-variant">Top Streak: {streak.longestStreakDays}</p>
          </div>
          <div className="flex h-24 items-end justify-between gap-xs px-xs">
            {WEEKDAY_BARS.map((h, i) => (
              <div
                key={i}
                className={`w-full rounded-t-sm ${h >= 85 ? "bg-secondary" : "bg-secondary-container"}`}
                style={{ height: `${h}%` }}
              />
            ))}
          </div>
          <div className="mt-sm flex justify-between font-label-sm text-[10px] text-on-surface-variant">
            {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
              <span key={d}>{d}</span>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-lg lg:grid-cols-12">
      <section className="space-y-md lg:col-span-8">
        <div className="flex items-center justify-between rounded-t-xl bg-surface-container-lowest px-md pt-md md:px-lg md:pt-lg">
          <h3 className="font-title-md text-title-md text-on-surface">Activity Heatmap</h3>
          <div className="flex items-center gap-sm text-[10px] text-on-surface-variant">
            <span>Less</span>
            <div className="flex gap-[2px]">
              {HEATMAP_INTENSITIES.map((c, i) => (
                <span key={i} className={`h-3 w-3 rounded-sm ${c}`} />
              ))}
            </div>
            <span>More</span>
          </div>
        </div>
        <div className="rounded-b-xl border border-t-0 border-outline-variant/20 bg-surface-container-lowest p-md md:p-lg">
          {heatmap === null ? (
            <Skeleton className="h-28 w-full" />
          ) : (
            <div className="flex flex-col gap-1">
              <p className="sr-only">
                A 52-week heatmap of your daily actions over the year, from less active to more active.
              </p>
              {/* Days labels and heatmap grid */}
              <div className="flex">
                <div className="w-8 flex flex-col justify-between py-1 text-[10px] text-on-surface-variant uppercase font-bold shrink-0">
                  <span>Mon</span>
                  <span>Wed</span>
                  <span>Fri</span>
                </div>
                <div className="flex-grow overflow-x-auto pb-xs">
                  <div className="grid grid-flow-col grid-rows-7 gap-1 min-w-max">
                    {heatmap.map((week, wi) =>
                      week.map((cell, di) => (
                        <div
                          key={`${wi}-${di}`}
                          title={`${cell.count} action${cell.count === 1 ? "" : "s"} on ${cell.date}`}
                          className={`h-3 w-3 rounded-sm transition-transform hover:scale-125 hover:z-10 cursor-pointer ${HEATMAP_INTENSITIES[cell.intensity]}`}
                        />
                      ))
                    )}
                  </div>
                </div>
              </div>
              {/* 12 Months row matching screen.png */}
              <div className="flex pl-8 mt-2 justify-between text-[10px] text-on-surface-variant uppercase font-bold">
                {MONTH_NAMES.map((m) => (
                  <span key={m}>{m}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="flex flex-col justify-between rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-md md:p-lg lg:col-span-4">
        <div>
          <div className="mb-lg flex items-center justify-between">
            <div>
              <h3 className="font-title-md text-title-md text-on-surface">Your Path</h3>
              {pathGoal && (
                <p className="line-clamp-1 text-xs text-on-surface-variant" title={pathGoal.title}>
                  {pathGoal.title}
                </p>
              )}
            </div>
            {pathGoal && (
              <Link
                href={`/goals/milestones/${pathGoal.id}`}
                className="flex shrink-0 items-center gap-0.5 text-xs font-semibold text-primary hover:underline"
              >
                <span>View Road</span>
                <Icon name="chevron_right" size={14} />
              </Link>
            )}
          </div>

          {milestones === null ? (
            <div className="space-y-sm">
              <Skeleton className="h-12 w-full rounded" />
              <Skeleton className="h-16 w-full rounded" />
              <Skeleton className="h-12 w-full rounded" />
            </div>
          ) : milestones.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-lg text-center">
              <div className="mb-sm flex h-10 w-10 items-center justify-center rounded-full bg-surface-container text-on-surface-variant">
                <Icon name="flag" size={20} />
              </div>
              <p className="font-label-sm text-xs font-semibold text-on-surface">
                {pathGoal ? "No milestones added yet" : "No active goal roadmap"}
              </p>
              <p className="mt-1 text-[11px] text-on-surface-variant">
                {pathGoal
                  ? "Define milestones for this goal to visualize your pathway."
                  : "Set a goal to visualize your milestones path."}
              </p>
              <Link
                href={pathGoal ? `/goals/milestones/${pathGoal.id}` : "/goals"}
                className="mt-md inline-flex items-center gap-xs rounded-full bg-primary-container px-md py-xs text-xs font-semibold text-on-primary-container hover:opacity-90"
              >
                <Icon name="add" size={14} /> {pathGoal ? "Add Milestones" : "Create a Goal"}
              </Link>
            </div>
          ) : (
            <div className="space-y-0 px-sm">
              {milestones.map((m, idx) => {
                const isLast = idx === milestones.length - 1;
                const isDone = m.status === "done";
                const isInProgress = m.status === "in_progress";
                const isBlocked = m.status === "blocked";

                return (
                  <div
                    key={m.id}
                    className={`flex ${isInProgress ? "min-h-24" : "min-h-16"} gap-md`}
                  >
                    <div className="flex flex-col items-center">
                      {isDone ? (
                        <span className="z-10 flex h-6 w-6 items-center justify-center rounded-full border-4 border-primary-fixed bg-primary text-on-primary">
                          <Icon name="check" size={12} />
                        </span>
                      ) : isInProgress ? (
                        <span className="z-10 h-6 w-6 animate-pulse rounded-full bg-primary ring-4 ring-primary-container/20" />
                      ) : isBlocked ? (
                        <span className="z-10 flex h-6 w-6 items-center justify-center rounded-full border-2 border-error bg-error-container text-on-error-container">
                          <Icon name="priority_high" size={12} />
                        </span>
                      ) : (
                        <span className="z-10 h-6 w-6 rounded-full border-2 border-outline-variant bg-surface" />
                      )}
                      {!isLast && (
                        <span
                          className={`h-full w-0.5 ${
                            isDone
                              ? "bg-primary"
                              : "border-l-2 border-dashed border-outline-variant"
                          }`}
                        />
                      )}
                    </div>

                    {isInProgress ? (
                      <div className="-mt-1 flex-1 rounded-lg border border-primary/10 bg-primary-container/10 p-sm">
                        <span className="font-label-sm font-bold text-primary">In Progress</span>
                        <span className="block text-xs font-bold text-on-surface">{m.title}</span>
                        {streak?.currentStreakDays ? (
                          <span className="mt-1 block text-[11px] text-on-surface-variant">
                            {streak.currentStreakDays} day streak
                          </span>
                        ) : null}
                      </div>
                    ) : (
                      <div className={`-mt-1 flex flex-col ${m.status === "upcoming" ? "opacity-60" : ""}`}>
                        <span
                          className={`font-label-sm font-bold ${
                            isDone
                              ? "text-primary"
                              : isBlocked
                              ? "text-error"
                              : "text-on-surface-variant"
                          }`}
                        >
                          {isDone ? "Completed" : isBlocked ? "Blocked" : "Upcoming"}
                        </span>
                        <span className="text-xs text-on-surface">{m.title}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>
      </div>

      {/* Achievement Badges Grid */}
      <section className="rounded-2xl bg-surface-container-low p-md md:p-lg">
        <div className="mb-lg flex items-end justify-between gap-md">
          <div>
            <h3 className="font-headline-lg text-headline-lg text-on-surface">Achievement Gallery</h3>
            <p className="text-sm text-on-surface-variant">Celebrating your consistent dedication to growth.</p>
          </div>
          <button
            type="button"
            onClick={() => setShowBadgesModal(true)}
            className="flex shrink-0 items-center gap-xs text-xs font-semibold text-primary hover:underline transition-all"
          >
            <span>View All Badges ({badges?.length ?? 12})</span>
            <Icon name="arrow_forward" size={16} />
          </button>
        </div>

        <div className="grid grid-cols-2 gap-md md:grid-cols-3 xl:grid-cols-6">
          {badges === null
            ? Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-44 w-full rounded-xl" />
              ))
            : badges.slice(0, 6).map((b) => (
                <BadgeTile
                  key={b.id}
                  badge={b}
                  onClick={() => setShowBadgesModal(true)}
                />
              ))}
        </div>
      </section>

      {/* View All Badges Modal */}
      {showBadgesModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-md backdrop-blur-sm animate-fade-in"
          onClick={() => setShowBadgesModal(false)}
        >
          <div
            className="relative flex max-h-[85vh] w-full max-w-4xl flex-col rounded-2xl border border-outline-variant bg-surface p-lg shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-outline-variant pb-md">
              <div>
                <h2 className="font-headline-lg text-headline-lg text-on-surface">Achievement Badges</h2>
                <p className="mt-1 text-xs text-on-surface-variant">
                  {earnedCount} of {badges?.length ?? 0} unlocked • Consistent actions unlock new African wealth milestones.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowBadgesModal(false)}
                className="rounded-full p-1 text-on-surface-variant hover:bg-surface-variant hover:text-on-surface transition-colors"
                aria-label="Close modal"
              >
                <Icon name="close" size={20} />
              </button>
            </div>

            {/* Filter Tabs */}
            <div className="flex gap-xs border-b border-outline-variant/40 py-sm">
              {(["all", "earned", "locked"] as const).map((tab) => {
                const count =
                  tab === "all"
                    ? badges?.length ?? 0
                    : tab === "earned"
                    ? earnedCount ?? 0
                    : lockedCount ?? 0;
                return (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setBadgeFilter(tab)}
                    className={`rounded-full px-md py-xs text-xs font-semibold capitalize transition-all ${
                      badgeFilter === tab
                        ? "bg-primary text-on-primary shadow-sm"
                        : "bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
                    }`}
                  >
                    {tab} ({count})
                  </button>
                );
              })}
            </div>

            {/* Badges List */}
            <div className="flex-grow overflow-y-auto py-md custom-scrollbar">
              <div className="grid grid-cols-2 gap-md sm:grid-cols-3 md:grid-cols-4">
                {(badges ?? [])
                  .filter((b) => {
                    if (badgeFilter === "earned") return b.earnedAt !== null;
                    if (badgeFilter === "locked") return b.earnedAt === null;
                    return true;
                  })
                  .map((badge) => (
                    <BadgeTile key={badge.id} badge={badge} />
                  ))}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end border-t border-outline-variant pt-md">
              <button
                type="button"
                onClick={() => setShowBadgesModal(false)}
                className="rounded-full bg-surface-container-high px-lg py-xs text-xs font-semibold text-on-surface hover:bg-surface-variant transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      <button
        onClick={() => dispatch({ type: "OPEN_FEEDBACK_MODAL" })}
        className="flex w-full items-center justify-center gap-sm rounded-full bg-primary py-md text-on-primary shadow-md transition-transform active:scale-95 hover:opacity-90 md:w-auto md:px-xl"
      >
        <Icon name="share" />
        <span className="font-title-md text-title-md">Share weekly summary</span>
      </button>

      <p className="pb-lg text-center font-body-md text-[13px] italic text-on-surface-variant">
        Inspired by the Sankofa bird: Looking back to move forward.
      </p>
      </div>
    </main>
  );
}