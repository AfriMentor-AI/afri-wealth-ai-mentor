"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { fetchDailyAction, fetchProfile, fetchStreak } from "@/lib/api";
import type { DailyAction, Profile, StreakStat } from "@/lib/types";
import { Skeleton } from "@/components/ui/Skeleton";

type ActionState = "done" | "progress" | "help" | null;

export default function DailyActionCardPage() {
  const router = useRouter();
  const [action, setAction] = useState<DailyAction | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [streak, setStreak] = useState<StreakStat | null>(null);
  const [activeState, setActiveState] = useState<ActionState>(null);

  useEffect(() => {
    fetchDailyAction().then(setAction);
    fetchProfile().then(setProfile);
    fetchStreak().then(setStreak);
  }, []);

  const controls: { id: ActionState; label: string; icon: string; color: string }[] = [
    { id: "done", label: "Mark done", icon: "check_circle", color: "text-secondary" },
    { id: "progress", label: "In progress", icon: "schedule", color: "text-primary" },
    { id: "help", label: "Need help", icon: "help_outline", color: "text-error" },
  ];

  return (
    <div className="min-h-full bg-surface">
      <header className="sticky top-0 z-10 flex items-center justify-between bg-surface px-margin-mobile py-sm">
        <div className="flex items-center gap-sm">
          <button
            onClick={() => router.back()}
            aria-label="Go back"
            className="tap-target flex items-center justify-center rounded-full text-on-surface-variant"
          >
            <Icon name="arrow_back" />
          </button>
          <h1 className="font-headline-lg-mobile text-headline-lg-mobile text-primary">AfriMentor AI</h1>
        </div>
        <div className="flex items-center gap-sm">
          <ThemeToggle />
          <div className="relative h-9 w-9 shrink-0 overflow-hidden rounded-full border-2 border-primary">
            <Image src="/images/chioma-avatar.png" alt="Chioma" fill className="object-cover" />
          </div>
        </div>
      </header>

      <main className="flex flex-col gap-lg px-margin-mobile pb-32 pt-lg">
        <section className="flex flex-col gap-xs">
          <p className="font-label-sm text-label-sm uppercase tracking-widest text-on-surface-variant">
            Good Morning{profile ? `, ${profile.name.split(" ")[0]}` : ""}
          </p>
          <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface">Ready to grow?</h2>
        </section>

        {action === null ? (
          <Skeleton className="h-56 w-full rounded" />
        ) : (
          <div className="rounded border border-outline-variant p-lg">
            <div className="flex items-center justify-between">
              <span className="rounded-full bg-secondary-container px-md py-xs font-label-sm text-label-sm text-on-secondary-container">
                Savings
              </span>
              {streak && (
                <div className="flex items-center gap-xs rounded-full border border-primary/20 bg-primary-container/10 px-md py-xs">
                  <span className="font-bold text-primary">🔥 {streak.currentStreakDays} day streak</span>
                </div>
              )}
            </div>

            <div className="mt-md flex flex-col gap-sm">
              <h3 className="font-headline-lg-mobile text-headline-lg-mobile leading-tight text-on-surface">
                {action.title}
              </h3>
              <p className="font-body-md text-body-md text-on-surface-variant">{action.description}</p>
            </div>

            <div className="mt-md grid grid-cols-1 gap-sm">
              {controls.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setActiveState(c.id)}
                  aria-pressed={activeState === c.id}
                  className={`tap-target flex items-center justify-between rounded border-2 px-lg py-md transition-all active:scale-[0.98] ${
                    activeState === c.id ? "border-primary bg-primary-container/10" : "border-outline-variant bg-surface hover:bg-surface-container-low"
                  }`}
                >
                  <span className="font-title-md text-title-md text-on-surface">{c.label}</span>
                  <Icon name={c.icon} className={c.color} />
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="rounded border border-outline-variant bg-surface-container-low p-md">
          <div className="flex items-start gap-md">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary">
              <Icon name="smart_toy" className="text-on-primary" />
            </div>
            <div className="flex flex-col gap-xs">
              <p className="font-label-sm text-label-sm text-primary">MENTOR ADVICE</p>
              <p className="font-body-md text-body-md italic text-on-surface">
                &ldquo;Consistency is the key to resilience{profile ? `, ${profile.name.split(" ")[0]}` : ""}. How can I
                assist with your savings today?&rdquo;
              </p>
            </div>
          </div>
        </div>

        <section className="flex flex-col gap-md">
          <h4 className="font-title-md text-title-md px-xs">This Month&rsquo;s Growth</h4>
          <div className="flex items-center gap-lg rounded border border-outline-variant bg-surface p-lg">
            <div className="relative h-20 w-20 shrink-0">
              <svg viewBox="0 0 36 36" className="h-full w-full">
                <path
                  className="text-surface-container-highest"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="3"
                />
                <path
                  className="text-secondary"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke="currentColor"
                  strokeDasharray="70, 100"
                  strokeLinecap="round"
                  strokeWidth="3"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center font-bold text-secondary">70%</div>
            </div>
            <div className="flex flex-col gap-xs">
              <p className="font-title-md text-title-md">GHC 450.00</p>
              <p className="font-label-sm text-label-sm text-on-surface-variant">Saved towards Emergency Fund</p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
