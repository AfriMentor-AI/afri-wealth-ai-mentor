"use client";

import { useState } from "react";
import { Icon } from "@/components/Icon";
import type { Milestone } from "@/lib/types";

interface MilestoneRoadProps {
  milestones: Milestone[];
  onCompleteMilestone?: (milestoneId: string) => void;
  onUpdateMilestone?: (
    milestoneId: string,
    updates: { title?: string; status?: Milestone["status"] }
  ) => Promise<void>;
  onDeleteMilestone?: (milestoneId: string) => Promise<void>;
  onCreateMilestone?: (input: {
    title: string;
    status?: Milestone["status"];
  }) => Promise<void>;
}

const statusLabel: Record<Milestone["status"], string> = {
  done: "Done",
  in_progress: "Active (In Progress)",
  blocked: "Blocked",
  upcoming: "Upcoming",
};

const statusOptions: Milestone["status"][] = [
  "in_progress",
  "done",
  "blocked",
  "upcoming",
];

export function MilestoneRoad({
  milestones,
  onCompleteMilestone,
  onUpdateMilestone,
  onDeleteMilestone,
  onCreateMilestone,
}: MilestoneRoadProps) {
  // Editing state for existing milestone
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editStatus, setEditStatus] = useState<Milestone["status"]>("upcoming");
  const [savingEdit, setSavingEdit] = useState(false);

  // New milestone creation state
  const [isAdding, setIsAdding] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newStatus, setNewStatus] = useState<Milestone["status"]>("upcoming");
  const [addingLoading, setAddingLoading] = useState(false);

  function startEditing(m: Milestone) {
    setEditingId(m.id);
    setEditTitle(m.title);
    setEditStatus(m.status);
  }

  function cancelEditing() {
    setEditingId(null);
    setEditTitle("");
  }

  async function handleSaveEdit(milestoneId: string) {
    if (!onUpdateMilestone || !editTitle.trim()) return;
    setSavingEdit(true);
    try {
      await onUpdateMilestone(milestoneId, {
        title: editTitle.trim(),
        status: editStatus,
      });
      setEditingId(null);
    } finally {
      setSavingEdit(false);
    }
  }

  async function handleDelete(milestoneId: string) {
    if (!onDeleteMilestone) return;
    if (!confirm("Are you sure you want to remove this milestone step?")) return;
    await onDeleteMilestone(milestoneId);
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!onCreateMilestone || !newTitle.trim()) return;
    setAddingLoading(true);
    try {
      await onCreateMilestone({
        title: newTitle.trim(),
        status: newStatus,
      });
      setNewTitle("");
      setNewStatus("upcoming");
      setIsAdding(false);
    } finally {
      setAddingLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-md">
      <ol className="flex flex-col">
        {milestones.map((m, i) => {
          const isLast = i === milestones.length - 1 && !isAdding;
          const isActionable = m.status === "in_progress" && !!onCompleteMilestone;
          const isCurrentlyEditing = editingId === m.id;

          const nodeClasses =
            m.status === "done"
              ? "bg-secondary text-on-secondary border-2 border-secondary"
              : m.status === "in_progress"
                ? "bg-primary-container text-on-primary-container border-2 border-primary-container"
                : m.status === "blocked"
                  ? "bg-error-container text-on-error-container border-2 border-error"
                  : "bg-surface text-on-surface-variant border-2 border-outline-variant";

          return (
            <li key={m.id} className="relative flex gap-md pb-lg last:pb-0">
              {!isLast && (
                <span
                  aria-hidden
                  className={`absolute left-[19px] top-10 h-full w-0.5 ${
                    m.status === "done"
                      ? "bg-secondary"
                      : "border-l-2 border-dashed border-outline-variant"
                  }`}
                />
              )}

              <div
                className={`z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-headline-lg-mobile text-[16px] ${nodeClasses}`}
              >
                {m.status === "done" ? "✓" : m.status === "blocked" ? "!" : i + 1}
              </div>

              <div className="flex flex-1 flex-col pt-1">
                {isCurrentlyEditing ? (
                  <div className="flex flex-col gap-sm rounded-xl border border-primary/40 bg-surface-container-low p-md shadow-sm">
                    <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                      Milestone Title
                    </label>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      placeholder="Milestone title"
                      className="w-full rounded border border-outline-variant bg-surface px-sm py-xs text-sm text-on-surface outline-none focus:border-primary"
                      autoFocus
                    />

                    <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                      Status
                    </label>
                    <select
                      value={editStatus}
                      onChange={(e) => setEditStatus(e.target.value as Milestone["status"])}
                      className="w-full rounded border border-outline-variant bg-surface px-sm py-xs text-sm text-on-surface outline-none focus:border-primary"
                    >
                      {statusOptions.map((opt) => (
                        <option key={opt} value={opt}>
                          {statusLabel[opt]}
                        </option>
                      ))}
                    </select>

                    <div className="flex items-center gap-xs pt-xs">
                      <button
                        type="button"
                        onClick={() => handleSaveEdit(m.id)}
                        disabled={savingEdit || !editTitle.trim()}
                        className="rounded-full bg-primary px-md py-xs text-xs font-bold text-on-primary hover:opacity-90 disabled:opacity-50"
                      >
                        {savingEdit ? "Saving..." : "Save"}
                      </button>
                      <button
                        type="button"
                        onClick={cancelEditing}
                        disabled={savingEdit}
                        className="rounded-full border border-outline-variant px-md py-xs text-xs font-medium text-on-surface hover:bg-surface-variant"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-between gap-sm">
                    <div className="min-w-0 flex-1">
                      <p
                        className={`font-title-md text-title-md leading-tight ${
                          m.status === "in_progress"
                            ? "text-primary font-bold"
                            : "text-on-surface"
                        }`}
                      >
                        {m.title}
                      </p>
                      <div className="mt-0.5 flex items-center gap-xs">
                        <span
                          className={`inline-block rounded px-xs py-0.5 text-[11px] font-semibold ${
                            m.status === "done"
                              ? "bg-secondary/15 text-secondary"
                              : m.status === "in_progress"
                                ? "bg-primary/15 text-primary"
                                : m.status === "blocked"
                                  ? "bg-error/15 text-error"
                                  : "bg-surface-variant text-on-surface-variant"
                          }`}
                        >
                          {statusLabel[m.status]}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-xs">
                      {isActionable && (
                        <button
                          onClick={() => onCompleteMilestone(m.id)}
                          className="tap-target shrink-0 rounded-full bg-primary px-sm py-xs font-label-sm text-label-sm text-on-primary transition-transform active:scale-95 shadow-sm hover:opacity-95"
                        >
                          Mark done
                        </button>
                      )}

                      {onUpdateMilestone && (
                        <button
                          type="button"
                          onClick={() => startEditing(m)}
                          aria-label="Edit milestone"
                          className="tap-target flex h-8 w-8 items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-variant hover:text-on-surface transition-colors"
                        >
                          <Icon name="edit" size={16} />
                        </button>
                      )}

                      {onDeleteMilestone && (
                        <button
                          type="button"
                          onClick={() => handleDelete(m.id)}
                          aria-label="Delete milestone"
                          className="tap-target flex h-8 w-8 items-center justify-center rounded-full text-on-surface-variant hover:bg-error/10 hover:text-error transition-colors"
                        >
                          <Icon name="delete" size={16} />
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {/* Add New Milestone Section */}
      {onCreateMilestone && (
        <div className="pt-sm">
          {!isAdding ? (
            <button
              type="button"
              onClick={() => setIsAdding(true)}
              className="flex w-full items-center justify-center gap-xs rounded-xl border border-dashed border-outline-variant py-md text-sm font-semibold text-primary transition-colors hover:border-primary hover:bg-primary/5 active:scale-[0.99]"
            >
              <Icon name="add" size={18} />
              <span>Add Milestone Step</span>
            </button>
          ) : (
            <form
              onSubmit={handleCreate}
              className="flex flex-col gap-sm rounded-xl border border-primary/40 bg-surface-container-low p-md shadow-sm animate-in fade-in"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold uppercase tracking-wider text-primary">
                  New Milestone Step
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setIsAdding(false);
                    setNewTitle("");
                  }}
                  className="text-on-surface-variant hover:text-on-surface"
                >
                  <Icon name="close" size={16} />
                </button>
              </div>

              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="e.g., Secure wholesale feed supplier"
                className="w-full rounded border border-outline-variant bg-surface px-sm py-xs text-sm text-on-surface outline-none focus:border-primary"
                autoFocus
                required
              />

              <div className="flex items-center gap-sm">
                <label className="text-xs font-medium text-on-surface-variant shrink-0">
                  Initial Status:
                </label>
                <select
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value as Milestone["status"])}
                  className="rounded border border-outline-variant bg-surface px-sm py-xs text-xs text-on-surface outline-none focus:border-primary"
                >
                  {statusOptions.map((opt) => (
                    <option key={opt} value={opt}>
                      {statusLabel[opt]}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-xs pt-xs">
                <button
                  type="submit"
                  disabled={addingLoading || !newTitle.trim()}
                  className="rounded-full bg-primary px-md py-xs text-xs font-bold text-on-primary hover:opacity-90 disabled:opacity-50"
                >
                  {addingLoading ? "Adding..." : "Add Step"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setIsAdding(false);
                    setNewTitle("");
                  }}
                  className="rounded-full border border-outline-variant px-md py-xs text-xs font-medium text-on-surface hover:bg-surface-variant"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
