"use client";

import { useState } from "react";
import { Icon } from "@/components/Icon";
import type { Milestone } from "@/lib/types";

type Status = Milestone["status"];
const LABEL: Record<Status, string> = { done: "Completed", in_progress: "Current focus", blocked: "Blocked", upcoming: "Upcoming" };
const OPTIONS: Status[] = ["in_progress", "done", "blocked", "upcoming"];
const FIELD = "w-full rounded-lg border border-outline-variant bg-surface px-3 py-2 font-body-md text-[15px] text-on-surface outline-none focus:border-primary focus:ring-2 focus:ring-primary/20";

function Node({ status, n }: { status: Status; n: number }) {
  const cls =
    status === "done" ? "bg-primary text-on-primary"
    : status === "in_progress" ? "bg-sunburst-gold text-ink ring-4 ring-sunburst-gold/30"
    : status === "blocked" ? "bg-error text-on-error"
    : "border-2 border-outline-variant bg-surface-container-low text-on-surface-variant";
  return (
    <span className={`z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full font-label-sm text-[15px] font-bold ${cls}`}>
      {status === "done" ? <Icon name="check" size={20} /> : status === "blocked" ? <Icon name="priority_high" size={20} /> : status === "in_progress" ? <Icon name="sync" size={20} /> : n}
    </span>
  );
}

export function MilestoneTimeline({
  milestones, onComplete, onUpdate, onDelete, onCreate,
}: {
  milestones: Milestone[];
  onComplete: (id: string) => Promise<void>;
  onUpdate: (id: string, u: { title?: string; status?: Status }) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onCreate: (i: { title: string; status?: Status }) => Promise<void>;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editStatus, setEditStatus] = useState<Status>("upcoming");
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newStatus, setNewStatus] = useState<Status>("upcoming");
  const [err, setErr] = useState<string | null>(null);

  async function run(fn: () => Promise<void>) {
    setBusy(true); setErr(null);
    try { await fn(); } catch { setErr("That didn't save — check your connection and try again."); } finally { setBusy(false); }
  }

  return (
    <div>
      {err && <p role="alert" className="mb-3 rounded-xl bg-error-container px-4 py-2 font-label-sm text-label-sm text-on-error-container">{err}</p>}
      <ol className="relative">
        {milestones.map((m, i) => {
          const last = i === milestones.length - 1 && !adding;
          const editing = editingId === m.id;
          return (
            <li key={m.id} className="relative flex gap-4 pb-6 last:pb-0">
              {!last && <span aria-hidden className={`absolute left-5 top-10 -ml-px h-[calc(100%-2.5rem)] w-0.5 ${m.status === "done" ? "bg-primary" : "border-l-2 border-dashed border-outline-variant"}`} />}
              <Node status={m.status} n={i + 1} />
              <div className={`min-w-0 flex-1 rounded-2xl border bg-surface-container-lowest p-4 shadow-sm md:p-5 ${m.status === "in_progress" ? "border-sunburst-gold ring-1 ring-sunburst-gold/40" : "border-outline-variant"} ${m.status === "upcoming" ? "opacity-80" : ""}`}>
                {editing ? (
                  <div className="flex flex-col gap-3">
                    <label className="font-eyebrow text-eyebrow uppercase text-on-surface-variant">Milestone title</label>
                    <input autoFocus value={editTitle} onChange={(e) => setEditTitle(e.target.value)} className={FIELD} />
                    <label className="font-eyebrow text-eyebrow uppercase text-on-surface-variant">Status</label>
                    <select value={editStatus} onChange={(e) => setEditStatus(e.target.value as Status)} className={FIELD}>
                      {OPTIONS.map((o) => <option key={o} value={o}>{LABEL[o]}</option>)}
                    </select>
                    <div className="flex gap-2">
                      <button type="button" disabled={busy || !editTitle.trim()} onClick={() => run(async () => { await onUpdate(m.id, { title: editTitle.trim(), status: editStatus }); setEditingId(null); })} className="rounded-full bg-primary px-5 py-2 font-label-sm text-label-sm text-on-primary disabled:opacity-50">{busy ? "Saving..." : "Save"}</button>
                      <button type="button" disabled={busy} onClick={() => setEditingId(null)} className="rounded-full border border-outline-variant px-5 py-2 font-label-sm text-label-sm text-on-surface">Cancel</button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded-full px-2.5 py-0.5 font-eyebrow text-[10px] uppercase ${m.status === "done" ? "bg-primary/15 text-primary" : m.status === "in_progress" ? "bg-sunburst-gold text-ink" : m.status === "blocked" ? "bg-error-container text-on-error-container" : "bg-surface-container-high text-on-surface-variant"}`}>{LABEL[m.status]}</span>
                        <span className="font-caption text-caption text-on-surface-variant">Phase {String(i + 1).padStart(2, "0")}</span>
                      </div>
                      <h3 className={`mt-2 font-title-md text-[20px] leading-7 ${m.status === "done" ? "text-on-surface-variant line-through decoration-outline/50" : "text-on-surface"}`}>{m.title}</h3>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <button type="button" aria-label="Edit milestone" onClick={() => { setEditingId(m.id); setEditTitle(m.title); setEditStatus(m.status); }} className="flex h-9 w-9 items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-container-low"><Icon name="edit" size={18} /></button>
                      <button type="button" aria-label="Delete milestone" onClick={() => { if (confirm("Are you sure you want to remove this milestone step?")) run(() => onDelete(m.id)); }} className="flex h-9 w-9 items-center justify-center rounded-full text-on-surface-variant hover:bg-error/10 hover:text-error"><Icon name="delete" size={18} /></button>
                    </div>
                  </div>
                )}
                {!editing && m.status === "in_progress" && (
                  <button type="button" disabled={busy} onClick={() => run(() => onComplete(m.id))} className="mt-4 flex h-11 items-center gap-2 rounded-full bg-sunburst-gold px-5 font-label-sm text-[15px] font-bold text-ink shadow-md active:scale-[0.98] disabled:opacity-50">
                    Mark as done <Icon name="check_circle" size={18} filled />
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      <div className="mt-6">
        {!adding ? (
          <button type="button" onClick={() => setAdding(true)} className="flex w-full items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-outline-variant py-4 font-label-sm text-[15px] text-primary transition-colors hover:border-primary hover:bg-primary/5">
            <Icon name="add" size={18} /> Add milestone step
          </button>
        ) : (
          <form onSubmit={(e) => { e.preventDefault(); if (!newTitle.trim()) return; run(async () => { await onCreate({ title: newTitle.trim(), status: newStatus }); setNewTitle(""); setNewStatus("upcoming"); setAdding(false); }); }} className="flex flex-col gap-3 rounded-2xl border border-primary/40 bg-surface-container-low p-4">
            <div className="flex items-center justify-between"><span className="font-eyebrow text-eyebrow uppercase text-primary">New milestone step</span><button type="button" aria-label="Close" onClick={() => setAdding(false)} className="text-on-surface-variant"><Icon name="close" size={18} /></button></div>
            <input autoFocus required value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="e.g. Secure wholesale feed supplier" className={FIELD} />
            <div className="flex items-center gap-2"><span className="font-caption text-caption text-on-surface-variant">Initial status</span>
              <select value={newStatus} onChange={(e) => setNewStatus(e.target.value as Status)} className="rounded-lg border border-outline-variant bg-surface px-2 py-1 font-caption text-caption text-on-surface">{OPTIONS.map((o) => <option key={o} value={o}>{LABEL[o]}</option>)}</select></div>
            <div className="flex gap-2"><button type="submit" disabled={busy || !newTitle.trim()} className="rounded-full bg-primary px-5 py-2 font-label-sm text-label-sm text-on-primary disabled:opacity-50">{busy ? "Adding..." : "Add step"}</button><button type="button" onClick={() => setAdding(false)} className="rounded-full border border-outline-variant px-5 py-2 font-label-sm text-label-sm text-on-surface">Cancel</button></div>
          </form>
        )}
      </div>
    </div>
  );
}
