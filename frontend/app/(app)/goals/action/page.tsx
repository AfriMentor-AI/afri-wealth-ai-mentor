"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { AppFrame, KenteStrip } from "@/components/shell/AppSidebar";
import { fetchDailyAction, fetchProfile, fetchStreak } from "@/lib/api";
import type { DailyAction, Profile, StreakStat } from "@/lib/types";
import { useAppState } from "@/lib/store";
import { mentorFor } from "@/lib/mentors";
import { img } from "@/lib/stitchImages";

type ActionState = "done" | "progress" | "help" | null;

const CONTROLS: { id: Exclude<ActionState, null>; label: string; icon: string }[] = [
  { id: "done", label: "Mark as done", icon: "check_circle" },
  { id: "progress", label: "In progress", icon: "schedule" },
  { id: "help", label: "Need help", icon: "help" },
];

export default function DailyActionPage() {
  const { selectedPersona: persona } = useAppState();
  const mentor = mentorFor(persona);
  const [action, setAction] = useState<DailyAction | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [streak, setStreak] = useState<StreakStat | null>(null);
  const [state, setState] = useState<ActionState>(null);

  useEffect(() => {
    fetchDailyAction().then(setAction).catch(() => {});
    fetchProfile().then(setProfile).catch(() => {});
    fetchStreak().then(setStreak).catch(() => {});
  }, []);

  const first = profile?.name?.split(" ")[0];

  return (
    <AppFrame title="Today’s action">
      <KenteStrip />
      <main className="mx-auto max-w-3xl px-5 pb-16 pt-6 md:px-10 md:pt-10">
        <nav className="mb-5 flex items-center gap-2 font-caption text-caption text-on-surface-variant" aria-label="Breadcrumb">
          <Link href="/goals" className="flex items-center gap-1 hover:text-primary"><Icon name="flag" size={16} /> Goals</Link>
          <span>/</span><span className="text-primary">Execute action</span>
        </nav>

        <section className="overflow-hidden rounded-3xl border border-outline-variant bg-surface-container-lowest p-6 shadow-sm md:p-10">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="rounded-full bg-gold-mist px-3 py-1.5 font-eyebrow text-eyebrow uppercase text-sunburst-gold"><Icon name="bolt" size={14} className="mr-1 align-[-2px]" />Mentor action trigger</span>
            {streak && <span className="rounded-full border border-primary/25 bg-primary/10 px-3 py-1.5 font-label-sm text-label-sm text-primary">🔥 {streak.currentStreakDays} day streak</span>}
          </div>

          <p className="mt-6 font-eyebrow text-eyebrow uppercase text-on-surface-variant">Good morning{first ? `, ${first}` : ""}</p>
          {action === null ? (
            <div className="mt-3 space-y-3"><div className="h-10 w-4/5 animate-pulse rounded-lg bg-surface-container-low" /><div className="h-5 w-3/5 animate-pulse rounded-lg bg-surface-container-low" /></div>
          ) : (
            <>
              <h1 className="mt-2 font-headline-lg-mobile text-headline-lg-mobile text-on-surface md:font-headline-xl md:text-[44px] md:leading-[52px]">{action.title}</h1>
              {action.description && action.description !== action.title && <p className="mt-3 font-body-lg text-body-lg text-on-surface-variant">{action.description}</p>}
            </>
          )}

          <div className="mt-8 flex items-start gap-4 rounded-2xl border-l-4 border-sunburst-gold bg-surface-container-low p-5">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={img(mentor.avatar)} alt="" className="h-14 w-14 shrink-0 rounded-full border-2 border-sunburst-gold object-cover" />
            <div>
              <p className="font-label-sm text-label-sm text-on-surface">{mentor.name} <span className="font-normal text-on-surface-variant">· {mentor.role}</span></p>
              <p className="mt-1 font-quote text-[18px] italic leading-7 text-on-surface">“Consistency is the key to resilience{first ? `, ${first}` : ""}. Take the step today, then tell me how it went.”</p>
            </div>
          </div>

          <div className="mt-8 grid gap-3 sm:grid-cols-3">
            {CONTROLS.map((c) => {
              const on = state === c.id;
              return (
                <button key={c.id} type="button" onClick={() => setState(c.id)} aria-pressed={on} className={`flex items-center justify-between gap-2 rounded-2xl border-2 px-5 py-4 text-left font-label-sm text-[15px] transition-all active:scale-[0.98] ${on ? (c.id === "done" ? "border-primary bg-primary/10" : c.id === "help" ? "border-error bg-error-container/40" : "border-sunburst-gold bg-gold-mist") : "border-outline-variant bg-surface hover:bg-surface-container-low"}`}>
                  <span className="text-on-surface">{c.label}</span>
                  <Icon name={c.icon} filled={on} className={c.id === "done" ? "text-primary" : c.id === "help" ? "text-error" : "text-sunburst-gold"} />
                </button>
              );
            })}
          </div>

          {state === "done" && <p role="status" className="mt-5 flex items-center gap-2 font-label-sm text-label-sm text-primary"><Icon name="verified" size={18} filled /> Nicely done. Log it on your <Link href="/progress" className="underline">Progress</Link> page to keep your streak alive.</p>}
          {state === "help" && <p role="status" className="mt-5 font-label-sm text-label-sm text-on-surface-variant">Stuck? <Link href="/chat" className="text-primary underline">Ask your mentor</Link> to break this step down.</p>}
        </section>
      </main>
    </AppFrame>
  );
}
