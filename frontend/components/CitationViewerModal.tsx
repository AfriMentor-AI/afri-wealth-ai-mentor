"use client";

import { useEffect, useState } from "react";
import { queryRag } from "@/lib/api";
import type { RagChunk } from "@/lib/types";
import { KenteStrip } from "./shell/AppSidebar";

interface Props {
  citationLabel: string | null;
  messageContext?: string;
  onClose: () => void;
  onAskFollowUp: (prompt: string) => void;
}

/** "Verified citation" viewer. Same RAG lookup as before (queryRag); restyled to the Stitch overlay. */
export function CitationViewerModal({ citationLabel, messageContext, onClose, onAskFollowUp }: Props) {
  const [loading, setLoading] = useState(false);
  const [chunks, setChunks] = useState<RagChunk[]>([]);

  useEffect(() => {
    if (!citationLabel && !messageContext) { setChunks([]); return; }
    let alive = true;
    setLoading(true);
    queryRag(citationLabel || messageContext || "AfriMentor Knowledge", { topK: 3 })
      .then((res) => { if (alive) { setChunks(res.results || []); setLoading(false); } })
      .catch((err) => { console.warn("Could not retrieve citation details:", err); if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [citationLabel, messageContext]);

  useEffect(() => {
    if (!citationLabel) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [citationLabel, onClose]);

  if (!citationLabel) return null;

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="citation-title" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
      className="fixed inset-0 z-[80] flex items-end justify-center bg-brand-ink/40 backdrop-blur-[6px] sm:items-center sm:p-4">
      <div className="relative flex max-h-[88vh] w-full max-w-xl animate-rise flex-col overflow-hidden rounded-t-[28px] bg-paper shadow-[0_24px_64px_rgba(20,17,13,0.22)] sm:rounded-[28px]">
        <div className="[&>div]:h-1.5"><KenteStrip /></div>
        <div className="flex items-start justify-between gap-4 px-6 pb-3 pt-6">
          <div className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-mist text-secondary">
              <span className="material-symbols-outlined text-[18px]">auto_stories</span>
            </span>
            <div>
              <p className="font-eyebrow text-eyebrow uppercase tracking-widest text-secondary">Verified source</p>
              <h2 id="citation-title" className="font-title-md text-[20px] font-medium leading-tight text-on-surface">{citationLabel}</h2>
            </div>
          </div>
          <button type="button" onClick={onClose} aria-label="Close citation details" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-outline-strong transition-colors hover:bg-surface-default hover:text-on-surface">
            <span className="material-symbols-outlined text-[20px]">close</span>
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 pb-4">
          <p className="rounded-2xl bg-surface-low p-4 font-body-md text-label-sm text-on-surface-variant">
            This answer was grounded in the AfriMentor knowledge corpus: regional enterprise curriculum, local trade research and practical financial guidance.
          </p>
          {loading ? (
            <div className="flex flex-col items-center justify-center py-8 text-on-surface-variant">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <p className="mt-3 font-caption text-caption">Looking up the source…</p>
            </div>
          ) : chunks.length > 0 ? (
            <div className="space-y-3">
              <h3 className="font-eyebrow text-eyebrow uppercase tracking-widest text-outline-strong">Matching excerpts ({chunks.length})</h3>
              {chunks.map((chunk, i) => {
                const meta = chunk.metadata || {};
                const pct = Math.min(100, Math.round(chunk.score * 100));
                return (
                  <article key={chunk.chunk_id || i} className="rounded-2xl border border-l-[4px] border-outline-subtle border-l-sunburst-gold bg-paper p-4 shadow-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-label-sm text-label-sm font-bold text-on-surface">{meta.title || meta.filename || citationLabel}</p>
                      {pct > 0 && <span className="rounded-full bg-indigo-mist px-2 py-0.5 font-caption text-[11px] font-bold text-secondary">{pct}% match</span>}
                    </div>
                    {meta.sector && <p className="mt-0.5 font-caption text-caption text-primary">Sector: {meta.sector}{meta.market ? ` · Market: ${meta.market}` : ""}</p>}
                    <blockquote className="mt-3 font-quote text-[17px] italic leading-snug text-on-surface">“{chunk.content}”</blockquote>
                  </article>
                );
              })}
            </div>
          ) : (
            <p className="rounded-2xl border border-outline-subtle bg-surface-low p-4 text-center font-caption text-caption text-on-surface-variant">
              This citation is grounded in the foundational {citationLabel} knowledge base.
            </p>
          )}
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-outline-subtle px-6 py-4">
          <button type="button" onClick={onClose} className="h-10 rounded-full px-5 font-label-sm text-label-sm font-semibold text-on-surface-variant transition-colors hover:bg-surface-default">Close</button>
          <button type="button" onClick={() => onAskFollowUp(`Can you share more practical details from "${citationLabel}" on how this applies to my business?`)}
            className="flex h-10 items-center gap-2 rounded-full bg-primary px-5 font-label-sm text-label-sm font-semibold text-on-primary shadow-sm transition-all hover:bg-primary-container active:scale-95">
            <span className="material-symbols-outlined text-[18px]">chat</span>Ask a follow-up
          </button>
        </div>
      </div>
    </div>
  );
}
