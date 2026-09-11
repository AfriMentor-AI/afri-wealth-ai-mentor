"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "./Icon";
import { useAppDispatch, useAppState } from "@/lib/store";
import { createGoal } from "@/lib/api";

export function CreateGoalModal() {
  const { newGoalModalOpen } = useAppState();
  const dispatch = useAppDispatch();
  const router = useRouter();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const titleInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!newGoalModalOpen) return;
    setTitle("");
    setDescription("");
    setDeadline("");
    setError(null);
    setTimeout(() => {
      titleInputRef.current?.focus();
    }, 50);

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [newGoalModalOpen]);

  if (!newGoalModalOpen) return null;

  function close() {
    if (creating) return;
    dispatch({ type: "CLOSE_NEW_GOAL_MODAL" });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setError("Please enter a goal title.");
      return;
    }

    setCreating(true);
    setError(null);

    try {
      const created = await createGoal({
        title: cleanTitle,
        description: description.trim() || undefined,
        deadline: deadline || undefined,
      });

      dispatch({ type: "SET_ACTIVE_GOAL_ID", goalId: created.id });
      dispatch({ type: "CLOSE_NEW_GOAL_MODAL" });

      // Signal goals page to refresh if currently mounted
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("goal-created", { detail: created }));
      }

      router.push("/goals");
    } catch (err: unknown) {
      console.warn("createGoal error:", err);
      setError("Failed to create goal. Please check your connection and try again.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 p-md backdrop-blur-sm animate-in fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-goal-title"
    >
      <div className="w-full max-w-lg rounded-2xl border border-outline-variant bg-surface p-lg shadow-2xl sm:p-xl animate-in zoom-in-95">
        <div className="mb-md flex items-center justify-between border-b border-outline-variant/40 pb-sm">
          <div className="flex items-center gap-sm">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary-container text-on-primary-container">
              <Icon name="flag" size={22} />
            </span>
            <div>
              <h2 id="create-goal-title" className="font-title-md text-title-md text-primary">
                Define New Purpose
              </h2>
              <p className="text-xs text-on-surface-variant">
                Set an aspirational milestone for your enterprise growth
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={close}
            disabled={creating}
            aria-label="Close modal"
            className="tap-target rounded-full p-xs text-on-surface-variant transition-colors hover:bg-surface-variant disabled:opacity-50"
          >
            <Icon name="close" size={20} />
          </button>
        </div>

        {error && (
          <div className="mb-md rounded-lg bg-error/10 p-sm text-xs font-semibold text-error">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-md">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-1">
              Goal Title <span className="text-error">*</span>
            </label>
            <input
              ref={titleInputRef}
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g., Expand Poultry Capacity to 500 Birds"
              className="w-full rounded-lg border border-outline-variant bg-surface-container-low px-md py-sm text-sm text-on-surface outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary"
              disabled={creating}
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-1">
              Description / Strategy <span className="text-[10px] lowercase font-normal text-on-surface-variant">(optional)</span>
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g., Save ₵300 weekly from feed margins and acquire two solar-powered incubators."
              rows={3}
              className="w-full rounded-lg border border-outline-variant bg-surface-container-low p-md text-sm text-on-surface outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary"
              disabled={creating}
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-1">
              Target Completion Date <span className="text-[10px] lowercase font-normal text-on-surface-variant">(optional)</span>
            </label>
            <input
              type="date"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="w-full rounded-lg border border-outline-variant bg-surface-container-low px-md py-sm text-sm text-on-surface outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary"
              disabled={creating}
            />
          </div>

          <div className="mt-lg flex flex-col-reverse gap-sm pt-sm sm:flex-row sm:justify-end sm:gap-md border-t border-outline-variant/30">
            <button
              type="button"
              onClick={close}
              disabled={creating}
              className="rounded-full px-lg py-md text-center font-bold text-on-surface-variant transition-all hover:bg-surface-variant disabled:opacity-50 text-sm"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={creating || !title.trim()}
              className="flex items-center justify-center gap-sm rounded-full bg-primary px-lg py-md font-bold text-on-primary shadow-sm transition-all hover:opacity-90 active:scale-95 disabled:opacity-50 text-sm"
            >
              {creating ? (
                <>
                  <Icon name="sync" size={18} className="animate-spin" />
                  Creating Goal...
                </>
              ) : (
                <>
                  <Icon name="add" size={18} />
                  Create Goal
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
