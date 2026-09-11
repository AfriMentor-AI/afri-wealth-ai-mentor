"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";
import { updateGoal, deleteGoal } from "@/lib/api";
import type { Goal } from "@/lib/types";

interface EditGoalModalProps {
  goal: Goal | null;
  isOpen: boolean;
  onClose: () => void;
  onGoalUpdated: (updatedGoal: Goal) => void;
  onGoalDeleted?: (goalId: string) => void;
}

export function EditGoalModal({
  goal,
  isOpen,
  onClose,
  onGoalUpdated,
  onGoalDeleted,
}: EditGoalModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const titleInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isOpen || !goal) return;
    setTitle(goal.title || "");
    setDescription(goal.description || "");
    if (goal.deadline) {
      const d = new Date(goal.deadline);
      if (!isNaN(d.getTime())) {
        setDeadline(d.toISOString().split("T")[0]);
      } else {
        setDeadline("");
      }
    } else {
      setDeadline("");
    }
    setConfirmDelete(false);
    setError(null);

    setTimeout(() => {
      titleInputRef.current?.focus();
    }, 50);

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, goal]);

  if (!isOpen || !goal) return null;

  function handleClose() {
    if (saving || deleting) return;
    setConfirmDelete(false);
    onClose();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!goal) return;
    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setError("Please provide a goal title.");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const updated = await updateGoal(goal.id, {
        title: cleanTitle,
        description: description.trim() || null,
        deadline: deadline || null,
      });

      onGoalUpdated(updated);
      handleClose();
    } catch (err: unknown) {
      console.warn("updateGoal error:", err);
      setError("Failed to update goal. Please check your connection and try again.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!goal) return;
    setDeleting(true);
    setError(null);

    try {
      await deleteGoal(goal.id);
      if (onGoalDeleted) {
        onGoalDeleted(goal.id);
      }
      handleClose();
    } catch (err: unknown) {
      console.warn("deleteGoal error:", err);
      setError("Failed to delete goal. Please check your connection and try again.");
      setDeleting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 p-md backdrop-blur-sm animate-in fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-goal-title"
    >
      <div className="w-full max-w-lg rounded-2xl border border-outline-variant bg-surface p-lg shadow-2xl sm:p-xl animate-in zoom-in-95">
        <div className="mb-md flex items-center justify-between border-b border-outline-variant/40 pb-sm">
          <div className="flex items-center gap-sm">
            <span className="flex h-10 w-10 items-center justify-center rounded-full bg-secondary-container text-on-secondary-container">
              <Icon name="edit" size={22} />
            </span>
            <div>
              <h2 id="edit-goal-title" className="font-title-md text-title-md text-on-surface">
                Edit Goal
              </h2>
              <p className="text-xs text-on-surface-variant">
                Modify your aspiration and milestone target date
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleClose}
            disabled={saving || deleting}
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
              placeholder="e.g., Expand Poultry Capacity"
              className="w-full rounded-lg border border-outline-variant bg-surface-container-low px-md py-sm text-sm text-on-surface outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary"
              disabled={saving || deleting}
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
              placeholder="Add details, notes, or business strategy..."
              rows={3}
              className="w-full rounded-lg border border-outline-variant bg-surface-container-low p-md text-sm text-on-surface outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary"
              disabled={saving || deleting}
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
              disabled={saving || deleting}
            />
          </div>

          {/* Delete Danger Zone */}
          <div className="rounded-xl border border-error/20 bg-error-container/10 p-md">
            {!confirmDelete ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-bold text-error">Danger Zone</p>
                  <p className="text-[11px] text-on-surface-variant">
                    Delete this goal and its associated milestones
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setConfirmDelete(true)}
                  disabled={saving || deleting}
                  className="rounded-full border border-error/40 px-md py-xs text-xs font-bold text-error hover:bg-error/10 active:scale-95 disabled:opacity-50"
                >
                  Delete Goal
                </button>
              </div>
            ) : (
              <div className="space-y-sm">
                <p className="text-xs font-bold text-error">
                  Are you sure you want to delete this goal?
                </p>
                <p className="text-[11px] text-on-surface-variant">
                  This action cannot be undone and will remove all linked milestones.
                </p>
                <div className="flex gap-sm">
                  <button
                    type="button"
                    onClick={handleDelete}
                    disabled={deleting}
                    className="rounded-full bg-error px-md py-xs text-xs font-bold text-on-error hover:opacity-90 active:scale-95 disabled:opacity-50"
                  >
                    {deleting ? "Deleting..." : "Yes, Delete"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(false)}
                    disabled={deleting}
                    className="rounded-full border border-outline-variant px-md py-xs text-xs font-medium text-on-surface hover:bg-surface-variant disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="mt-lg flex flex-col-reverse gap-sm pt-sm sm:flex-row sm:justify-end sm:gap-md border-t border-outline-variant/30">
            <button
              type="button"
              onClick={handleClose}
              disabled={saving || deleting}
              className="rounded-full px-lg py-md text-center font-bold text-on-surface-variant transition-all hover:bg-surface-variant disabled:opacity-50 text-sm"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || deleting || !title.trim()}
              className="flex items-center justify-center gap-sm rounded-full bg-primary px-lg py-md font-bold text-on-primary shadow-sm transition-all hover:opacity-90 active:scale-95 disabled:opacity-50 text-sm"
            >
              {saving ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-on-primary border-t-transparent" />
                  <span>Saving...</span>
                </>
              ) : (
                <>
                  <Icon name="check" size={18} />
                  <span>Save Changes</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
