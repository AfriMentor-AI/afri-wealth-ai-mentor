"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { Icon } from "./Icon";
import { useAppDispatch, useAppState } from "@/lib/store";
import { submitFeedback } from "@/lib/api";

export function FeedbackSurveyModal() {
  const { feedbackModalOpen } = useAppState();
  const dispatch = useAppDispatch();
  const [rating, setRating] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Move focus into the dialog on open so keyboard/SR users don't land back
  // on the page behind it, and close on Escape per the dialog pattern.
  useEffect(() => {
    if (!feedbackModalOpen) return;
    closeButtonRef.current?.focus();
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feedbackModalOpen]);

  if (!feedbackModalOpen) return null;

  function close() {
    dispatch({ type: "CLOSE_FEEDBACK_MODAL" });
    setSubmitted(false);
    setRating(null);
    setComment("");
  }

  async function submit() {
    if (!rating) return;
    setSubmitting(true);
    await submitFeedback({ npsScore: rating, comment: comment.trim() || undefined });
    setSubmitting(false);
    setSubmitted(true);
  }

  return (
    <div className="fixed inset-0 z-30 flex items-end justify-center bg-inverse-surface/40 md:items-center" role="dialog" aria-modal="true" aria-labelledby="feedback-title">
      <div className="mx-auto w-full max-w-[400px] rounded-t bg-surface shadow-2xl md:rounded">
        <div className="flex justify-center pb-xs pt-sm">
          <div className="h-1 w-10 rounded-full bg-outline-variant opacity-50" />
        </div>

        <div className="relative overflow-hidden px-margin-mobile pb-xl pt-sm">
          <header className="mb-lg">
            <div className="mb-xs flex items-start justify-between">
              <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded-full border-2 border-primary">
                <Image src="/images/chioma-avatar.png" alt="Chioma" fill className="object-cover" />
              </div>
              <button
                ref={closeButtonRef}
                onClick={close}
                aria-label="Close feedback survey"
                className="tap-target rounded-full p-xs text-on-surface-variant hover:bg-surface-variant"
              >
                <Icon name="close" />
              </button>
            </div>
            <h2 id="feedback-title" className="font-headline-lg-mobile text-headline-lg-mobile text-primary">
              How was your journey?
            </h2>
            <p className="mt-sm font-body-md text-on-surface-variant">
              Your feedback helps CHIOMA tailor your mentorship experience.
            </p>
          </header>

          {submitted ? (
            <div className="py-lg text-center">
              <Icon name="check_circle" filled size={40} className="mx-auto text-secondary" />
              <p className="mt-sm font-title-md text-title-md text-on-surface">Thanks for the feedback.</p>
              <p className="mt-xs font-body-md text-on-surface-variant">It helps CHIOMA tailor what comes next.</p>
              <button
                onClick={close}
                className="tap-target mt-lg h-12 w-full rounded-full bg-primary font-title-md text-title-md text-on-primary transition-transform active:scale-[0.98]"
              >
                Done
              </button>
            </div>
          ) : (
            <>
              <div className="mb-xl">
                <p className="mb-md font-label-sm text-label-sm text-on-surface">Likelihood to recommend AfriMentor AI</p>
                <div className="flex flex-wrap justify-between gap-2">
                  {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                    <button
                      key={n}
                      onClick={() => setRating(n)}
                      aria-pressed={rating === n}
                      className={`flex h-12 w-9 items-center justify-center rounded-lg border font-title-md text-on-surface-variant transition-all ${
                        rating === n
                          ? "border-2 border-primary bg-primary-container/10 text-primary"
                          : "border-outline-variant hover:border-primary hover:bg-primary-container/20"
                      }`}
                    >
                      {n}
                    </button>
                  ))}
                </div>
                <div className="mt-xs flex justify-between px-xs">
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Not likely</span>
                  <span className="font-label-sm text-label-sm text-on-surface-variant">Very likely</span>
                </div>
              </div>

              <div className="mb-xl">
                <label htmlFor="feedback-comment" className="mb-sm block font-label-sm text-label-sm text-on-surface">
                  Tell CHIOMA more...
                </label>
                <div className="relative">
                  <textarea
                    id="feedback-comment"
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    rows={3}
                    className="w-full resize-none rounded border border-outline-variant bg-surface-container-low p-md font-body-md text-on-surface outline-none placeholder:text-on-surface-variant focus:border-transparent focus:ring-2 focus:ring-primary"
                    placeholder="What did you value most about this goal?"
                  />
                  <button
                    aria-label="Answer with voice instead"
                    className="tap-target absolute bottom-3 right-3 flex items-center justify-center rounded-full border border-outline-variant bg-surface-container-high text-primary transition-transform active:scale-90 hover:bg-surface-variant"
                  >
                    <Icon name="mic" />
                  </button>
                </div>
              </div>

              <div className="flex flex-col gap-sm">
                <button
                  onClick={submit}
                  disabled={!rating || submitting}
                  className="tap-target h-12 w-full rounded-full bg-primary font-title-md text-title-md text-on-primary transition-all active:scale-[0.98] disabled:opacity-40"
                >
                  {submitting ? "Sending..." : "Submit Feedback"}
                </button>
                <button
                  onClick={close}
                  className="tap-target h-11 w-full rounded-full bg-transparent font-title-md text-title-md text-primary transition-all hover:bg-surface-variant active:scale-[0.98]"
                >
                  Dismiss
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
