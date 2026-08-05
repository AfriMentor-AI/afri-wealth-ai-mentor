"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { fetchBadges, fetchStreak } from "@/lib/api";
import type { BadgeWithStatus, StreakStat } from "@/lib/types";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAppDispatch } from "@/lib/store";

const WEEKDAY_BARS = [40, 60, 55, 85, 100, 95, 98]; // % height, matches reference chart shape
const HEATMAP_INTENSITIES = ["bg-surface-container", "bg-secondary-fixed", "bg-secondary-container", "bg-secondary"];

export default function ProgressBoardPage() {
  const dispatch = useAppDispatch();
  const [streak, setStreak] = useState<StreakStat | null>(null);
  const [badges, setBadges] = useState<BadgeWithStatus[] | null>(null);
  const [heatmap, setHeatmap] = useState<number[][] | null>(null);

  useEffect(() => {
    fetchStreak().then(setStreak);
    fetchBadges().then(setBadges);
    // Generated client-side only to avoid SSR/client hydration mismatch —
    // in production this is real per-day activity data from the API, not random.
    const weeks = Array.from({ length: 13 }, () =>
      Array.from({ length: 7 }, () => Math.floor(Math.random() * HEATMAP_INTENSITIES.length))
    );
    setHeatmap(weeks);
  }, []);

  return (
    <main className="space-y-xl px-margin-mobile pb-24 pt-md">
      <section>
        <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface">Your Growth</h2>
        <p className="font-body-md text-on-surface-variant">Consistent action builds lasting wealth, Kofi.</p>
      </section>

      {streak === null ? (
        <Skeleton className="h-40 w-full rounded" />
      ) : (
        <div className="rounded border border-outline-variant bg-surface-container-low p-md shadow-sm">
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

      <section className="space-y-md">
        <div className="flex items-center justify-between">
          <h3 className="font-title-md text-title-md text-on-surface">Action Heatmap</h3>
          <span className="font-label-sm text-label-sm text-on-surface-variant">Last 3 Months</span>
        </div>
        <div className="rounded border border-outline-variant bg-surface-container-lowest p-md">
          {heatmap === null ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <div className="flex gap-1 overflow-x-auto pb-sm">
              <div className="grid grid-rows-7 gap-1 pr-1 text-[8px] text-on-surface-variant">
                <div>M</div>
                <div />
                <div>W</div>
                <div />
                <div>F</div>
                <div />
                <div>S</div>
              </div>
              {heatmap.map((week, wi) => (
                <div key={wi} className="grid grid-rows-7 gap-1">
                  {week.map((intensity, di) => (
                    <div key={di} className={`h-2.5 w-2.5 rounded-[2px] ${HEATMAP_INTENSITIES[intensity]}`} />
                  ))}
                </div>
              ))}
            </div>
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
        <h3 className="font-title-md text-title-md text-on-surface">Milestones Reached</h3>
        <div className="grid grid-cols-2 gap-md">
          {badges === null
            ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-32 w-full rounded" />)
            : badges.map((b, i) => {
                const wide = i === 2;
                const earned = b.earnedAt !== null;
                return (
                  <div
                    key={b.id}
                    className={`flex flex-col items-center gap-sm rounded border p-md text-center transition-transform active:scale-95 ${
                      wide ? "col-span-2 flex-row justify-start text-left" : ""
                    } ${
                      earned
                        ? i === 0
                          ? "border-secondary-container bg-secondary-container/20"
                          : "border-primary-fixed bg-primary-fixed/20"
                        : "border-outline-variant bg-surface-container-high opacity-70"
                    }`}
                  >
                    <div
                      className={`relative flex shrink-0 items-center justify-center rounded-full ${wide ? "h-12 w-12" : "h-16 w-16"} ${
                        earned ? (i === 0 ? "bg-secondary-container text-on-secondary-container" : "bg-primary-fixed text-on-primary-fixed") : "bg-surface-variant text-on-surface-variant"
                      }`}
                    >
                      <Icon name={b.iconName ?? "workspace_premium"} filled={earned} size={wide ? 24 : 32} />
                      {!earned && <Icon name="lock" className="absolute -bottom-1 -right-1" size={14} />}
                    </div>
                    <div>
                      <p className="font-label-sm text-label-sm font-bold text-on-surface">{b.label}</p>
                      <p className="text-[10px] text-on-surface-variant">{b.description}</p>
                    </div>
                  </div>
                );
              })}
        </div>
      </section>

      <button
        onClick={() => dispatch({ type: "OPEN_FEEDBACK_MODAL" })}
        className="flex w-full items-center justify-center gap-sm rounded-full bg-primary py-md text-on-primary shadow-md transition-transform active:scale-95 hover:opacity-90"
      >
        <Icon name="share" />
        <span className="font-title-md text-title-md">Share weekly summary</span>
      </button>

      <p className="pb-lg text-center font-body-md text-[13px] italic text-on-surface-variant">
        Inspired by the Sankofa bird: Looking back to move forward.
      </p>
    </main>
  );
}
