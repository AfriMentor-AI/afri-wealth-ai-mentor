"use client";

import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/Icon";
import { fetchProgressSummary, shareWeeklySummary } from "@/lib/api";
import type { BadgeWithStatus, HeatmapDay, StreakStat } from "@/lib/types";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAppDispatch } from "@/lib/store";

const HEATMAP_INTENSITIES = ["bg-surface-container", "bg-secondary-fixed", "bg-secondary-container", "bg-secondary"];

function intensityFor(count: number): number {
  if (count <= 0) return 0;
  if (count === 1) return 1;
  if (count === 2) return 2;
  return 3;
}

function weekdayLabel(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00`).toLocaleDateString(undefined, { weekday: "short" });
}

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

type ShareStatus = "idle" | "loading" | "shared" | "copied" | "error";

export default function ProgressBoardPage() {
  const dispatch = useAppDispatch();
  const [streak, setStreak] = useState<StreakStat | null>(null);
  const [badges, setBadges] = useState<BadgeWithStatus[] | null>(null);
  const [heatmapDays, setHeatmapDays] = useState<HeatmapDay[] | null>(null);
  const [shareStatus, setShareStatus] = useState<ShareStatus>("idle");

  useEffect(() => {
    fetchProgressSummary().then((summary) => {
      setStreak(summary.streak);
      setBadges(summary.badges);
      setHeatmapDays(summary.heatmap);
    });
  }, []);

  const earnedCount = badges?.filter((b) => b.earnedAt !== null).length ?? null;
  const lockedCount = badges ? badges.length - (earnedCount ?? 0) : null;

  const weeks = useMemo(() => {
    if (!heatmapDays) return null;
    const chunks: HeatmapDay[][] = [];
    for (let i = 0; i < heatmapDays.length; i += 7) chunks.push(heatmapDays.slice(i, i + 7));
    return chunks;
  }, [heatmapDays]);

  const lastWeek = heatmapDays ? heatmapDays.slice(-7) : null;
  const lastWeekMax = lastWeek ? Math.max(1, ...lastWeek.map((d) => d.count)) : 1;

  async function handleShare() {
    setShareStatus("loading");
    try {
      const summary = await shareWeeklySummary();
      if (typeof navigator !== "undefined" && navigator.share) {
        await navigator.share({ title: "My AfriMentor AI progress", text: summary.shareText });
        setShareStatus("shared");
      } else if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(summary.shareText);
        setShareStatus("copied");
      } else {
        setShareStatus("error");
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        setShareStatus("idle");
        return;
      }
      console.error("Failed to share weekly summary:", error);
      setShareStatus("error");
    } finally {
      setTimeout(() => setShareStatus("idle"), 2500);
    }
  }

  const shareLabel: Record<ShareStatus, string> = {
    idle: "Share weekly summary",
    loading: "Sharing...",
    shared: "Shared!",
    copied: "Copied to clipboard!",
    error: "Couldn't share — try again",
  };

  return (
    <main className="space-y-xl px-margin-mobile pb-24 pt-md md:mx-auto md:max-w-6xl md:space-y-lg md:px-lg md:pb-lg md:pt-lg">
      <section>
        <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface md:font-headline-lg md:text-headline-lg">
          Your Growth
        </h2>
        <p className="font-body-md text-on-surface-variant">Consistent action builds lasting wealth.</p>
      </section>

      {/* Desktop hero stats row — real streak/badge numbers from
          progress-gamification-service, not fabricated "Global Rank"/
          "Knowledge Points" stats. */}
      <section className="hidden gap-lg md:grid md:grid-cols-3">
        <div className="flex flex-col gap-sm rounded-xl border border-outline-variant/30 bg-secondary-container p-lg">
          <span className="font-label-sm text-label-sm uppercase tracking-widest text-on-secondary-container">
            Active Streak
          </span>
          <div className="flex items-baseline gap-sm">
            <span className="font-headline-xl text-headline-xl text-on-secondary-container">
              {streak?.currentStreakDays ?? "—"}
            </span>
            <span className="font-title-md text-title-md text-on-secondary-container/80">Days</span>
          </div>
          <span className="font-label-sm text-label-sm text-on-secondary-container/80">
            Longest: {streak?.longestStreakDays ?? "—"} days
          </span>
        </div>
        <div className="flex flex-col gap-sm rounded-xl border border-outline-variant/30 bg-surface-container-high p-lg">
          <span className="font-label-sm text-label-sm uppercase tracking-widest text-on-surface-variant">
            Badges Earned
          </span>
          <span className="font-headline-xl text-headline-xl text-on-surface">{earnedCount ?? "—"}</span>
          <span className="font-label-sm text-label-sm text-on-surface-variant">
            {lockedCount ?? "—"} still to unlock
          </span>
        </div>
        <div className="flex flex-col gap-sm rounded-xl border border-outline-variant/30 bg-surface-container-high p-lg">
          <span className="font-label-sm text-label-sm uppercase tracking-widest text-on-surface-variant">
            Actions Completed
          </span>
          <span className="font-headline-xl text-headline-xl text-on-surface">
            {streak?.actionsCompletedTotal ?? "—"}
          </span>
        </div>
      </section>

      {streak === null || lastWeek === null ? (
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
            {lastWeek.map((day) => {
              const h = Math.round(20 + (day.count / lastWeekMax) * 80);
              return (
                <div
                  key={day.date}
                  className={`w-full rounded-t-sm ${day.count >= lastWeekMax && day.count > 0 ? "bg-secondary" : "bg-secondary-container"}`}
                  style={{ height: `${h}%` }}
                  title={`${day.date}: ${day.count} action${day.count === 1 ? "" : "s"}`}
                />
              );
            })}
          </div>
          <div className="mt-sm flex justify-between font-label-sm text-[10px] text-on-surface-variant">
            {lastWeek.map((day) => (
              <span key={day.date}>{weekdayLabel(day.date)}</span>
            ))}
          </div>
        </div>
      )}

      <section className="space-y-md">
        <div className="flex items-center justify-between">
          <h3 className="font-title-md text-title-md text-on-surface">Action Heatmap</h3>
          <span className="font-label-sm text-label-sm text-on-surface-variant">Last 3 Months</span>
        </div>
        <div className="rounded border border-outline-variant bg-surface-container-lowest p-md md:p-lg">
          {weeks === null ? (
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
                {weeks.map((week, wi) => (
                  <div key={wi} className="grid grid-rows-7 gap-1 md:gap-[3px]">
                    {week.map((day) => (
                      <div
                        key={day.date}
                        title={`${day.date}: ${day.count} action${day.count === 1 ? "" : "s"}`}
                        className={`h-2.5 w-2.5 rounded-[2px] md:h-3 md:w-3 ${HEATMAP_INTENSITIES[intensityFor(day.count)]}`}
                      />
                    ))}
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="mt-md flex items-center justify-end gap-sm">
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

      <section className="space-y-md">
        <h3 className="font-title-md text-title-md text-on-surface">Badges Earned</h3>
        <div className="grid grid-cols-2 gap-md md:grid-cols-4 lg:grid-cols-6">
          {badges === null
            ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32 w-full rounded" />)
            : badges.map((b, i) => <BadgeTile key={b.id} badge={b} wide={i === 2} />)}
        </div>
      </section>

      <div className="flex flex-col items-center gap-sm md:items-start">
        <button
          onClick={handleShare}
          disabled={shareStatus === "loading"}
          className="flex w-full items-center justify-center gap-sm rounded-full bg-primary py-md text-on-primary shadow-md transition-transform active:scale-95 hover:opacity-90 disabled:opacity-70 md:w-auto md:px-xl"
        >
          <Icon name={shareStatus === "copied" || shareStatus === "shared" ? "check" : "share"} />
          <span className="font-title-md text-title-md">{shareLabel[shareStatus]}</span>
        </button>
        <button
          onClick={() => dispatch({ type: "OPEN_FEEDBACK_MODAL" })}
          className="font-label-sm text-label-sm text-on-surface-variant underline underline-offset-2 hover:text-on-surface"
        >
          Give feedback on your journey
        </button>
      </div>

      <p className="pb-lg text-center font-body-md text-[13px] italic text-on-surface-variant">
        Inspired by the Sankofa bird: Looking back to move forward.
      </p>
    </main>
  );
}
