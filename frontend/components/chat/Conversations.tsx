"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { img } from "@/lib/stitchImages";
import { ACCENT_BG, ACCENT_RING, ACCENT_TEXT } from "@/lib/mentors";
import { timeAgo, type ConversationRow, type Conversations } from "./useConversations";

function DeleteDialog({ preview, onConfirm, onCancel }: { preview: string; onConfirm: () => void; onCancel: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onCancel(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel]);
  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-brand-ink/40 px-4 backdrop-blur-[6px]" onClick={onCancel} role="presentation">
      <div role="alertdialog" aria-modal="true" aria-labelledby="del-title" className="w-full max-w-sm animate-rise rounded-[24px] bg-paper p-6 shadow-[0_24px_64px_rgba(20,17,13,0.22)]" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center gap-2">
          <span className="material-symbols-outlined text-[20px] text-tertiary">warning</span>
          <span className="font-eyebrow text-eyebrow uppercase tracking-widest text-tertiary">Cannot be undone</span>
        </div>
        <h2 id="del-title" className="font-title-md text-[22px] font-medium text-on-surface">Delete this conversation?</h2>
        <p className="mt-2 font-body-md text-label-sm text-on-surface-variant">“{preview}”</p>
        <p className="mt-1 font-caption text-caption text-outline-strong">This conversation and all its messages will be permanently removed.</p>
        <div className="mt-6 flex gap-3">
          <button type="button" onClick={onCancel} className="h-11 flex-1 rounded-full border border-outline-subtle font-label-sm text-label-sm font-semibold text-on-surface transition-colors hover:bg-surface-default">Cancel</button>
          <button type="button" onClick={onConfirm} className="flex h-11 flex-1 items-center justify-center gap-2 rounded-full bg-tertiary font-label-sm text-label-sm font-semibold text-on-tertiary transition-all hover:bg-tertiary-container active:scale-95">
            <span className="material-symbols-outlined text-[18px]">delete</span>Delete
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function AiTag({ className = "" }: { className?: string }) {
  return <span className={`absolute -bottom-1 -right-1 rounded border border-paper bg-indigo-mist px-1 py-[1px] text-[9px] font-bold tracking-wide text-secondary shadow-xs ${className}`}>AI</span>;
}

/** Desktop / tablet row (W1/W2 panel). */
function PanelRow({ r, active, onOpen, onDelete }: { r: ConversationRow; active: boolean; onOpen: () => void; onDelete: () => void }) {
  return (
    <div className={`group relative flex min-h-[68px] items-center gap-3 rounded-xl py-2.5 pl-3.5 pr-2 transition-all ${active ? "border-l-[3px] border-sunburst-gold bg-gold-mist/35 shadow-[0_2px_8px_rgba(255,180,0,0.08)]" : "hover:bg-surface-high/60"}`}>
      <button type="button" onClick={onOpen} aria-current={active ? "true" : undefined} className="flex min-w-0 flex-1 items-center gap-3 text-left">
        <span className="relative shrink-0">
          <img src={img(r.mentor.avatar)} alt={r.title} className={`h-11 w-11 rounded-full object-cover ring-2 ${ACCENT_RING[r.mentor.accent]}`} />
          <AiTag />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center justify-between gap-2">
            <span className={`truncate font-label-sm text-label-sm text-on-surface ${active ? "font-bold" : "font-semibold"}`}>{r.title}</span>
            <span className={`shrink-0 font-caption text-[11px] ${active ? "font-bold text-sunburst-gold" : "text-outline-strong"}`}>{timeAgo(r.session.lastMessageAt ?? r.session.updatedAt, true)}</span>
          </span>
          <span className="block truncate font-caption text-caption text-on-surface-variant">{r.preview}</span>
        </span>
      </button>
      <button type="button" aria-label={`Delete conversation with ${r.title}`} onClick={onDelete} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-outline-strong opacity-0 transition-all hover:bg-tertiary-fixed hover:text-tertiary focus-visible:opacity-100 group-hover:opacity-100">
        <span className="material-symbols-outlined text-[18px]">delete</span>
      </button>
    </div>
  );
}

export function ConversationPanel({
  convo, onSelect, onCollapse, activeCount = true, className = "",
}: { convo: Conversations; onSelect?: () => void; onCollapse?: () => void; activeCount?: boolean; className?: string }) {
  const [q, setQ] = useState("");
  const rows = convo.rows.filter((r) => !q.trim() || (r.title + " " + r.preview + " " + r.mentor.role).toLowerCase().includes(q.trim().toLowerCase()));
  return (
    <aside className={`flex h-full w-[300px] shrink-0 flex-col border-r border-outline-subtle bg-surface-low ${className}`} aria-label="Conversations">
      <div className="flex items-center justify-between px-5 pb-4 pt-6">
        <div className="flex items-center gap-2">
          <h2 className="font-title-md text-title-md tracking-tight text-on-surface">Conversations</h2>
          {activeCount && <span className="rounded-full bg-surface-high px-2 py-0.5 font-caption text-[11px] font-semibold text-on-surface-variant">{convo.rows.length} Active</span>}
        </div>
        {onCollapse && (
          <button type="button" onClick={onCollapse} title="Collapse panel" aria-label="Collapse conversations panel" className="flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-high hover:text-on-surface">
            <span className="material-symbols-outlined text-[20px]">first_page</span>
          </button>
        )}
      </div>
      <div className="px-5 pb-4">
        <Link href="/persona" className="group flex h-[44px] w-full items-center justify-center gap-2 rounded-full bg-primary-container font-label-sm text-label-sm font-semibold text-on-primary shadow-sm transition-all duration-150 hover:bg-primary active:scale-[0.98]">
          <span className="material-symbols-outlined text-[18px] transition-transform group-hover:rotate-90">add</span>
          <span>New conversation</span>
        </Link>
      </div>
      <div className="px-5 pb-3">
        <label className="relative block w-full">
          <span className="sr-only">Filter conversations</span>
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[18px] text-outline-strong">search</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter mentors & topics…" className="h-9 w-full rounded-lg border border-outline-subtle bg-paper pl-9 pr-3 font-caption text-caption text-on-surface placeholder:text-outline-strong focus:border-primary-container focus:outline-none" />
        </label>
      </div>
      <div className="flex-1 select-none space-y-1 overflow-y-auto px-2 pb-3">
        {rows.length === 0 && (
          <p className="px-3 py-4 font-caption text-caption text-on-surface-variant">
            {convo.rows.length === 0 ? (convo.loaded ? "No conversations yet. Choose a mentor to start one." : "Loading conversations…") : "No conversations match your filter."}
          </p>
        )}
        {rows.map((r) => (
          <PanelRow key={r.session.id} r={r} active={r.session.id === convo.activeId}
            onOpen={async () => { await convo.open(r.session.id); onSelect?.(); }}
            onDelete={() => convo.requestDelete(r.session.id, r.preview.slice(0, 40))} />
        ))}
      </div>
      {convo.pendingDelete && <DeleteDialog preview={convo.pendingDelete.preview} onConfirm={convo.confirmDelete} onCancel={convo.cancelDelete} />}
    </aside>
  );
}

/** Mobile card with swipe-to-delete (M5). */
function MobileCard({ r, active, onOpen, onDelete }: { r: ConversationRow; active: boolean; onOpen: () => void; onDelete: () => void }) {
  const [dx, setDx] = useState(0);
  const start = useRef<number | null>(null);
  const ring = r.mentor.accent;
  return (
    <div className="relative overflow-hidden rounded-[16px] bg-paper shadow-sm">
      <div className={`absolute inset-y-0 right-0 flex w-20 items-center justify-center bg-tertiary transition-opacity ${dx < 0 ? "opacity-100" : "pointer-events-none opacity-0"}`}>
        <button type="button" onClick={onDelete} aria-label="Delete conversation" className="flex flex-col items-center gap-0.5 text-on-tertiary">
          <span className="material-symbols-outlined text-[22px]">delete</span>
          <span className="text-[11px] font-bold">Delete</span>
        </button>
      </div>
      <div
        style={{ transform: `translateX(${dx}px)`, transition: dx === 0 || start.current === null ? "transform .2s" : "none" }}
        onTouchStart={(e) => { start.current = e.touches[0].clientX; }}
        onTouchMove={(e) => { if (start.current === null) return; const d = e.touches[0].clientX - start.current; setDx(d < 0 ? Math.max(d, -80) : 0); }}
        onTouchEnd={() => { if (dx > -50) setDx(0); else setDx(-80); start.current = null; }}
        className={`relative bg-paper ${active ? "bg-gold-mist/20" : ""}`}
      >
        {active && <div className="absolute inset-y-0 left-0 w-[4px] bg-sunburst-gold" />}
        <button type="button" onClick={onOpen} className="flex w-full items-center gap-3.5 p-3.5 pl-4 text-left active:scale-[0.99]">
          <span className="relative shrink-0">
            <span className={`flex h-[52px] w-[52px] items-center justify-center rounded-full p-0.5 shadow-sm ${ACCENT_BG[ring]}`}>
              <img src={img(r.mentor.avatar)} alt={r.title} className="h-full w-full rounded-full object-cover" />
            </span>
            <span className="absolute -bottom-1 -right-1 flex items-center justify-center rounded-full bg-indigo-mist px-1.5 text-[10px] font-bold tracking-tight text-secondary shadow-sm">AI</span>
          </span>
          <span className="min-w-0 flex-1">
            <span className="mb-0.5 flex items-baseline justify-between">
              <span className="flex min-w-0 items-center gap-1.5">
                <span className="truncate font-body-md text-[15px] font-semibold text-on-surface">{r.title}</span>
                <span className={`shrink-0 font-caption text-[11px] font-bold ${ACCENT_TEXT[ring]}`}>{r.mentor.role.replace("The ", "")}</span>
              </span>
              <span className={`ml-1 shrink-0 font-caption text-[12px] ${active ? "font-medium text-primary" : "text-outline-strong"}`}>{timeAgo(r.session.lastMessageAt ?? r.session.updatedAt)}</span>
            </span>
            <span className="line-clamp-1 block text-[13px] leading-tight text-on-surface-variant">{r.preview}</span>
          </span>
        </button>
      </div>
    </div>
  );
}

/** Mobile "Conversations" screen body (M5). The header + tab bar are provided by the page. */
export function ConversationScreen({ convo, onOpen }: { convo: Conversations; onOpen: () => void }) {
  const [q, setQ] = useState("");
  const rows = convo.rows.filter((r) => !q.trim() || (r.title + " " + r.preview).toLowerCase().includes(q.trim().toLowerCase()));
  return (
    <div className="flex w-full flex-col">
      <div className="flex items-center justify-between px-margin pb-space-sm pt-space-md">
        <div className="flex flex-col">
          <span className="font-eyebrow text-[10px] uppercase tracking-widest text-primary">Your mentors</span>
          <h2 className="font-headline-lg-mobile text-headline-lg-mobile text-on-surface">Conversations</h2>
        </div>
        <Link href="/persona" aria-label="New conversation" className="group flex h-11 w-11 items-center justify-center rounded-full bg-primary-container text-on-primary shadow-md transition-all hover:bg-primary active:scale-95">
          <span className="material-symbols-outlined text-[24px] transition-transform duration-300 group-hover:rotate-90">add</span>
        </Link>
      </div>
      <div className="px-margin pb-space-md pt-space-xs">
        <label className="flex items-center gap-2 rounded-xl bg-surface-container-low px-3 py-2 text-on-surface-variant">
          <span className="material-symbols-outlined text-[20px] text-outline-strong">search</span>
          <span className="sr-only">Search conversations</span>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search mentors or advice…" className="w-full bg-transparent text-[14px] text-on-surface placeholder:text-outline-strong focus:outline-none" />
        </label>
      </div>
      <div className="flex flex-col gap-3 px-margin pb-8">
        {rows.length === 0 && (
          <div className="rounded-2xl bg-paper p-6 text-center shadow-sm">
            <span className="material-symbols-outlined text-[32px] text-outline-strong">forum</span>
            <p className="mt-2 font-label-sm text-label-sm text-on-surface">{convo.rows.length === 0 ? (convo.loaded ? "No conversations yet" : "Loading…") : "Nothing matches your search"}</p>
            {convo.rows.length === 0 && convo.loaded && <Link href="/persona" className="mt-4 inline-flex h-10 items-center rounded-full bg-primary-container px-5 font-label-sm text-label-sm font-semibold text-on-primary">Choose a mentor</Link>}
          </div>
        )}
        {rows.map((r) => (
          <MobileCard key={r.session.id} r={r} active={r.session.id === convo.activeId}
            onOpen={async () => { await convo.open(r.session.id); onOpen(); }}
            onDelete={() => convo.requestDelete(r.session.id, r.preview.slice(0, 40))} />
        ))}
      </div>
      {convo.pendingDelete && <DeleteDialog preview={convo.pendingDelete.preview} onConfirm={convo.confirmDelete} onCancel={convo.cancelDelete} />}
    </div>
  );
}
