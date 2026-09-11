"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { fetchDailyAction, fetchGoals, fetchProfile, fetchStreak, recordAction } from "@/lib/api";
import type { DailyAction, Goal, Profile, StreakStat } from "@/lib/types";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAppDispatch } from "@/lib/store";

type ActionState = "done" | "progress" | "help" | null;

export default function DailyActionCardPage() {
  const router = useRouter();
  const dispatch = useAppDispatch();

  const [action, setAction] = useState<DailyAction | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [streak, setStreak] = useState<StreakStat | null>(null);
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [activeState, setActiveState] = useState<ActionState>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [feedbackNotice, setFeedbackNotice] = useState<string | null>(null);

  useEffect(() => {
    fetchDailyAction().then((a) => {
      setAction(a);
      if (a?.done) {
        setActiveState("done");
      }
    });
    fetchProfile().then(setProfile);
    fetchStreak().then(setStreak);
    fetchGoals().then(setGoals);
  }, []);

  async function handleControlClick(state: ActionState) {
    if (state === "done") {
      setIsRecording(true);
      setFeedbackNotice(null);
      try {
        const res = await recordAction("daily_action");
        setStreak(res.streak);
        setActiveState("done");
        if (action) {
          setAction({ ...action, done: true });
        }
        if (res.newlyEarnedBadges && res.newlyEarnedBadges.length > 0) {
          setFeedbackNotice(`🎉 Action recorded! You unlocked: ${res.newlyEarnedBadges[0].label}`);
        } else {
          setFeedbackNotice(`✨ Great job! Your streak is now ${res.streak.currentStreakDays} days.`);
        }
      } catch (err) {
        console.warn("Failed to record action:", err);
        setActiveState("done");
        setFeedbackNotice("Marked done for today.");
      } finally {
        setIsRecording(false);
      }
    } else if (state === "help") {
      setActiveState("help");
      const actionTitle = action?.title || "today's daily action";
      dispatch({
        type: "SET_CHAT_DRAFT",
        draft: `I need help with my daily action: "${actionTitle}". Can you give me clear, practical advice on how to get started?`,
      });
      router.push("/chat");
    } else {
      setActiveState(state);
    }
  }

  const controls: { id: ActionState; label: string; icon: string; color: string }[] = [
    { id: "done", label: activeState === "done" ? "Completed" : "Mark done", icon: "check_circle", color: "text-secondary" },
    { id: "progress", label: "In progress", icon: "schedule", color: "text-primary" },
    { id: "help", label: "Need help", icon: "help_outline", color: "text-error" },
  ];

  const primaryGoal = goals && goals.length > 0
    ? goals.find((g) => g.progressPct < 100) || goals[0]
    : null;

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

        {feedbackNotice && (
          <div className="rounded-xl border border-secondary/30 bg-secondary-container p-md font-label-sm text-sm text-on-secondary-container shadow-sm animate-fadeIn">
            {feedbackNotice}
          </div>
        )}

        {action === null ? (
          <Skeleton className="h-56 w-full rounded" />
        ) : (
          <div className="rounded border border-outline-variant p-lg">
            <div className="flex items-center justify-between">
              <span className="rounded-full bg-secondary-container px-md py-xs font-label-sm text-label-sm text-on-secondary-container">
                Daily Focus
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
                  disabled={isRecording}
                  onClick={() => handleControlClick(c.id)}
                  aria-pressed={activeState === c.id}
                  className={`tap-target flex items-center justify-between rounded border-2 px-lg py-md transition-all active:scale-[0.98] ${
                    activeState === c.id ? "border-primary bg-primary-container/10" : "border-outline-variant bg-surface hover:bg-surface-container-low"
                  }`}
                >
                  <span className="font-title-md text-title-md text-on-surface">
                    {c.id === "done" && isRecording ? "Recording..." : c.label}
                  </span>
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
                &ldquo;Consistency is the key to resilience{profile ? `, ${profile.name.split(" ")[0]}` : ""}. {action ? `Taking 10 minutes to focus on "${action.title.toLowerCase()}" today will compound into significant stability for your ${profile?.sector ?? "enterprise"}.` : "How can I assist with your savings today?"}&rdquo;
              </p>
            </div>
          </div>
        </div>

        <section className="flex flex-col gap-md">
          <h4 className="font-title-md text-title-md px-xs">This Month&rsquo;s Growth</h4>
          {goals === null ? (
            <Skeleton className="h-28 w-full rounded border border-outline-variant" />
          ) : primaryGoal ? (
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
                    strokeDasharray={`${primaryGoal.progressPct}, 100`}
                    strokeLinecap="round"
                    strokeWidth="3"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center font-bold text-secondary">
                  {primaryGoal.progressPct}%
                </div>
              </div>
              <div className="flex flex-col gap-xs min-w-0">
                <p className="font-title-md text-title-md truncate">{primaryGoal.title}</p>
                <p className="font-label-sm text-label-sm text-on-surface-variant">
                  {primaryGoal.deadline
                    ? `Target: ${new Date(primaryGoal.deadline).toLocaleDateString(undefined, {
                        year: "numeric",
                        month: "short",
                        day: "numeric",
                      })}`
                    : "Guided progression with your mentor"}
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between rounded border border-dashed border-outline-variant bg-surface p-lg">
              <div className="flex flex-col gap-xs">
                <p className="font-title-md text-title-md text-on-surface">No active goals yet</p>
                <p className="font-label-sm text-label-sm text-on-surface-variant">Set your first business target to track progress</p>
              </div>
              <button
                type="button"
                onClick={() => router.push("/goals")}
                className="rounded-full bg-primary px-md py-xs font-label-sm text-xs font-semibold text-on-primary"
              >
                Create Goal
              </button>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
