"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { queryRag } from "@/lib/api";
import type { RagChunk } from "@/lib/types";

interface CitationViewerModalProps {
  citationLabel: string | null;
  messageContext?: string;
  onClose: () => void;
  onAskFollowUp: (prompt: string) => void;
}

export function CitationViewerModal({
  citationLabel,
  messageContext,
  onClose,
  onAskFollowUp,
}: CitationViewerModalProps) {
  const [loading, setLoading] = useState(false);
  const [chunks, setChunks] = useState<RagChunk[]>([]);

  useEffect(() => {
    if (!citationLabel && !messageContext) {
      setChunks([]);
      return;
    }

    let isMounted = true;
    setLoading(true);

    const queryText = citationLabel || messageContext || "AfriMentor Knowledge";
    queryRag(queryText, { topK: 3 })
      .then((res) => {
        if (isMounted) {
          setChunks(res.results || []);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.warn("Could not retrieve citation details:", err);
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [citationLabel, messageContext]);

  if (!citationLabel) return null;

  const handleAskFollowUp = (topic?: string) => {
    const prompt = topic
      ? `Can you explain more about what "${citationLabel}" says regarding: ${topic}?`
      : `Can you share more practical details from "${citationLabel}" on how this applies to my business?`;
    onAskFollowUp(prompt);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="citation-title"
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/60 p-sm backdrop-blur-sm md:p-md animate-fadeIn"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="relative flex max-h-[85vh] w-full max-w-xl flex-col rounded-2xl border border-outline-variant/30 bg-surface text-on-surface shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-outline-variant/20 bg-surface/95 px-md py-sm backdrop-blur-md md:px-lg md:py-md">
          <div className="flex items-center gap-xs">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Icon name="auto_stories" size={18} />
            </span>
            <div>
              <p className="font-label-sm text-[10px] uppercase tracking-wider text-primary font-bold">
                Verified Knowledge Source
              </p>
              <h2 id="citation-title" className="font-title-md text-base font-bold text-on-surface">
                {citationLabel}
              </h2>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close citation details"
            className="tap-target flex h-8 w-8 items-center justify-center rounded-full text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface"
          >
            <Icon name="close" size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 space-y-md overflow-y-auto p-md md:p-lg">
          <div className="rounded-xl border border-primary/20 bg-primary-container/20 p-md">
            <p className="font-label-sm text-xs font-semibold text-primary">
              AfriMentor Verified Intelligence
            </p>
            <p className="mt-xs font-body-sm text-xs leading-relaxed text-on-surface-variant">
              This response was grounded using the AfriMentor RAG Corpus, linking regional enterprise curriculum, local trade research, and practical financial guidelines.
            </p>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-lg text-on-surface-variant">
              <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <p className="mt-sm font-label-sm text-xs">Querying RAG Corpus...</p>
            </div>
          ) : chunks.length > 0 ? (
            <div className="space-y-sm">
              <h3 className="font-title-sm text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                Matching Corpus Excerpts ({chunks.length})
              </h3>
              {chunks.map((chunk, idx) => {
                const meta = chunk.metadata || {};
                const matchPercent = Math.min(100, Math.round(chunk.score * 100));
                return (
                  <div
                    key={chunk.chunk_id || idx}
                    className="rounded-xl border border-outline-variant/30 bg-surface-container-low p-md transition-colors hover:border-primary/30"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-xs">
                      <p className="font-label-md text-xs font-bold text-on-surface">
                        {meta.title || meta.filename || citationLabel}
                      </p>
                      {matchPercent > 0 && (
                        <span className="rounded-full bg-secondary-container px-2 py-0.5 font-label-sm text-[10px] font-bold text-on-secondary-container">
                          {matchPercent}% Match
                        </span>
                      )}
                    </div>
                    {meta.sector && (
                      <p className="mt-0.5 font-label-sm text-[11px] text-primary">
                        Sector: {meta.sector} {meta.market ? `• Market: ${meta.market}` : ""}
                      </p>
                    )}
                    <p className="mt-sm font-body-sm text-xs leading-relaxed text-on-surface-variant bg-surface p-sm rounded border border-outline-variant/10">
                      &ldquo;{chunk.content}&rdquo;
                    </p>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="rounded-xl border border-outline-variant/20 bg-surface-container-low p-md text-center">
              <p className="font-body-sm text-xs text-on-surface-variant">
                Citation is grounded in the foundational {citationLabel} knowledge base.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-outline-variant/20 bg-surface/95 px-md py-sm backdrop-blur-md md:px-lg md:py-md">
          <button
            onClick={onClose}
            className="rounded-lg border border-outline-variant/30 px-md py-2 font-label-md text-xs font-medium text-on-surface transition-colors hover:bg-surface-container"
          >
            Close
          </button>
          <button
            onClick={() => handleAskFollowUp()}
            className="flex items-center gap-xs rounded-lg bg-primary px-md py-2 font-label-md text-xs font-bold text-on-primary shadow-sm transition-all hover:bg-primary/90 active:scale-95"
          >
            <Icon name="chat" size={16} />
            Ask Follow-up in Chat
          </button>
        </div>
      </div>
    </div>
  );
}
