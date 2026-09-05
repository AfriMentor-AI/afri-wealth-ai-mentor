"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { fetchInsights, toggleInsightFavorite, queryRag, fetchRagStats } from "@/lib/api";
import type { InsightItem, RagChunk, RagCorpusStats } from "@/lib/types";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAppDispatch, useAppState } from "@/lib/store";
import { InsightReaderModal } from "@/components/InsightReaderModal";

const FILTERS = [
  { label: "Sector", icon: "expand_more" },
  { label: "Topic", icon: "expand_more" },
  { label: "Audio", icon: "headphones" },
  { label: "Text", icon: "description" },
  { label: "RAG Corpus", icon: "database" },
];

// Card shared by the mobile "Curated Insights" list and the desktop grid —
// same InsightItem data, no fabricated titles/stats beyond what's real here.
function InsightCard({
  item,
  isFavorite,
  onToggleFavorite,
  onOpen,
}: {
  item: InsightItem;
  isFavorite: boolean;
  onToggleFavorite: () => void;
  onOpen: () => void;
}) {
  return (
    <div
      onClick={onOpen}
      className="group relative flex cursor-pointer flex-col gap-sm rounded border border-outline-variant/30 bg-surface-container-low p-md transition-all duration-300 hover:border-primary/40 hover:shadow-md active:scale-[0.99] md:rounded-xl md:p-lg"
    >
      <div className="flex items-start justify-between">
        <div className="flex flex-col gap-xs">
          <span className="inline-flex w-fit items-center gap-xs rounded-full bg-secondary-container px-sm py-1 text-[10px] font-bold uppercase tracking-wider text-on-secondary-container">
            <Icon name="auto_stories" size={14} />
            {item.summary}
          </span>
          <h3 className="font-title-md text-title-md pt-xs leading-tight text-on-surface">{item.title}</h3>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onOpen();
          }}
          aria-label={item.isAudio ? "Play audio insight" : "Read article"}
          className="rounded-full bg-primary/10 p-sm text-primary transition-transform hover:scale-110 active:scale-95"
        >
          <Icon name={item.isAudio ? "play_circle" : "menu_book"} filled={item.isAudio} />
        </button>
      </div>
      <div className="flex items-center gap-md text-label-sm text-on-surface-variant">
        <div className="flex items-center gap-xs">
          <Icon name={item.isAudio ? "headphones" : "description"} size={18} />
          <span>{item.isAudio ? "Audio Insight" : "Article"}</span>
        </div>
        <div className="flex items-center gap-xs">
          <Icon name="schedule" size={18} />
          <span>{item.durationMinutes} min</span>
        </div>
        <button
          aria-label={isFavorite ? "Remove from favorites" : "Save to favorites"}
          onClick={(e) => {
            e.stopPropagation();
            onToggleFavorite();
          }}
          className="tap-target ml-auto flex items-center justify-center rounded-full text-primary transition-transform hover:scale-110 active:scale-95"
        >
          <Icon name="favorite" filled={isFavorite} size={18} />
        </button>
      </div>
    </div>
  );
}

export default function InsightLibraryPage() {
  const { libraryFavorites } = useAppState();
  const dispatch = useAppDispatch();
  const [insights, setInsights] = useState<InsightItem[] | null>(null);
  const [selectedItem, setSelectedItem] = useState<InsightItem | null>(null);
  const [activeFilter, setActiveFilter] = useState("Sector");
  const [search, setSearch] = useState("");

  const [ragResults, setRagResults] = useState<RagChunk[]>([]);
  const [isRagSearching, setIsRagSearching] = useState(false);
  const [ragStats, setRagStats] = useState<RagCorpusStats | null>(null);

  useEffect(() => {
    fetchInsights().then(setInsights);
    fetchRagStats().then(setRagStats);
  }, []);

  useEffect(() => {
    const queryTerm = search.trim();
    if (!queryTerm && activeFilter !== "RAG Corpus") {
      setRagResults([]);
      return;
    }
    const q = queryTerm || "trade finance micro enterprise";
    const timer = setTimeout(() => {
      setIsRagSearching(true);
      queryRag(q, { topK: 4 })
        .then((res) => {
          setRagResults(res.results || []);
        })
        .catch((err) => {
          console.warn("RAG search error:", err);
          setRagResults([]);
        })
        .finally(() => setIsRagSearching(false));
    }, 350);

    return () => clearTimeout(timer);
  }, [search, activeFilter]);

  const handleDiscussRagChunk = (chunk: RagChunk) => {
    const title = chunk.metadata?.title || chunk.metadata?.filename || "Corpus Intelligence";
    dispatch({
      type: "SET_CHAT_DRAFT",
      draft: `I saw this verified intelligence on "${title}": "${chunk.content.slice(0, 140)}...". How should I apply this practically in my enterprise?`,
    });
    router.push("/chat");
  };

  const filtered = (insights ?? []).filter((item) => {
    if (search && !item.title.toLowerCase().includes(search.toLowerCase())) return false;
    if (activeFilter === "Audio") return item.isAudio;
    if (activeFilter === "Text") return !item.isAudio;
    return true;
  });
  const curated = filtered.slice(0, 2);
  const recommended = filtered.slice(2);

  const toggleFavorite = async (id: string) => {
    const isFav = libraryFavorites.has(id);
    dispatch({ type: "TOGGLE_LIBRARY_FAVORITE", id });
    try {
      await toggleInsightFavorite(id, !isFav);
    } catch (err) {
      console.warn("Could not sync favorite to backend:", err);
    }
  };

  return (
    <main className="pb-24 pt-md md:flex md:min-h-full md:gap-lg md:px-lg md:pb-lg md:pt-lg">
      {/* Desktop filter rail */}
      <aside className="hidden shrink-0 flex-col justify-between gap-lg lg:flex lg:w-64">
        <div className="flex flex-col gap-lg">
          <h3 className="flex items-center gap-sm font-title-md text-title-md text-on-surface">
            <Icon name="filter_list" className="text-primary" />
            Refine Library
          </h3>
          <div className="flex flex-col gap-xs">
            {FILTERS.map((f) => (
              <button
                key={f.label}
                onClick={() => setActiveFilter(f.label)}
                className={`flex items-center gap-md rounded-lg p-sm text-left font-body-md transition-colors ${
                  activeFilter === f.label
                    ? "bg-primary-container text-on-primary-container"
                    : "text-on-surface hover:bg-surface-container-low"
                }`}
              >
                <Icon name={f.icon} size={18} />
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Live RAG Corpus Status Card */}
        <div className="rounded-xl border border-primary/20 bg-primary-container/10 p-md text-xs">
          <div className="flex items-center gap-xs font-bold text-primary">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
            </span>
            RAG Knowledge Base
          </div>
          <p className="mt-1 text-[11px] leading-tight text-on-surface-variant">
            {ragStats?.documents?.total !== undefined
              ? `${ragStats.documents.total} docs indexed in ChromaDB`
              : "Hybrid BM25 + Vector Retrieval connected"}
          </p>
        </div>
      </aside>

      <div className="flex-1 space-y-lg px-margin-mobile md:px-0">
        <section className="relative">
          <label className="relative block">
          <span className="sr-only">Search insights, sectors, or tools</span>
          <span className="pointer-events-none absolute inset-y-0 left-md flex items-center text-on-surface-variant">
            <Icon name="search" />
          </span>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search insights, sectors, or tools..."
            className="h-12 w-full rounded border-none bg-surface-container pl-12 pr-md font-body-md text-body-md placeholder:text-on-surface-variant/60 focus:outline-none focus:ring-2 focus:ring-primary md:max-w-md"
          />
        </label>
        </section>

        {/* Mobile-only filter chips — same state as the desktop rail above. */}
        <section className="-mx-margin-mobile flex gap-sm overflow-x-auto px-margin-mobile py-xs lg:hidden">
          {FILTERS.map((f) => (
            <button
              key={f.label}
              onClick={() => setActiveFilter(f.label)}
              className={`flex items-center gap-xs whitespace-nowrap rounded-full px-md py-sm font-label-sm text-label-sm transition-colors ${
                activeFilter === f.label
                  ? "bg-primary-container text-on-primary-container shadow-sm"
                  : "bg-surface-container text-on-surface-variant hover:bg-surface-variant"
              }`}
            >
              {f.label}
              <Icon name={f.icon} size={16} />
            </button>
          ))}
        </section>
        {/* Grounded RAG Corpus Intelligence Section */}
        {(activeFilter === "RAG Corpus" || (search.trim().length > 0 && ragResults.length > 0) || isRagSearching) && (
          <section className="space-y-md animate-fadeIn">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-xs">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <Icon name="database" size={16} />
                </span>
                <h2 className="font-title-md text-title-md text-on-surface">
                  {activeFilter === "RAG Corpus" ? "RAG Knowledge Corpus" : "Grounded Corpus Intelligence"}
                </h2>
              </div>
              {isRagSearching && (
                <span className="flex items-center gap-xs text-xs text-primary font-medium">
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                  Searching vector index...
                </span>
              )}
            </div>

            {isRagSearching && ragResults.length === 0 ? (
              <div className="grid gap-md md:grid-cols-2">
                <Skeleton className="h-36 w-full rounded-xl" />
                <Skeleton className="h-36 w-full rounded-xl" />
              </div>
            ) : ragResults.length > 0 ? (
              <div className="grid gap-md md:grid-cols-2">
                {ragResults.map((chunk, idx) => {
                  const meta = chunk.metadata || {};
                  const matchPercent = Math.min(100, Math.round(chunk.score * 100));
                  return (
                    <div
                      key={chunk.chunk_id || idx}
                      className="flex flex-col justify-between rounded-xl border border-primary/30 bg-surface-container-low p-md transition-all hover:border-primary/60 hover:shadow-md"
                    >
                      <div>
                        <div className="flex items-start justify-between gap-xs">
                          <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-sm py-0.5 font-label-sm text-[10px] font-bold text-primary uppercase tracking-wide">
                            <Icon name="auto_stories" size={12} />
                            {meta.source_origin || "Verified Corpus"}
                          </span>
                          {matchPercent > 0 && (
                            <span className="rounded-full bg-secondary-container px-2 py-0.5 font-label-sm text-[10px] font-bold text-on-secondary-container">
                              {matchPercent}% Match
                            </span>
                          )}
                        </div>
                        <h3 className="mt-xs font-title-sm text-sm font-bold leading-snug text-on-surface">
                          {meta.title || meta.filename || "Enterprise Strategy Intelligence"}
                        </h3>
                        {meta.sector && (
                          <p className="mt-0.5 font-label-sm text-[11px] text-on-surface-variant">
                            Sector: {meta.sector} {meta.market ? `• Market: ${meta.market}` : ""}
                          </p>
                        )}
                        <p className="mt-xs line-clamp-3 rounded bg-surface/80 p-xs font-body-sm text-xs leading-relaxed text-on-surface-variant border border-outline-variant/10">
                          &ldquo;{chunk.content}&rdquo;
                        </p>
                      </div>

                      <div className="mt-md flex items-center justify-between border-t border-outline-variant/10 pt-xs">
                        <button
                          onClick={() => handleDiscussRagChunk(chunk)}
                          className="flex items-center gap-xs rounded-lg bg-primary/10 px-sm py-1 font-label-sm text-xs font-semibold text-primary transition-colors hover:bg-primary/20 active:scale-95"
                        >
                          <Icon name="chat" size={14} />
                          Discuss in Chat
                        </button>
                        <span className="font-label-sm text-[10px] text-on-surface-variant">
                          Method: {chunk.retrieval_method || "hybrid"}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-xl border border-outline-variant/20 bg-surface-container-low p-md text-center text-xs text-on-surface-variant">
                No matching RAG documents found for &ldquo;{search}&rdquo;. Try another term like &ldquo;pricing&rdquo;, &ldquo;loan&rdquo;, or &ldquo;savings&rdquo;.
              </div>
            )}
          </section>
        )}
        <section className="space-y-md">
          <h2 className="font-title-md text-title-md text-on-surface">Curated Insights</h2>
          <div className="md:grid md:grid-cols-2 md:gap-md md:space-y-0 xl:grid-cols-3">
            {insights === null
              ? Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-28 w-full rounded md:h-40" />)
              : curated.map((item) => (
                  <InsightCard
                    key={item.id}
                    item={item}
                    isFavorite={libraryFavorites.has(item.id)}
                    onToggleFavorite={() => toggleFavorite(item.id)}
                    onOpen={() => setSelectedItem(item)}
                  />
                ))}
          </div>
        </section>

        <section className="space-y-md">
          <div className="flex items-center justify-between">
            <h2 className="font-title-md text-title-md text-on-surface">Recommended for you</h2>
          </div>

          {/* Mobile: horizontal scroll cards. Desktop: same real data in the grid above. */}
          <div className="-mx-margin-mobile flex gap-md overflow-x-auto px-margin-mobile pb-sm md:hidden">
            {insights === null
              ? Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-40 w-44 shrink-0 rounded" />)
              : recommended.map((item, i) => (
                  <div
                    key={item.id}
                    onClick={() => setSelectedItem(item)}
                    className="w-44 shrink-0 cursor-pointer overflow-hidden rounded border border-outline-variant/30 bg-surface-container-low transition-all duration-300 hover:border-primary/40 active:scale-[0.98]"
                  >
                    <div className="relative flex h-24 items-center justify-center bg-gradient-to-br from-primary-container to-secondary-container">
                      <Icon name={i === 0 ? "storefront" : "agriculture"} filled size={32} className="text-on-primary-container" />
                      <span className="absolute left-2 top-2 rounded-full bg-inverse-surface/80 px-sm py-[2px] text-[10px] font-bold text-inverse-on-surface">
                        {i === 0 ? "New" : "Popular"}
                      </span>
                    </div>
                    <div className="p-sm">
                      <p className="font-label-sm text-[11px] font-bold uppercase text-primary">{item.category}</p>
                      <p className="mt-xs font-body-md text-[13px] font-semibold leading-tight text-on-surface">
                        {item.title}
                      </p>
                    </div>
                  </div>
                ))}
          </div>
          <div className="hidden md:grid md:grid-cols-2 md:gap-md xl:grid-cols-3">
            {insights === null
              ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-40 w-full rounded-xl" />)
              : recommended.map((item) => (
                  <InsightCard
                    key={item.id}
                    item={item}
                    isFavorite={libraryFavorites.has(item.id)}
                    onToggleFavorite={() => toggleFavorite(item.id)}
                    onOpen={() => setSelectedItem(item)}
                  />
                ))}
          </div>
        </section>
      </div>

      {/* Interactive Reader & Audio Player Modal */}
      <InsightReaderModal
        item={selectedItem}
        isFavorite={selectedItem ? libraryFavorites.has(selectedItem.id) : false}
        onClose={() => setSelectedItem(null)}
        onToggleFavorite={() => selectedItem && toggleFavorite(selectedItem.id)}
      />
    </main>
  );
}
