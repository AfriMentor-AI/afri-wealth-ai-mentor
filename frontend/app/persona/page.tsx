"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { ThemeToggle } from "@/components/ThemeToggle";
import { fetchPersonas } from "@/lib/api";
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

export default function PersonaSelectionPage() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const [personas, setPersonas] = useState<Persona[] | null>(null);

  useEffect(() => {
    fetchPersonas().then(setPersonas);
  }, []);

  function choose(persona: Persona) {
    dispatch({ type: "SET_PERSONA", persona });
    router.push("/chat");
  }

  return (
    <div className="mx-auto min-h-screen max-w-2xl bg-surface">
      <header className="flex items-center justify-between px-margin-mobile py-md">
        <p className="font-title-md text-title-md text-on-surface">AfriMentor AI</p>
        <ThemeToggle />
      </header>

      <main className="px-margin-mobile pb-24">
        <h1 className="font-headline-lg-mobile text-headline-lg-mobile text-on-background">Choose your mentor</h1>
        <p className="mt-xs font-body-md text-body-md text-on-surface-variant">
          Select a guide who understands your journey and speaks your language.
        </p>

        <div className="mt-lg flex flex-col gap-md md:grid md:grid-cols-2">
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
                      className={`tap-target flex-1 rounded-full py-md font-label-sm text-label-sm transition-transform active:scale-95 ${
                        persona.isRecommended ? "bg-primary text-on-primary" : "bg-surface-variant text-on-surface-variant"
                      }`}
                    >
                      {persona.isRecommended ? "Select Mentor" : "Hear an example"}
                    </button>
                    {!persona.isRecommended && (
                      <button
                        onClick={() => choose(persona)}
                        aria-label={`Select ${persona.name} as mentor`}
                        className="tap-target flex items-center justify-center rounded-full border border-outline-variant px-md text-on-surface-variant"
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
  );
}
