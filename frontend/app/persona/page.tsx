"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { ThemeToggleButton } from "@/components/ThemeSwitch";
import { KenteStrip } from "@/components/shell/AppSidebar";
import { fetchPersonas, startChatSession, selectPersona } from "@/lib/api";
import type { Persona } from "@/lib/types";
import { useAppDispatch } from "@/lib/store";
import { mentorFor, ACCENT_TEXT, ACCENT_BORDER, ACCENT_BG } from "@/lib/mentors";
import { playTextToSpeech, stopCurrentSpeech } from "@/lib/voice";
import { img } from "@/lib/stitchImages";

export default function PersonaSelectionPage() {
  const router = useRouter();
  const dispatch = useAppDispatch();
  const [personas, setPersonas] = useState<Persona[] | null>(null);
  const [selectingId, setSelectingId] = useState<string | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    fetchPersonas().then((p) => mounted.current && setPersonas(p));
    return () => {
      mounted.current = false;
      stopCurrentSpeech();
    };
  }, []);

  async function choose(persona: Persona) {
    stopCurrentSpeech();
    setError(null);
    setSelectingId(persona.id);
    dispatch({ type: "SET_PERSONA", persona });
    try {
      const sessionId = await startChatSession(persona.id);
      dispatch({ type: "SET_CHAT_SESSION_ID", sessionId });
      // Notify persona-prompt-service of the session binding
      selectPersona(persona.id, sessionId).catch((err) => console.warn("selectPersona notice:", err));
      router.push("/chat");
    } catch (e) {
      console.error("Failed to start chat session:", e);
      setError("Couldn't start your session — check your connection and try again.");
      setSelectingId(null);
    }
  }

  function hear(persona: Persona) {
    const m = mentorFor(persona);
    if (playingId === persona.id) {
      stopCurrentSpeech();
      setPlayingId(null);
      return;
    }
    setPlayingId(persona.id);
    playTextToSpeech(m.welcome, persona.id, () => mounted.current && setPlayingId(null)).catch(() => setPlayingId(null));
  }

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      <KenteStrip />
      <header className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-5 py-4 md:px-10">
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => router.push("/intake")} aria-label="Back to intake" className="flex h-10 w-10 items-center justify-center rounded-full text-on-surface-variant transition-colors hover:bg-surface-container-low">
            <Icon name="arrow_back" />
          </button>
          <div>
            <p className="font-eyebrow text-eyebrow uppercase text-sunburst-gold">Dignified Growth</p>
            <p className="font-title-md text-[22px] leading-none text-on-surface">AfriMentor AI</p>
          </div>
        </div>
        <ThemeToggleButton />
      </header>

      <main className="mx-auto max-w-7xl px-5 pb-16 md:px-10">
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-full bg-surface-container-low px-3 py-1 font-eyebrow text-eyebrow uppercase text-on-surface-variant">
            <span className="text-sunburst-gold">●</span> Mentor selection · Final step
          </span>
          <span className="font-label-sm text-label-sm text-on-surface-variant">Step 4 of 4</span>
        </div>
        <h1 className="mt-4 font-headline-xl-mobile text-headline-xl-mobile text-on-surface md:font-headline-xl md:text-[56px] md:leading-[62px]">Choose your mentor</h1>
        <p className="mt-3 max-w-3xl font-body-lg text-body-lg text-on-surface-variant">
          Every mentor embodies a proven domain of trade across Lagos, Nairobi, Kigali, Accra and Kano — grounded in ancestral lore, calibrated to your enterprise reality.
        </p>

        {error && <p role="alert" className="mt-4 rounded-xl bg-error-container px-4 py-3 font-label-sm text-label-sm text-on-error-container">{error}</p>}

        <div className="mt-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {personas === null
            ? Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-[520px] animate-pulse rounded-3xl bg-surface-container-low" />)
            : personas.map((persona) => {
                const m = mentorFor(persona);
                const rec = !!persona.isRecommended;
                const busy = selectingId !== null;
                return (
                  <article
                    key={persona.id}
                    className={`relative flex flex-col overflow-hidden rounded-3xl border bg-surface-container-lowest p-4 shadow-sm transition-shadow hover:shadow-lg ${rec ? "border-sunburst-gold ring-2 ring-sunburst-gold/40" : "border-outline-variant"}`}
                  >
                    <span className={`absolute inset-x-0 top-0 h-1.5 ${ACCENT_BG[m.accent]}`} />
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <span className={`rounded-full bg-surface-container-low px-3 py-1 font-eyebrow text-eyebrow uppercase ${ACCENT_TEXT[m.accent]}`}>
                        {rec ? "Recommended for you" : m.domain}
                      </span>
                    </div>
                    <div className={`relative mx-auto mt-4 w-full overflow-hidden rounded-t-[999px] rounded-b-2xl border-2 ${ACCENT_BORDER[m.accent]}`}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={img(m.portrait)} alt={m.name} className="aspect-[4/5] w-full object-cover" />
                      <span className="absolute bottom-2 left-2 rounded-full bg-ink/60 px-2.5 py-1 font-caption text-caption text-white backdrop-blur">{m.place}</span>
                    </div>
                    <h2 className="mt-4 font-title-md text-title-md text-on-surface">{m.name}</h2>
                    <p className={`font-eyebrow text-eyebrow uppercase ${ACCENT_TEXT[m.accent]}`}>{m.role}</p>
                    <p className="mt-2 font-body-md text-[14px] leading-5 text-on-surface-variant">{m.focus}</p>
                    <blockquote className={`mt-4 rounded-xl border-l-4 bg-surface-container-low px-4 py-3 ${ACCENT_BORDER[m.accent]}`}>
                      <p className="font-quote text-[16px] italic leading-6 text-on-surface">“{m.quote}”</p>
                      <footer className="mt-2 font-eyebrow text-[10px] uppercase tracking-wider text-on-surface-variant">{m.quoteSource}</footer>
                    </blockquote>
                    <div className="mt-auto flex flex-col gap-2 pt-5">
                      <button type="button" onClick={() => hear(persona)} aria-pressed={playingId === persona.id} className={`flex h-10 items-center justify-between rounded-lg bg-surface-container-low px-3 font-label-sm text-label-sm ${ACCENT_TEXT[m.accent]}`}>
                        <span className="flex items-center gap-2"><Icon name={playingId === persona.id ? "stop_circle" : "volume_up"} size={20} /> {playingId === persona.id ? "Stop" : "Hear an example"}</span>
                        <Icon name="graphic_eq" size={18} className={playingId === persona.id ? "animate-pulse" : ""} />
                      </button>
                      <button
                        type="button"
                        onClick={() => choose(persona)}
                        disabled={busy}
                        className={`flex h-12 items-center justify-center gap-2 rounded-full font-label-sm text-[15px] font-bold transition-all active:scale-[0.98] disabled:opacity-50 ${rec ? "bg-sunburst-gold text-ink shadow-md" : "border border-outline text-on-surface hover:bg-surface-container-low"}`}
                      >
                        {selectingId === persona.id ? "Starting..." : "Select mentor"}
                        {selectingId !== persona.id && <Icon name="arrow_forward" size={18} />}
                      </button>
                    </div>
                  </article>
                );
              })}
        </div>

        <div className="mt-10 flex items-start gap-4 rounded-2xl border border-outline-variant bg-surface-container-low p-5">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gold-mist text-sunburst-gold"><Icon name="verified_user" /></span>
          <div>
            <p className="font-label-sm text-[15px] font-bold text-on-surface">Your data stays yours</p>
            <p className="mt-1 font-body-md text-[14px] leading-5 text-on-surface-variant">Mentors work from what you tell them and from vetted trade guidance. You can change mentors at any time as your needs evolve.</p>
          </div>
        </div>
      </main>
    </div>
  );
}
