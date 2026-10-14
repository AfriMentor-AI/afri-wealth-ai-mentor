"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { useAppDispatch, useAppState } from "@/lib/store";
import { createGoal, updateGoal, deleteGoal } from "@/lib/api";
import type { Goal } from "@/lib/types";

const field = "w-full rounded-xl border border-outline-variant bg-surface-container-low px-4 py-2.5 font-body-md text-[15px] text-on-surface outline-none transition-colors placeholder:text-on-surface-variant/60 focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:opacity-60";
const lbl = "mb-1 block font-eyebrow text-eyebrow uppercase text-on-surface-variant";

function Shell({ id, icon, title, subtitle, onClose, busy, children }: { id: string; icon: string; title: string; subtitle: string; onClose: () => void; busy: boolean; children: React.ReactNode }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && !busy && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [busy, onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/50 p-0 backdrop-blur-sm sm:items-center sm:p-4" role="dialog" aria-modal="true" aria-labelledby={id} onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <div className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-t-3xl border border-outline-variant bg-surface-container-lowest p-6 shadow-2xl sm:rounded-3xl sm:p-8">
        <div className="mb-5 flex items-start justify-between gap-3 border-b border-outline-variant/50 pb-4">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-full bg-gold-mist text-sunburst-gold"><Icon name={icon} /></span>
            <div>
              <h2 id={id} className="font-title-md text-[22px] leading-7 text-on-surface">{title}</h2>
              <p className="font-caption text-caption text-on-surface-variant">{subtitle}</p>
            </div>
          </div>
          <button type="button" onClick={onClose} disabled={busy} aria-label="Close" className="flex h-9 w-9 items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container-low disabled:opacity-50"><Icon name="close" size={20} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function GoldButton({ children, ...p }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...p} className="flex h-11 items-center justify-center gap-2 rounded-full bg-sunburst-gold px-6 font-label-sm text-[15px] font-bold text-ink shadow-md transition-all hover:brightness-105 active:scale-[0.98] disabled:opacity-50">{children}</button>;
}

export function CreateGoalModal() {
  const { newGoalModalOpen } = useAppState();
  const dispatch = useAppDispatch();
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!newGoalModalOpen) return;
    setTitle(""); setDescription(""); setDeadline(""); setError(null);
    const t = setTimeout(() => ref.current?.focus(), 50);
    return () => clearTimeout(t);
  }, [newGoalModalOpen]);

  if (!newGoalModalOpen) return null;
  const close = () => !creating && dispatch({ type: "CLOSE_NEW_GOAL_MODAL" });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const clean = title.trim();
    if (!clean) { setError("Please enter a goal title."); return; }
    setCreating(true); setError(null);
    try {
      const created = await createGoal({ title: clean, description: description.trim() || undefined, deadline: deadline || undefined });
      dispatch({ type: "SET_ACTIVE_GOAL_ID", goalId: created.id });
      dispatch({ type: "CLOSE_NEW_GOAL_MODAL" });
      window.dispatchEvent(new CustomEvent("goal-created", { detail: created }));
      router.push("/goals");
    } catch (err) {
      console.warn("createGoal error:", err);
      setError("Failed to create goal. Please check your connection and try again.");
    } finally { setCreating(false); }
  }

  return (
    <Shell id="create-goal-title" icon="flag" title="Define new purpose" subtitle="Set an aspirational milestone for your enterprise growth" onClose={close} busy={creating}>
      {error && <div role="alert" className="mb-4 rounded-xl bg-error-container px-4 py-3 font-label-sm text-label-sm text-on-error-container">{error}</div>}
      <form onSubmit={submit} className="space-y-4">
        <div><label className={lbl}>Goal title <span className="text-error">*</span></label><input ref={ref} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Expand poultry capacity to 500 birds" className={field} disabled={creating} required /></div>
        <div><label className={lbl}>Description / strategy <span className="normal-case tracking-normal">(optional)</span></label><textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} placeholder="e.g. Save weekly from feed margins and add two solar incubators." className={field} disabled={creating} /></div>
        <div><label className={lbl}>Target completion date <span className="normal-case tracking-normal">(optional)</span></label><input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className={field} disabled={creating} /></div>
        <div className="flex flex-col-reverse gap-2 border-t border-outline-variant/40 pt-4 sm:flex-row sm:justify-end">
          <button type="button" onClick={close} disabled={creating} className="h-11 rounded-full px-6 font-label-sm text-[15px] font-bold text-on-surface-variant hover:bg-surface-container-low">Cancel</button>
          <GoldButton type="submit" disabled={creating || !title.trim()}>{creating ? "Creating..." : <><Icon name="add" size={18} /> Create goal</>}</GoldButton>
        </div>
      </form>
    </Shell>
  );
}

export function EditGoalModal({ goal, isOpen, onClose, onGoalUpdated, onGoalDeleted }: { goal: Goal | null; isOpen: boolean; onClose: () => void; onGoalUpdated: (g: Goal) => void; onGoalDeleted?: (id: string) => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !goal) return;
    setTitle(goal.title || "");
    setDescription(goal.description || "");
    const d = goal.deadline ? new Date(goal.deadline) : null;
    setDeadline(d && !isNaN(d.getTime()) ? d.toISOString().split("T")[0] : "");
    setConfirmDelete(false); setError(null);
  }, [isOpen, goal]);

  if (!isOpen || !goal) return null;
  const busy = saving || deleting;
  const close = () => { if (!busy) { setConfirmDelete(false); onClose(); } };

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!goal) return;
    const clean = title.trim();
    if (!clean) { setError("Please provide a goal title."); return; }
    setSaving(true); setError(null);
    try {
      const updated = await updateGoal(goal.id, { title: clean, description: description.trim() || null, deadline: deadline || null });
      onGoalUpdated(updated);
      setSaving(false);
      onClose();
    } catch (err) {
      console.warn("updateGoal error:", err);
      setError("Failed to update goal. Please check your connection and try again.");
      setSaving(false);
    }
  }

  async function remove() {
    if (!goal) return;
    setDeleting(true); setError(null);
    try {
      await deleteGoal(goal.id);
      onGoalDeleted?.(goal.id);
      setDeleting(false);
      onClose();
    } catch (err) {
      console.warn("deleteGoal error:", err);
      setError("Failed to delete goal. Please check your connection and try again.");
      setDeleting(false);
    }
  }

  return (
    <Shell id="edit-goal-title" icon="edit" title="Edit goal" subtitle="Modify your aspiration and target date" onClose={close} busy={busy}>
      {error && <div role="alert" className="mb-4 rounded-xl bg-error-container px-4 py-3 font-label-sm text-label-sm text-on-error-container">{error}</div>}
      <form onSubmit={submit} className="space-y-4">
        <div><label className={lbl}>Goal title <span className="text-error">*</span></label><input value={title} onChange={(e) => setTitle(e.target.value)} className={field} disabled={busy} required autoFocus /></div>
        <div><label className={lbl}>Description / strategy</label><textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className={field} disabled={busy} /></div>
        <div><label className={lbl}>Target completion date</label><input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className={field} disabled={busy} /></div>
        <div className="rounded-xl border border-error/30 bg-error-container/20 p-4">
          {!confirmDelete ? (
            <div className="flex items-center justify-between gap-3">
              <div><p className="font-label-sm text-label-sm text-error">Danger zone</p><p className="font-caption text-caption text-on-surface-variant">Delete this goal and its milestones</p></div>
              <button type="button" onClick={() => setConfirmDelete(true)} disabled={busy} className="rounded-full border border-error/50 px-4 py-1.5 font-label-sm text-label-sm text-error hover:bg-error/10 disabled:opacity-50">Delete goal</button>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="font-label-sm text-label-sm text-error">Delete this goal? This can’t be undone and removes all linked milestones.</p>
              <div className="flex gap-2">
                <button type="button" onClick={remove} disabled={deleting} className="rounded-full bg-error px-4 py-1.5 font-label-sm text-label-sm text-on-error disabled:opacity-50">{deleting ? "Deleting..." : "Yes, delete"}</button>
                <button type="button" onClick={() => setConfirmDelete(false)} disabled={deleting} className="rounded-full border border-outline-variant px-4 py-1.5 font-label-sm text-label-sm text-on-surface">Cancel</button>
              </div>
            </div>
          )}
        </div>
        <div className="flex flex-col-reverse gap-2 border-t border-outline-variant/40 pt-4 sm:flex-row sm:justify-end">
          <button type="button" onClick={close} disabled={busy} className="h-11 rounded-full px-6 font-label-sm text-[15px] font-bold text-on-surface-variant hover:bg-surface-container-low">Cancel</button>
          <GoldButton type="submit" disabled={busy || !title.trim()}>{saving ? "Saving..." : <><Icon name="check" size={18} /> Save changes</>}</GoldButton>
        </div>
      </form>
    </Shell>
  );
}
