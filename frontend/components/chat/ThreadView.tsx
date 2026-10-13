"use client";

import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { img } from "@/lib/stitchImages";
import { stripThinkTags } from "@/lib/api";
import { ACCENT_BG, ACCENT_RING, ACCENT_TEXT, type MentorMeta } from "@/lib/mentors";
import type { ChatMessage } from "@/lib/types";
import { MentorMessageContent, formatTime } from "./Message";
import type { ChatController } from "./useChatController";

const BOOKMARK_KEY = "afrimentor-bookmarked-messages";
function readBookmarks(): string[] {
  try { return JSON.parse(window.localStorage.getItem(BOOKMARK_KEY) || "[]"); } catch { return []; }
}

function dayLabel(iso: string) {
  const d = new Date(iso);
  const today = new Date();
  const y = new Date(); y.setDate(today.getDate() - 1);
  if (d.toDateString() === today.toDateString()) return "Today";
  if (d.toDateString() === y.toDateString()) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
}

const firstName = (n: string) => n.split(" ").filter((w) => w !== "Alhaji")[0] || n;

function AiPill({ children = "AI" }: { children?: React.ReactNode }) {
  return <span className="rounded-full bg-indigo-mist px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-secondary">{children}</span>;
}

/* ---------------------------------------------------------------- header */

export function ThreadHeader({
  mentor, name, ctrl, variant, onBack, onTogglePanel, panelOpen,
}: { mentor: MentorMeta; name: string; ctrl: ChatController; variant: "web" | "mobile"; onBack?: () => void; onTogglePanel?: () => void; panelOpen?: boolean }) {
  const speaking = Boolean(ctrl.playingAudioMessageId);
  const lastMentor = [...ctrl.chatMessages].reverse().find((m) => m.sender === "mentor");
  const listen = () => {
    if (speaking) ctrl.stopSpeaking();
    else if (lastMentor) ctrl.handlePlayTTS(lastMentor.id, lastMentor.content);
  };

  if (variant === "mobile") {
    return (
      <header className="sticky top-0 z-40 flex w-full items-center justify-between bg-warm-white/90 px-margin pb-3 pt-[max(env(safe-area-inset-top),0.75rem)] shadow-sm backdrop-blur-md">
        <div className="flex min-w-0 items-center gap-space-sm">
          <button type="button" onClick={onBack} aria-label="Back to conversations" className="flex h-10 w-10 items-center justify-center rounded-full text-on-surface transition-colors hover:bg-surface-container active:scale-95">
            <span className="material-symbols-outlined text-[24px]">arrow_back</span>
          </button>
          <div className="relative shrink-0">
            <div className={`flex h-10 w-10 items-center justify-center rounded-full p-[2px] shadow-sm ${ACCENT_BG[mentor.accent]}`}>
              <img src={img(mentor.avatar)} alt={name} className="h-full w-full rounded-full object-cover" />
            </div>
            <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full bg-persona-trader shadow-[0_0_0_2px_rgb(var(--c-warm-white))]" />
          </div>
          <div className="flex min-w-0 flex-col">
            <div className="flex items-center gap-1.5">
              <h2 className="truncate font-title-md text-body-md font-semibold leading-tight tracking-tight text-on-surface">{name}</h2>
              <span className="material-symbols-outlined icon-fill text-[16px] text-sunburst-gold">verified</span>
            </div>
            <p className="truncate font-caption text-caption leading-none text-outline">{mentor.role} · AI mentor</p>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button type="button" onClick={listen} disabled={!lastMentor && !speaking} aria-label={speaking ? "Stop audio reply" : "Listen to the latest reply"} className="flex h-9 w-9 items-center justify-center rounded-full text-on-surface-variant transition-colors hover:bg-surface-container disabled:opacity-40">
            <span className="material-symbols-outlined text-[20px]">{speaking ? "stop_circle" : "volume_up"}</span>
          </button>
        </div>
      </header>
    );
  }

  return (
    <header className="sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between border-b border-outline-subtle bg-warm-white/90 px-4 shadow-[0_1px_4px_rgba(20,17,13,0.02)] backdrop-blur-md lg:px-8">
      <div className="flex min-w-0 items-center gap-3.5">
        {!panelOpen && onTogglePanel && (
          <button type="button" onClick={onTogglePanel} aria-label="Show conversations" title="Show conversations" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-high hover:text-on-surface">
            <span className="material-symbols-outlined text-[22px]">menu</span>
          </button>
        )}
        <div className="relative shrink-0">
          <img src={img(mentor.avatar)} alt={name} className={`h-10 w-10 rounded-full object-cover shadow-sm ring-2 ${ACCENT_RING[mentor.accent]}`} />
          <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-warm-white bg-persona-trader" />
        </div>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="truncate font-title-md text-[18px] font-bold leading-none text-on-surface">{name}</h1>
            <AiPill />
          </div>
          <p className="mt-0.5 flex items-center gap-1.5 font-caption text-caption text-on-surface-variant">
            <span className="truncate">{mentor.role}</span>
            <span className="h-1 w-1 shrink-0 rounded-full bg-outline-strong" />
            <span className="hidden truncate font-medium text-primary sm:inline">{mentor.domain}</span>
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {speaking && <span className="hidden animate-pulse items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-[11px] font-semibold text-primary sm:flex">Speaking…</span>}
        <button type="button" onClick={listen} disabled={!lastMentor && !speaking} className="flex h-9 items-center gap-2 rounded-full bg-surface-default px-3.5 font-label-sm text-[12px] text-on-surface transition-colors hover:bg-surface-high disabled:opacity-50">
          <span className="material-symbols-outlined text-[18px] text-primary">{speaking ? "stop_circle" : "volume_up"}</span>
          <span className="font-semibold">{speaking ? "Stop" : "Listen"}</span>
        </button>
      </div>
    </header>
  );
}

/* --------------------------------------------------------------- composer */

export function Composer({ ctrl, name, variant }: { ctrl: ChatController; mentor?: MentorMeta; name: string; variant: "dock" | "hero" | "mobile" }) {
  const { isRecording, isTranscribing, chatDraft, isTyping, streamingContent, dispatch } = ctrl;
  const first = firstName(name);
  const busy = isTyping || streamingContent !== null;
  const canSend = Boolean(chatDraft.trim()) && !busy && !isRecording && !isTranscribing;
  const mm = String(Math.floor(ctrl.recordSeconds / 60)).padStart(2, "0");
  const ss = String(ctrl.recordSeconds % 60).padStart(2, "0");

  const shell =
    variant === "hero"
      ? "w-full rounded-[28px] bg-paper p-2 pl-5 shadow-[0_16px_48px_rgba(20,17,13,0.10)] transition-all focus-within:ring-2 focus-within:ring-primary"
      : variant === "mobile"
      ? "w-full rounded-[28px] bg-paper px-2 py-1.5 shadow-[0_12px_40px_rgba(20,17,13,0.10)] transition-all focus-within:ring-2 focus-within:ring-sunburst-gold"
      : "pointer-events-auto w-full max-w-[760px] rounded-[28px] border border-outline-subtle bg-paper p-2 pl-3 shadow-[0_16px_48px_rgba(20,17,13,0.10)] transition-all duration-200 focus-within:ring-2 focus-within:ring-sunburst-gold";
  const sendCls =
    variant === "mobile"
      ? "bg-gradient-to-br from-sunburst-gold to-persona-rural-hustler text-on-surface shadow-[0_3px_0_#9A6B00] active:translate-y-1 active:shadow-none"
      : "bg-gradient-to-br from-persona-trader to-sunburst-gold text-white shadow-md hover:brightness-105 active:scale-95";

  return (
    <div className={shell}>
      {isRecording ? (
        <div className="flex items-center gap-3 px-2 py-1" role="status">
          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-tertiary" />
          <span className="font-mono text-[13px] font-semibold text-on-surface">{mm}:{ss}</span>
          <span className="flex-1 truncate font-body-md text-label-sm text-on-surface-variant">Listening… tap when done</span>
          <button type="button" onClick={ctrl.cancelRecording} aria-label="Cancel recording" className="flex h-9 w-9 items-center justify-center rounded-full text-outline-strong transition-colors hover:bg-surface-default hover:text-on-surface">
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
          <button type="button" onClick={ctrl.toggleVoiceRecording} aria-label="Stop recording and send" className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-all ${sendCls}`}>
            <span className="material-symbols-outlined text-[20px]">arrow_upward</span>
          </button>
        </div>
      ) : (
        <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (canSend) ctrl.send(); }}>
          <button type="button" title="Attach a file" aria-label="Attach a file" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-outline-strong transition-colors hover:bg-surface-default hover:text-on-surface">
            <span className="material-symbols-outlined text-[20px]">attach_file</span>
          </button>
          <input
            value={chatDraft}
            onChange={(e) => dispatch({ type: "SET_CHAT_DRAFT", draft: e.target.value })}
            aria-label={`Message ${first}`}
            disabled={isTranscribing}
            placeholder={isTranscribing ? "Transcribing your voice note…" : variant === "mobile" ? `Message ${first}…` : `Message ${first}… (e.g. How do I plan next month’s stock?)`}
            className="min-w-0 flex-1 bg-transparent py-2 pr-2 font-body-md text-body-md text-on-surface placeholder:text-outline-strong focus:outline-none"
          />
          <button type="button" onClick={ctrl.toggleVoiceRecording} disabled={isTranscribing} title="Answer with your voice" aria-label={isTranscribing ? "Transcribing voice note" : "Record a voice note"} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-outline-strong transition-colors hover:bg-surface-default hover:text-primary disabled:opacity-50">
            <span className="material-symbols-outlined text-[22px]">{isTranscribing ? "hourglass_empty" : "mic"}</span>
          </button>
          <button type="submit" disabled={!canSend} title="Send message" aria-label={`Send message to ${first}`} className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-all disabled:opacity-40 ${sendCls}`}>
            <span className="material-symbols-outlined text-[20px]">arrow_upward</span>
          </button>
        </form>
      )}
    </div>
  );
}

const DISCLAIMER = "AI mentor · not formal financial advice · grounded in communal African enterprise wisdom";

/* --------------------------------------------------------------- messages */

function UserBubble({ m, variant }: { m: ChatMessage; variant: "web" | "mobile" }) {
  return (
    <div className="flex w-full justify-end">
      <div className="flex max-w-[85%] flex-col items-end md:max-w-[72%]">
        <div className={`whitespace-pre-line rounded-[20px] rounded-br-[6px] px-5 py-4 font-body-md text-body-md leading-relaxed text-on-primary shadow-sm selection:bg-sunburst-gold selection:text-midnight-bg ${variant === "mobile" ? "bg-primary px-4 py-3" : "bg-primary-container"}`}>
          {m.content}
        </div>
        <div className="mt-1.5 flex items-center gap-1.5 pr-1 font-caption text-[11px] text-on-surface-variant">
          <span>{formatTime(m.created_at)}</span>
          <span className="material-symbols-outlined icon-fill text-[14px] text-primary">done_all</span>
        </div>
      </div>
    </div>
  );
}

function MentorMessage({
  m, mentor, name, ctrl, onCitation, bookmarked, onBookmark,
}: { m: ChatMessage; mentor: MentorMeta; name: string; ctrl: ChatController; onCitation: (label: string, ctx: string) => void; bookmarked: boolean; onBookmark: () => void }) {
  const first = firstName(name);
  const playing = ctrl.playingAudioMessageId === m.id;
  const [copied, setCopied] = useState(false);
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  const cite = m.citations && m.citations.length > 0 ? m.citations[0] : null;

  async function copy() {
    try {
      await navigator.clipboard.writeText(stripThinkTags(m.content));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard unavailable */ }
  }

  return (
    <article className="flex w-full flex-col space-y-4 pt-2">
      <div className="flex items-center justify-between pb-1">
        <div className="flex items-center gap-2.5">
          <img src={img(mentor.avatar)} alt={name} className={`h-8 w-8 rounded-full object-cover ring-2 ${ACCENT_RING[mentor.accent]}`} />
          <span className="font-label-sm text-label-sm font-bold text-primary">{name}</span>
          <span className="rounded bg-gold-mist px-1.5 py-[1px] font-caption text-[10px] font-bold text-gold-pressed-shadow">{mentor.role.replace("The ", "")}</span>
        </div>
        <span className="font-caption text-[12px] text-outline-strong">{formatTime(m.created_at)}</span>
      </div>

      <MentorMessageContent content={m.content} />

      {cite && (
        <div className="pt-1">
          <button type="button" onClick={() => onCitation(cite.label, m.content)} title="View the verified source" className="inline-flex max-w-full items-center gap-2 rounded-full bg-indigo-mist px-3.5 py-1.5 text-left font-caption text-caption font-semibold text-secondary transition-colors hover:bg-secondary-fixed">
            <span className="material-symbols-outlined text-[16px]">menu_book</span>
            <span className="truncate">Sourced from {cite.label}</span>
            <span className="material-symbols-outlined text-[14px]">north_east</span>
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-outline-subtle/70 pt-2">
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => ctrl.handlePlayTTS(m.id, m.content)} aria-label={playing ? "Stop voice playback" : `Listen to ${first}`} className="flex h-8 items-center gap-1.5 rounded-full bg-surface-default px-3 font-caption text-[12px] font-semibold text-on-surface transition-colors hover:bg-surface-high">
            <span className="material-symbols-outlined text-[16px] text-primary">{playing ? "stop" : "play_arrow"}</span>
            <span>{playing ? "Stop" : `Listen to ${first}`}</span>
            {playing && <span className="flex h-3 items-end gap-[2px]" aria-hidden>{[0, 1, 2, 3].map((i) => <span key={i} className="w-[3px] animate-pulse rounded-full bg-primary" style={{ height: `${6 + ((i * 5) % 8)}px`, animationDelay: `${i * 0.12}s` }} />)}</span>}
          </button>
          <button type="button" onClick={copy} title="Copy advice" aria-label="Copy advice" className="flex h-8 w-8 items-center justify-center rounded-full text-outline-strong transition-colors hover:bg-surface-default hover:text-on-surface">
            <span className="material-symbols-outlined text-[18px]">{copied ? "check" : "content_copy"}</span>
          </button>
          <button type="button" onClick={onBookmark} aria-pressed={bookmarked} title={bookmarked ? "Saved on this device" : "Save this advice"} aria-label="Save this advice" className={`flex h-8 w-8 items-center justify-center rounded-full transition-colors hover:bg-surface-default ${bookmarked ? "text-sunburst-gold" : "text-outline-strong hover:text-on-surface"}`}>
            <span className={`material-symbols-outlined text-[18px] ${bookmarked ? "icon-fill" : ""}`}>{bookmarked ? "bookmark" : "bookmark_border"}</span>
          </button>
        </div>
        <div className="flex items-center gap-1">
          <span className="mr-1 hidden font-caption text-[11px] text-outline-strong sm:inline">Was this sound counsel?</span>
          <button type="button" onClick={() => setVote(vote === "up" ? null : "up")} aria-pressed={vote === "up"} title="Helpful" aria-label="Helpful" className={`flex h-7 w-7 items-center justify-center rounded-full transition-colors hover:bg-gold-mist/40 ${vote === "up" ? "text-sunburst-gold" : "text-outline-strong hover:text-sunburst-gold"}`}>
            <span className={`material-symbols-outlined text-[16px] ${vote === "up" ? "icon-fill" : ""}`}>thumb_up</span>
          </button>
          <button type="button" onClick={() => setVote(vote === "down" ? null : "down")} aria-pressed={vote === "down"} title="Not relevant" aria-label="Not relevant" className={`flex h-7 w-7 items-center justify-center rounded-full transition-colors hover:bg-surface-default ${vote === "down" ? "text-on-surface" : "text-outline-strong hover:text-on-surface"}`}>
            <span className={`material-symbols-outlined text-[16px] ${vote === "down" ? "icon-fill" : ""}`}>thumb_down</span>
          </button>
        </div>
      </div>
    </article>
  );
}

function Thinking({ first }: { first: string }) {
  return (
    <div className="flex w-fit items-center gap-3 rounded-xl border border-outline-subtle bg-surface-low px-4 py-3" role="status" aria-live="polite">
      <div className="relative flex h-5 w-5 items-center justify-center">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sunburst-gold/40 opacity-75" />
        <span className="relative inline-flex h-3 w-3 rounded-full bg-gradient-to-tr from-persona-trader to-sunburst-gold" />
      </div>
      <span className="font-caption text-caption font-semibold text-on-surface">{first} is thinking…</span>
    </div>
  );
}

function CommitmentCallout({ ctrl }: { ctrl: ChatController }) {
  const { goalPickerGoals, newGoalInput, setNewGoalInput } = ctrl;
  return (
    <div className="relative overflow-hidden rounded-2xl border border-outline-subtle bg-paper p-5 pl-6 shadow-sm">
      <div className="absolute inset-y-0 left-0 w-[4px] bg-sunburst-gold" />
      {goalPickerGoals ? (
        <div className="flex flex-col gap-2.5">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[18px] text-sunburst-gold">flag</span>
            <span className="font-eyebrow text-eyebrow uppercase tracking-widest text-outline-strong">Goal architecture</span>
          </div>
          <p className="font-quote text-[20px] italic text-on-surface">Which goal should this go under?</p>
          {goalPickerGoals.map((g) => (
            <button key={g.id} type="button" onClick={() => ctrl.confirmTagWithGoal(g.id)} className="rounded-full bg-surface-default px-4 py-2.5 text-left font-label-sm text-label-sm font-semibold text-on-surface transition-colors hover:bg-primary hover:text-on-primary">{g.title}</button>
          ))}
          {newGoalInput === "" ? (
            <button type="button" onClick={() => setNewGoalInput(" ")} className="flex items-center gap-2 rounded-full border border-dashed border-outline-strong px-4 py-2.5 text-left font-label-sm text-label-sm text-on-surface-variant transition-colors hover:bg-surface-default">
              <span className="material-symbols-outlined text-[18px]">add_circle</span>New goal
            </button>
          ) : (
            <form className="flex items-center gap-2" onSubmit={async (e) => {
              e.preventDefault();
              const title = newGoalInput.trim();
              if (!title) return;
              const { createGoal } = await import("@/lib/api");
              const created = await createGoal({ title });
              await ctrl.confirmTagWithGoal(created.id);
            }}>
              <input autoFocus value={newGoalInput.trimStart()} onChange={(e) => setNewGoalInput(e.target.value)} placeholder="Goal name…" className="min-w-0 flex-1 rounded-full border border-outline-subtle bg-surface-low px-4 py-2.5 font-label-sm text-label-sm text-on-surface placeholder:text-outline-strong focus:border-primary focus:outline-none" />
              <button type="submit" disabled={!newGoalInput.trim()} className="rounded-full bg-primary px-4 py-2.5 font-label-sm text-label-sm font-semibold text-on-primary disabled:opacity-40">Create</button>
            </form>
          )}
          <button type="button" onClick={() => ctrl.setGoalPickerGoals(null)} className="self-start font-label-sm text-label-sm text-outline-strong hover:text-on-surface">Cancel</button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined icon-fill text-[18px] text-sunburst-gold">lightbulb</span>
            <span className="font-eyebrow text-eyebrow font-bold uppercase tracking-widest text-sunburst-gold">Worth committing to</span>
          </div>
          <p className="font-quote text-[20px] italic leading-snug text-on-surface">Tag this advice as a commitment?</p>
          <div>
            <button type="button" onClick={ctrl.handleTagCommitment} className="rounded-full bg-primary px-5 py-2 font-label-sm text-label-sm font-semibold text-on-primary shadow-sm transition-all hover:bg-primary-container active:scale-95">Yes, tag it</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- thread */

export function ThreadBody({
  ctrl, mentor, name, variant, onCitation,
}: { ctrl: ChatController; mentor: MentorMeta; name: string; variant: "web" | "mobile"; onCitation: (label: string, ctx: string) => void }) {
  const { chatMessages, isTyping, streamingContent } = ctrl;
  const scrollRef = useRef<HTMLDivElement>(null);
  const [atBottom, setAtBottom] = useState(true);
  const [bookmarks, setBookmarks] = useState<string[]>([]);
  const first = firstName(name);
  const hero = chatMessages.length === 0 && !isTyping && streamingContent === null;

  useEffect(() => { setBookmarks(readBookmarks()); }, []);
  function toggleBookmark(id: string) {
    setBookmarks((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      try { window.localStorage.setItem(BOOKMARK_KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  }

  const scrollToLatest = useCallback((smooth = true) => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  }, []);

  useEffect(() => { if (atBottom) scrollToLatest(chatMessages.length > 1); }, [chatMessages.length, streamingContent, isTyping]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { scrollToLatest(false); }, [ctrl.chatSessionId, scrollToLatest]);

  function onScroll() {
    const el = scrollRef.current;
    if (!el) return;
    setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 120);
  }

  const lastDay = useRef("");
  lastDay.current = "";

  if (hero) {
    return (
      <div ref={scrollRef} className="flex flex-1 justify-center overflow-y-auto px-4 py-8">
        <div className="flex min-h-full w-full max-w-[760px] flex-col justify-center">
          <div className="flex animate-rise flex-col items-center text-center">
            <div className="relative mb-6">
              <div className="flex h-[94px] w-[94px] items-center justify-center rounded-full bg-gradient-to-br from-persona-trader via-sunburst-gold to-persona-market-queen p-[3px] shadow-lg">
                <img src={img(mentor.portrait)} alt={name} className="h-full w-full rounded-full bg-paper object-cover" />
              </div>
              <span className="absolute -bottom-2 right-1/2 translate-x-1/2 whitespace-nowrap rounded-full bg-indigo-mist px-2.5 py-0.5 font-caption text-[11px] font-bold text-secondary shadow-sm">AI MENTOR</span>
            </div>
            <h1 className="mb-3 max-w-[620px] font-headline-lg text-headline-lg-mobile text-on-surface md:text-headline-lg">“{mentor.welcome}”</h1>
            <p className="mb-8 max-w-[540px] font-body-md text-body-md leading-relaxed text-on-surface-variant">
              {first} draws on {mentor.focus.replace(/ • /g, ", ")} and verified African enterprise research.
            </p>
            <Composer ctrl={ctrl} mentor={mentor} name={name} variant="hero" />
            <div className="mt-3 flex items-center gap-2 font-caption text-caption text-outline-strong">
              <span className="material-symbols-outlined text-[14px]">shield</span><span>{DISCLAIMER}</span>
            </div>
            <div className="mt-8 flex w-full flex-col items-center">
              <span className="mb-3 font-eyebrow text-eyebrow uppercase tracking-widest text-outline-strong">Common questions for {first}</span>
              <div className="flex max-w-[680px] flex-wrap items-center justify-center gap-2.5">
                {mentor.starters.map((s) => (
                  <button key={s} type="button" onClick={() => ctrl.send(s.replace(/^\S+\s/, ""))} className="flex items-center gap-2 rounded-full bg-surface-default px-4 py-2.5 font-body-md text-[14px] text-on-surface shadow-sm transition-all hover:-translate-y-0.5 hover:bg-surface-high">
                    <span>{s}</span><span className="material-symbols-outlined text-[16px] text-outline">north_east</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div ref={scrollRef} onScroll={onScroll} role="log" aria-label={`Conversation with ${name}`} className="flex-1 overflow-y-auto px-margin py-8 md:px-6">
        <div className="mx-auto flex max-w-[760px] flex-col space-y-7">
          {chatMessages.map((m, i) => {
            const label = dayLabel(m.created_at);
            const showDay = i === 0 || dayLabel(chatMessages[i - 1].created_at) !== label;
            return (
              <Fragment key={m.id}>
                {showDay && (
                  <div className="flex justify-center">
                    <span className="rounded-full bg-surface-default px-3.5 py-1 font-caption text-caption font-semibold tracking-wide text-on-surface-variant shadow-xs">{label}</span>
                  </div>
                )}
                {m.sender === "user" ? (
                  <UserBubble m={m} variant={variant} />
                ) : (
                  <MentorMessage m={m} mentor={mentor} name={name} ctrl={ctrl} onCitation={onCitation} bookmarked={bookmarks.includes(m.id)} onBookmark={() => toggleBookmark(m.id)} />
                )}
              </Fragment>
            );
          })}

          {(isTyping || (streamingContent !== null && !stripThinkTags(streamingContent))) && <Thinking first={first} />}

          {streamingContent !== null && Boolean(stripThinkTags(streamingContent)) && (
            <article className="flex w-full flex-col space-y-4 pt-2">
              <div className="flex items-center gap-2.5">
                <img src={img(mentor.avatar)} alt={name} className={`h-8 w-8 rounded-full object-cover ring-2 ${ACCENT_RING[mentor.accent]}`} />
                <span className="font-label-sm text-label-sm font-bold text-primary">{name}</span>
              </div>
              <div>
                <MentorMessageContent content={streamingContent} />
                <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-primary align-middle" aria-hidden />
              </div>
            </article>
          )}

          {ctrl.showCommitmentPrompt && !isTyping && streamingContent === null && <CommitmentCallout ctrl={ctrl} />}

          {ctrl.sendError && (
            <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-tertiary/30 bg-tertiary-fixed/50 px-4 py-3">
              <div className="flex items-center gap-2 font-caption text-caption text-on-surface">
                <span className="material-symbols-outlined text-[18px] text-tertiary">error</span>{ctrl.sendError}
              </div>
              <div className="flex items-center gap-1">
                <button type="button" onClick={ctrl.retryLast} className="flex items-center gap-1 rounded-full px-3 py-1 font-label-sm text-label-sm font-semibold text-tertiary transition-colors hover:bg-tertiary-fixed">
                  <span className="material-symbols-outlined text-[16px]">refresh</span>Retry
                </button>
                <button type="button" onClick={() => ctrl.setSendError(null)} aria-label="Dismiss" className="flex h-7 w-7 items-center justify-center rounded-full text-outline-strong hover:bg-surface-default">
                  <span className="material-symbols-outlined text-[16px]">close</span>
                </button>
              </div>
            </div>
          )}
          <div className="h-32" />
        </div>
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-40 flex flex-col items-center bg-gradient-to-t from-warm-white via-warm-white/95 to-transparent px-4 pb-[max(env(safe-area-inset-bottom),1.25rem)] pt-12 md:px-6">
        {!atBottom && (
          <button type="button" onClick={() => scrollToLatest()} aria-label="Scroll to latest message" className="pointer-events-auto mb-3 flex h-9 w-9 items-center justify-center rounded-full border border-outline-subtle bg-paper text-on-surface-variant shadow-md transition-all hover:-translate-y-0.5 hover:text-primary">
            <span className="material-symbols-outlined text-[20px]">arrow_downward</span>
          </button>
        )}
        <div className="pointer-events-auto w-full max-w-[760px]">
          <Composer ctrl={ctrl} mentor={mentor} name={name} variant={variant === "mobile" ? "mobile" : "dock"} />
        </div>
        <p className="mt-2.5 text-center font-caption text-[11px] tracking-wide text-outline-strong">{DISCLAIMER}</p>
      </div>
    </div>
  );
}

export function NothingSelected({ onStart, mentors }: { onStart: () => void; mentors: MentorMeta[] }) {
  return (
    <div className="flex flex-1 items-center justify-center overflow-y-auto px-4 py-8">
      <div className="flex w-full max-w-[620px] animate-rise flex-col items-center text-center">
        <div className="relative mb-6 flex h-36 w-36 items-center justify-center">
          <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-sunburst-gold/20 via-gold-mist/40 to-transparent blur-xl" />
          <div className="relative flex h-28 w-28 items-center justify-center rounded-full bg-paper shadow-lg">
            <span className="material-symbols-outlined icon-fill text-[56px] text-sunburst-gold">forum</span>
          </div>
        </div>
        <h2 className="mb-3 max-w-[580px] font-headline-lg text-headline-lg-mobile text-on-surface md:text-headline-lg">Select a conversation or start a new one</h2>
        <p className="mb-8 max-w-[500px] font-body-md text-body-md leading-relaxed text-on-surface-variant">Pick up an earlier conversation with one of your mentors, or start a fresh one about stock, cashflow, pricing or growth.</p>
        <button type="button" onClick={onStart} className="flex items-center gap-3 rounded-full bg-sunburst-gold px-8 py-4 font-label-sm text-[16px] font-bold text-on-surface shadow-[0_4px_0_0_#9A6B00] transition-all hover:translate-y-[2px] hover:shadow-[0_2px_0_0_#9A6B00] active:translate-y-[4px] active:shadow-none">
          <span className="material-symbols-outlined text-[22px]">auto_awesome</span><span>Start a new conversation</span>
        </button>
        <div className="mt-12 grid w-full max-w-[620px] grid-cols-2 gap-4 sm:grid-cols-4">
          {mentors.slice(0, 4).map((m) => (
            <div key={m.id} className="flex flex-col items-center rounded-2xl bg-paper p-3 text-center shadow-sm">
              <img src={img(m.avatar)} alt={m.name} className={`mb-2 h-12 w-12 rounded-full object-cover ring-2 ${ACCENT_RING[m.accent]}`} />
              <span className="font-label-sm text-[12px] font-bold text-on-surface">{m.name.split(" ").filter((w) => w !== "Alhaji")[0]}</span>
              <span className={`font-caption text-[10px] ${ACCENT_TEXT[m.accent]}`}>{m.domain}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
