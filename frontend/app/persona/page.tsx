"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/Button";
import { fetchPersonas, startChatSession, selectPersona } from "@/lib/api";
import type { Persona } from "@/lib/types";
import { useAppDispatch } from "@/lib/store";
import { Skeleton } from "@/components/ui/Skeleton";

function initials(name: string) {
  return name
    .replace("The ", "")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2);
}

const PERSONA_ICONS: Record<string, string> = {
  "market-queen": "storefront",
  "tech-founder": "computer",
  trader: "swap_horiz",
  "rural-hustler": "agriculture",
  creative: "palette",
};

export default function PersonaSelectionPage() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const [personas, setPersonas] = useState<Persona[] | null>(null);
  const [selectingId, setSelectingId] = useState<string | null>(null);

  useEffect(() => {
    fetchPersonas().then(setPersonas);
  }, []);

  async function choose(persona: Persona) {
    setSelectingId(persona.id);
    dispatch({ type: "SET_PERSONA", persona });
    try {
      const sessionId = await startChatSession(persona.id);
      dispatch({ type: "SET_CHAT_SESSION_ID", sessionId });
      // Notify persona-prompt-service of the session binding
      selectPersona(persona.id, sessionId).catch((err) =>
        console.warn("selectPersona notice:", err)
      );
      router.push("/chat");
    } catch (error) {
      console.error("Failed to start chat session:", error);
      setSelectingId(null);
    }
  }

  return (
    <div className="min-h-screen bg-surface">
      {/* ========================================================================= */}
      {/* MOBILE VIEW (md:hidden) — 100% original mobile design & layout */}
      {/* ========================================================================= */}
      <div className="mx-auto min-h-screen max-w-2xl bg-surface md:hidden">
        <header className="flex items-center justify-between px-margin-mobile py-md">
          <p className="font-title-md text-title-md text-on-surface">AfriMentor AI</p>
          <ThemeToggle />
        </header>

        <main className="px-margin-mobile pb-24">
          <h1 className="font-headline-lg-mobile text-headline-lg-mobile text-on-background">Choose your mentor</h1>
          <p className="mt-xs font-body-md text-body-md text-on-surface-variant">
            Select a guide who understands your journey and speaks your language.
          </p>

          <div className="mt-lg flex flex-col gap-md">
            {personas === null
              ? Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-32 w-full rounded" />)
              : personas.map((persona) => (
                  <div
                    key={persona.id}
                    className={`relative rounded border p-md ${
                      persona.isRecommended
                        ? "border-primary-container bg-surface-container-low ring-2 ring-primary/10"
                        : "border-outline-variant bg-surface-container-low"
                    }`}
                  >
                    {persona.isRecommended && (
                      <div className="absolute -top-3 left-4 flex items-center gap-xs rounded-full bg-primary px-sm py-xs text-on-primary">
                        <Icon name="workspace_premium" filled size={14} />
                        <span className="font-label-sm text-label-sm uppercase tracking-wider">Recommended for you</span>
                      </div>
                    )}
                    <div className="mt-sm flex items-start gap-md">
                      <div
                        className={`flex h-16 w-16 shrink-0 items-center justify-center rounded-full border-2 font-headline-lg-mobile text-[20px] ${
                          persona.isRecommended
                            ? "border-primary-container bg-primary-container text-on-primary-container"
                            : "border-outline-variant bg-surface-variant text-on-surface-variant"
                        }`}
                      >
                        {initials(persona.name)}
                      </div>
                      <div className="flex-1">
                        <h3 className="font-title-md text-title-md text-on-surface">{persona.name}</h3>
                        <p className="font-body-md text-body-md text-on-surface-variant">{persona.tagline}</p>
                      </div>
                    </div>
                    <div className="mt-md flex gap-sm">
                      <button
                        onClick={() => choose(persona)}
                        disabled={selectingId !== null}
                        className={`tap-target flex-1 rounded-full py-md font-label-sm text-label-sm transition-transform active:scale-95 disabled:opacity-50 ${
                          persona.isRecommended ? "bg-primary text-on-primary" : "bg-surface-variant text-on-surface-variant"
                        }`}
                      >
                        {selectingId === persona.id
                          ? "Starting..."
                          : persona.isRecommended
                          ? "Select Mentor"
                          : "Hear an example"}
                      </button>
                      {!persona.isRecommended && (
                        <button
                          onClick={() => choose(persona)}
                          disabled={selectingId !== null}
                          aria-label={`Select ${persona.name} as mentor`}
                          className="tap-target flex items-center justify-center rounded-full border border-outline-variant px-md text-on-surface-variant disabled:opacity-50"
                        >
                          <Icon name="check" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
          </div>
        </main>
      </div>

      {/* ========================================================================= */}
      {/* DESKTOP VIEW (hidden md:flex) — Enhanced responsive desktop experience */}
      {/* ========================================================================= */}
      <div className="mx-auto hidden min-h-screen max-w-6xl flex-col justify-between px-xl py-lg md:flex">
        {/* Top Header */}
        <header className="flex items-center justify-between border-b border-outline-variant/40 pb-md">
          <div className="flex items-center gap-md">
            <button
              onClick={() => router.push("/intake")}
              aria-label="Back to intake"
              className="tap-target -ml-2 flex items-center justify-center rounded-full p-2 text-on-surface-variant hover:bg-surface-container-low transition-colors"
            >
              <Icon name="arrow_back" />
            </button>
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary-container text-on-primary-container">
              <Icon name="psychology" size={26} />
            </div>
            <div>
              <p className="font-headline-lg-mobile text-[18px] font-bold leading-none text-primary">AfriMentor AI</p>
              <p className="font-label-sm text-label-sm text-on-surface-variant">Mentor Selection • Final Step</p>
            </div>
          </div>
          <div className="flex items-center gap-md">
            <span className="rounded-full bg-secondary-container/50 px-md py-xs font-label-sm text-label-sm text-on-secondary-container">
              Step 4 of 4: Choose Guide
            </span>
            <ThemeToggle />
          </div>
        </header>

        {/* Headline Section */}
        <main className="flex-1 py-xl">
          <div className="mb-xl flex flex-col gap-xs">
            <h1 className="font-headline-xl text-headline-xl text-on-surface">Choose Your Mentor</h1>
            <p className="max-w-2xl font-body-lg text-body-lg text-on-surface-variant">
              Select a mentor grounded in African business wisdom, cultural context, and real-world execution.
              Your guide will tailor daily milestones and guidance to your goals.
            </p>
          </div>

          {/* Persona Card Grid */}
          <div className="grid grid-cols-2 gap-lg lg:grid-cols-3">
            {personas === null
              ? Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-64 w-full rounded-2xl" />
                ))
              : personas.map((persona) => {
                  const iconName = PERSONA_ICONS[persona.id] || "person";
                  const isSelecting = selectingId === persona.id;

                  return (
                    <div
                      key={persona.id}
                      className={`relative flex flex-col justify-between rounded-2xl border p-lg transition-all hover:shadow-md ${
                        persona.isRecommended
                          ? "border-primary bg-primary-container/10 ring-2 ring-primary/30"
                          : "border-outline-variant/70 bg-surface-container-low hover:border-outline"
                      }`}
                    >
                      {persona.isRecommended && (
                        <div className="absolute -top-3.5 left-6 flex items-center gap-xs rounded-full bg-primary px-md py-xs text-on-primary shadow-sm">
                          <Icon name="workspace_premium" filled size={16} />
                          <span className="font-label-sm text-label-sm font-bold uppercase tracking-wider">
                            Recommended for you
                          </span>
                        </div>
                      )}

                      <div>
                        <div className="mt-sm flex items-start gap-md">
                          <div
                            className={`flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl border-2 font-headline-lg-mobile text-[22px] font-bold ${
                              persona.isRecommended
                                ? "border-primary-container bg-primary-container text-on-primary-container"
                                : "border-outline-variant bg-surface-variant text-on-surface-variant"
                            }`}
                          >
                            <Icon name={iconName} size={28} />
                          </div>
                          <div className="flex-1">
                            <h3 className="font-title-md text-title-md font-bold text-on-surface">{persona.name}</h3>
                            <span className="font-label-sm text-[12px] text-primary">
                              {initials(persona.name)} • AfriMentor
                            </span>
                          </div>
                        </div>

                        <p className="mt-md font-body-md text-body-md leading-relaxed text-on-surface-variant">
                          {persona.tagline}
                        </p>
                      </div>

                      <div className="mt-lg flex items-center gap-sm pt-md border-t border-outline-variant/30">
                        <Button
                          variant={persona.isRecommended ? "cta" : "primary"}
                          disabled={selectingId !== null}
                          onClick={() => choose(persona)}
                          className="h-12 flex-1 text-[16px]"
                        >
                          {isSelecting ? "Starting Chat..." : "Select Mentor"}
                          {!isSelecting && <Icon name="arrow_forward" />}
                        </Button>
                      </div>
                    </div>
                  );
                })}
          </div>
        </main>

        {/* Footer */}
        <footer className="border-t border-outline-variant/40 py-md">
          <div className="flex items-center justify-between text-on-surface-variant">
            <div className="flex items-center gap-sm">
              <Icon name="spa" className="text-primary" />
              <span className="font-label-sm text-label-sm">
                Rooted in West African business traditions. Switch mentors anytime in settings.
              </span>
            </div>
            <span className="font-label-sm text-label-sm text-on-surface-variant/70">
              Secure • Communal • Tailored
            </span>
          </div>
        </footer>
      </div>
    </div>
  );
}
