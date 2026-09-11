"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { fetchProgressSummary, recordAction, shareWeeklySummary } from "@/lib/api";
import type { BadgeWithStatus, StreakStat } from "@/lib/types";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAppState } from "@/lib/store";

const HEATMAP_INTENSITIES = ["bg-surface-container", "bg-secondary-fixed", "bg-secondary-container", "bg-secondary"];

function BadgeTile({ badge, wide = false }: { badge: BadgeWithStatus; wide?: boolean }) {
  const earned = badge.earnedAt !== null;
  return (
    <div
      className={`flex flex-col items-center gap-sm rounded border p-md text-center transition-transform active:scale-95 md:hover:border-primary/50 ${
        wide ? "col-span-2 flex-row justify-start text-left md:col-span-1 md:flex-col md:justify-center md:text-center" : ""
      } ${
        earned
          ? "border-primary-fixed bg-primary-fixed/20"
          : "border-outline-variant bg-surface-container-high opacity-70 md:border-dashed"
      }`}
    >
      <div
        className={`relative flex shrink-0 items-center justify-center rounded-full ${wide ? "h-12 w-12 md:h-16 md:w-16" : "h-16 w-16"} ${
          earned ? "bg-primary-fixed text-on-primary-fixed" : "bg-surface-variant text-on-surface-variant"
        }`}
      >
        <Icon name={badge.iconName ?? "workspace_premium"} filled={earned} size={wide ? 24 : 32} />
        {!earned && <Icon name="lock" className="absolute -bottom-1 -right-1" size={14} />}
      </div>
      <div>
        <p className="font-label-sm text-label-sm font-bold text-on-surface">{badge.label}</p>
        <p className="text-[10px] text-on-surface-variant">{badge.description}</p>
      </div>
    </div>
  );
}

export default function ProgressBoardPage() {
  const { profile } = useAppState();
  const [streak, setStreak] = useState<StreakStat | null>(null);
  const [badges, setBadges] = useState<BadgeWithStatus[] | null>(null);
  const [heatmap, setHeatmap] = useState<number[][] | null>(null);
  const [weeklyBars, setWeeklyBars] = useState<number[]>([20, 20, 20, 20, 20, 20, 20]);
  const [recordingAction, setRecordingAction] = useState(false);
  const [awardNotice, setAwardNotice] = useState<string | null>(null);
  const [shareNotice, setShareNotice] = useState<string | null>(null);
  const [isSharing, setIsSharing] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  async function loadData() {
    const summary = await fetchProgressSummary();
    setStreak(summary.streak);
    setBadges(summary.badges);
    if (summary.heatmap && summary.heatmap.length > 0) {
      // Derive the past 7 days of activity heights
      const last7 = summary.heatmap.slice(-7);
      const computedBars = last7.map((d) => (d.count > 0 ? Math.min(100, 30 + d.count * 35) : 15));
      while (computedBars.length < 7) {
        computedBars.unshift(15);
      }
      setWeeklyBars(computedBars);

      const weeks: number[][] = [];
      for (let i = 0; i < summary.heatmap.length; i += 7) {
        const slice = summary.heatmap.slice(i, i + 7);
        const intensities = slice.map((d) => Math.min(3, d.count));
        while (intensities.length < 7) {
          intensities.push(0);
        }
        weeks.push(intensities);
      }
      setHeatmap(weeks);
    } else {
      setHeatmap(Array.from({ length: 13 }, () => Array(7).fill(0)));
      setWeeklyBars([15, 15, 15, 15, 15, 15, 15]);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

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

  async function handleShareWeekly() {
    setIsSharing(true);
    setShareNotice(null);
    try {
      const summary = await shareWeeklySummary();
      const text =
        summary?.shareText ||
        `This week I completed ${streak?.actionsCompletedTotal ?? 0} actions on AfriMentor AI and I'm on a ${streak?.currentStreakDays ?? 1}-day streak! 🔥`;

      if (typeof navigator !== "undefined" && navigator.share) {
        try {
          await navigator.share({
            title: "My AfriMentor Weekly Growth",
            text,
          });
          setShareNotice("Shared successfully! 🎉");
          return;
        } catch {
          // User dismissed or share failed, fallback to copy
        }
      }
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(text);
        setShareNotice("Copied weekly progress summary to clipboard! 🎉");
      }
    } catch (err) {
      console.warn("Share failed:", err);
      setShareNotice("Could not share summary right now.");
    } finally {
      setIsSharing(false);
      setTimeout(() => setShareNotice(null), 5000);
    }
  }

  const earnedCount = badges?.filter((b) => b.earnedAt !== null).length ?? null;
  const lockedCount = badges ? badges.length - (earnedCount ?? 0) : null;
  const nextLockedBadge = badges?.find((b) => b.earnedAt === null);

  const displayedBadges = (badges ?? []).filter((b) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return b.label.toLowerCase().includes(q) || (b.description && b.description.toLowerCase().includes(q));
  });

  return (
    <main
      className="min-h-full bg-surface pb-24 pt-md md:pb-lg md:pt-0"
      style={{ backgroundImage: "radial-gradient(circle, rgba(126,87,0,0.035) 2px, transparent 2px)", backgroundSize: "60px 60px" }}
    >
      <header className="hidden h-16 items-center justify-between border-b border-outline-variant bg-surface px-lg lg:flex">
        <h1 className="font-title-md text-title-md text-primary">Progress Board</h1>
        <div className="flex items-center gap-md">
          <label className="relative w-48 xl:w-64">
            <span className="sr-only">Search achievements</span>
            <Icon name="search" size={18} className="absolute left-sm top-1/2 -translate-y-1/2 text-on-surface-variant" />
            <input
              placeholder="Search badges..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-9 w-full rounded-full border-0 bg-surface-container-low pl-9 pr-md text-xs focus:ring-2 focus:ring-primary"
            />
          </label>
          <Icon name="notifications_none" className="text-on-surface-variant" />
          <Icon name="settings" className="text-on-surface-variant" />
          <button
            type="button"
            onClick={handleShareWeekly}
            disabled={isSharing}
            className="flex items-center gap-xs rounded-full bg-surface-container-high px-md py-sm text-xs text-primary transition-opacity hover:opacity-80 disabled:opacity-50"
          >
            <Icon name="share" size={16} /> {isSharing ? "Sharing..." : "Share"}
          </button>
          <button type="button" onClick={() => window.print()} className="flex items-center gap-xs rounded-full border border-outline-variant px-md py-sm text-xs text-on-surface-variant transition-colors hover:bg-surface-variant">
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

        {awardNotice && <div className="rounded-xl border border-secondary bg-secondary-container p-md text-sm font-medium text-on-secondary-container shadow-sm animate-fadeIn">{awardNotice}</div>}
        {shareNotice && <div className="rounded-xl border border-primary/30 bg-primary-container/30 p-md text-sm font-medium text-primary shadow-sm animate-fadeIn">{shareNotice}</div>}

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
            {weeklyBars.map((h, i) => (
              <div
                key={i}
                className={`w-full rounded-t-sm transition-all duration-500 ${h >= 50 ? "bg-secondary" : "bg-secondary-container"}`}
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
          <div className="hidden items-center gap-sm text-[10px] text-on-surface-variant md:flex"><span>Less</span><div className="flex gap-1">{HEATMAP_INTENSITIES.map((c) => <span key={c} className={`h-3 w-3 rounded-sm ${c}`} />)}</div><span>More</span></div>
        </div>
        <div className="rounded-b-xl border border-t-0 border-outline-variant/20 bg-surface-container-lowest p-md md:p-lg">
          {heatmap === null ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <>
              <p className="sr-only">
                A heatmap of your daily action over the last 3 months, from less active to more active.
              </p>
              <div aria-hidden="true" className="flex gap-1 overflow-x-auto pb-sm md:gap-[3px]">
                <div className="grid grid-rows-7 gap-1 pr-1 text-[8px] text-on-surface-variant md:gap-[3px] md:text-[10px] md:uppercase md:font-bold">
                  <div>M</div>
                  <div />
                  <div>W</div>
                  <div />
                  <div>F</div>
                  <div />
                  <div>S</div>
                </div>
                {heatmap.map((week, wi) => (
                  <div key={wi} className="grid grid-rows-7 gap-1 md:gap-[3px]">
                    {week.map((intensity, di) => (
                      <div key={di} className={`h-2.5 w-2.5 rounded-[2px] md:h-3 md:w-3 ${HEATMAP_INTENSITIES[intensity]}`} />
                    ))}
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="mt-md flex items-center justify-end gap-sm md:hidden">
            <span className="text-[10px] text-on-surface-variant">Less</span>
            <div className="flex gap-xs">
              {HEATMAP_INTENSITIES.map((c) => (
                <div key={c} className={`h-3 w-3 rounded-[2px] ${c}`} />
              ))}
            </div>
            <span className="text-[10px] text-on-surface-variant">More</span>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-md md:p-lg lg:col-span-4">
        <h3 className="mb-lg font-title-md text-title-md text-on-surface">Your Path</h3>
        <div className="space-y-0 px-sm">
          {/* Milestone 1: Profile & Diagnostic */}
          <div className="flex min-h-16 gap-md">
            <div className="flex flex-col items-center">
              <span className="z-10 flex h-6 w-6 items-center justify-center rounded-full border-4 border-primary-fixed bg-primary text-on-primary">
                <Icon name="check" size={12} />
              </span>
              <span className="h-full w-0.5 bg-primary" />
            </div>
            <div className="-mt-1 flex flex-col">
              <span className="font-label-sm font-bold text-primary">Completed</span>
              <span className="text-xs text-on-surface">Intake &amp; Enterprise Baseline</span>
              <span className="text-[10px] text-on-surface-variant">{profile?.sector ?? "Diagnostic setup complete"}</span>
            </div>
          </div>

          {/* Milestone 2: Daily Rhythm */}
          <div className="flex min-h-24 gap-md">
            <div className="flex flex-col items-center">
              <span className={`z-10 h-6 w-6 rounded-full ring-4 ${
                (streak?.currentStreakDays ?? 0) >= 7 ? "bg-secondary ring-secondary/20" : "animate-pulse bg-primary ring-primary-container/20"
              }`} />
              <span className="h-full w-0.5 border-l-2 border-dashed border-outline-variant" />
            </div>
            <div className="mt-[-4px] rounded-lg border border-primary/10 bg-primary-container/10 p-sm">
              <span className="font-label-sm font-bold text-primary">
                {(streak?.currentStreakDays ?? 0) >= 7 ? "Mastered" : "In Progress"}
              </span>
              <span className="block text-xs font-bold text-on-surface">Daily action practice</span>
              <span className="mt-1 block text-[11px] text-on-surface-variant">
                {streak?.currentStreakDays ?? 0} day streak • {streak?.actionsCompletedTotal ?? 0} total actions
              </span>
            </div>
          </div>

          {/* Milestone 3: Next Badge or Target */}
          <div className="flex min-h-16 gap-md">
            <div className="flex flex-col items-center">
              <span className="z-10 h-6 w-6 rounded-full border-2 border-outline-variant bg-surface" />
            </div>
            <div className="-mt-1 opacity-80">
              <span className="font-label-sm font-bold text-on-surface-variant">Next Milestone</span>
              <span className="block text-xs text-on-surface font-semibold">
                {nextLockedBadge ? nextLockedBadge.label : "Master Mentor Badge"}
              </span>
              <span className="block text-[10px] text-on-surface-variant">
                {nextLockedBadge?.description ?? "Keep logging daily actions to unlock more achievements"}
              </span>
            </div>
          </div>
        </div>
      </section>
      </div>

      <section className="rounded-2xl bg-surface-container-low p-md md:p-lg">
        <div className="mb-lg flex items-end justify-between">
          <div>
            <h3 className="font-headline-lg text-headline-lg text-on-surface">Achievement Gallery</h3>
            <p className="text-sm text-on-surface-variant">Celebrating your consistent dedication to growth.</p>
          </div>
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="text-xs font-semibold text-primary hover:underline"
            >
              Clear filter ({displayedBadges.length})
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 gap-md md:grid-cols-3 xl:grid-cols-6">
          {badges === null ? (
            Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-36 w-full rounded-xl" />)
          ) : displayedBadges.length > 0 ? (
            displayedBadges.map((b, i) => <BadgeTile key={b.id} badge={b} wide={i === 2} />)
          ) : (
            <div className="col-span-full rounded-xl border border-dashed border-outline-variant p-lg text-center text-sm text-on-surface-variant">
              No badges match &ldquo;{searchQuery}&rdquo;.
            </div>
          )}
        </div>
      </section>

      <button
        onClick={handleShareWeekly}
        disabled={isSharing}
        className="flex w-full items-center justify-center gap-sm rounded-full bg-primary py-md text-on-primary shadow-md transition-transform active:scale-95 hover:opacity-90 disabled:opacity-50 md:w-auto md:px-xl"
      >
        <Icon name="share" />
        <span className="font-title-md text-title-md">{isSharing ? "Preparing..." : "Share weekly summary"}</span>
      </button>

      <p className="pb-lg text-center font-body-md text-[13px] italic text-on-surface-variant">
        Inspired by the Sankofa bird: Looking back to move forward.
      </p>
      </div>
    </main>
  );
}