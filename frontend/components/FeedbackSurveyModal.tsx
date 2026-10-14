"use client";

import { useEffect, useRef, useState } from "react";
import { useAppDispatch, useAppState } from "@/lib/store";
import { submitFeedback } from "@/lib/api";
import { KenteStrip } from "./shell/AppSidebar";

/** "Enterprise Reflections" feedback dialog (W13/M10). Opened via OPEN_FEEDBACK_MODAL. */
export function FeedbackSurveyModal() {
  const { feedbackModalOpen } = useAppState();
  const dispatch = useAppDispatch();
  const [rating, setRating] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  function close() {
    dispatch({ type: "CLOSE_FEEDBACK_MODAL" });
    setSubmitted(false); setRating(null); setComment("");
  }

  useEffect(() => {
    if (!feedbackModalOpen) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feedbackModalOpen]);

  if (!feedbackModalOpen) return null;

  async function submit() {
    if (!rating) return;
    setSubmitting(true);
    await submitFeedback({ npsScore: rating, comment: comment.trim() || undefined });
    setSubmitting(false);
    setSubmitted(true);
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-end justify-center p-0 backdrop-blur-[6px] sm:items-center sm:p-4 bg-brand-ink/40" role="dialog" aria-modal="true" aria-labelledby="feedback-title" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
      <div className="relative flex max-h-[92vh] w-full max-w-[560px] animate-rise flex-col overflow-hidden rounded-t-[28px] bg-paper shadow-[0_24px_64px_rgba(20,17,13,0.22)] sm:rounded-[28px]">
        <div className="[&>div]:h-1.5"><KenteStrip /></div>
        <div className="flex flex-col gap-6 overflow-y-auto p-7 sm:p-8">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gold-mist text-sunburst-gold">
                <span className="material-symbols-outlined text-[18px]">temp_preferences_custom</span>
              </div>
              <span className="font-eyebrow text-eyebrow uppercase tracking-widest text-outline-strong">Enterprise reflections</span>
            </div>
            <button ref={closeRef} type="button" onClick={close} aria-label="Close feedback survey" className="flex h-8 w-8 items-center justify-center rounded-full text-outline-strong transition-colors hover:bg-surface-default hover:text-on-surface">
              <span className="material-symbols-outlined text-[20px]">close</span>
            </button>
          </div>

          {submitted ? (
            <div className="py-6 text-center">
              <span className="material-symbols-outlined icon-fill text-[44px] text-primary">check_circle</span>
              <h2 id="feedback-title" className="mt-3 font-title-md text-headline-lg-mobile font-medium text-on-surface">Thank you.</h2>
              <p className="mt-2 font-body-md text-label-sm text-on-surface-variant">Your reflections help your mentors give you sharper advice.</p>
              <button type="button" onClick={close} className="mt-6 h-11 rounded-full bg-primary px-8 font-label-sm text-label-sm font-semibold text-on-primary transition-all active:scale-95">Done</button>
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-2">
                <h2 id="feedback-title" className="font-title-md text-headline-lg-mobile font-medium leading-tight text-on-surface">How grounding has AfriMentor been for your enterprise?</h2>
                <p className="font-body-md text-label-sm text-on-surface-variant">Your feedback sharpens the counsel your mentors give you next.</p>
              </div>
              <div className="flex flex-col gap-2 pt-1">
                <div className="grid w-full grid-cols-10 gap-1.5 sm:gap-2" role="group" aria-label="Likelihood to recommend, 1 to 10">
                  {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                    <button key={n} type="button" aria-pressed={rating === n} onClick={() => setRating(n)}
                      className={`flex h-10 items-center justify-center rounded-xl font-label-sm text-caption transition-all ${rating === n ? "bg-primary font-bold text-on-primary shadow-sm ring-2 ring-primary-fixed" : "bg-surface-default text-on-surface hover:bg-surface-high"}`}>
                      {n}
                    </button>
                  ))}
                </div>
                <div className="mt-1 flex items-center justify-between px-0.5 font-caption text-caption text-outline-strong">
                  <span>Not likely</span>
                  <span className="font-semibold text-primary">{rating && rating >= 9 ? "Highly grounding" : ""}</span>
                  <span>Very likely</span>
                </div>
              </div>
              <div className="flex flex-col gap-2">
                <label htmlFor="feedback-comment" className="font-label-sm text-label-sm font-semibold text-on-surface">What advice or feature helped you most?</label>
                <div className="rounded-2xl bg-surface-low p-3.5 transition-all focus-within:bg-paper focus-within:shadow-md">
                  <textarea id="feedback-comment" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Tell us what worked, and what to improve." className="w-full resize-none border-none bg-transparent font-body-md text-label-sm text-on-surface outline-none placeholder:text-outline-strong" />
                </div>
              </div>
              <div className="flex items-center justify-between pt-2">
                <button type="button" onClick={close} className="rounded-full px-4 py-2 font-label-sm text-label-sm text-outline-strong transition-colors hover:text-on-surface">Dismiss</button>
                <button type="button" onClick={submit} disabled={!rating || submitting} className="flex h-11 items-center gap-2 rounded-full bg-primary px-8 font-label-sm text-label-sm font-semibold text-on-primary shadow-sm transition-all hover:bg-primary-container active:scale-95 disabled:opacity-40">
                  <span className="material-symbols-outlined text-[18px]">send</span>
                  <span>{submitting ? "Sending…" : "Submit reflections"}</span>
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
