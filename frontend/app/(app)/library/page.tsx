"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { fetchInsights, toggleInsightFavorite, queryRag, fetchRagStats } from "@/lib/api";
import type { InsightItem, RagChunk, RagCorpusStats } from "@/lib/types";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAppDispatch, useAppState } from "@/lib/store";
import { InsightReaderModal } from "@/components/InsightReaderModal";
import { NotificationPopover } from "@/components/NotificationPopover";

const FILTERS = [
  { label: "Sector", icon: "expand_more" },
  { label: "Topic", icon: "expand_more" },
  { label: "Audio", icon: "headphones" },
  { label: "Text", icon: "description" },
  { label: "RAG Corpus", icon: "database" },
];

const CARD_ART = [
  {
    image:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuAFseUcS0GHZY8TrW2_-IIfdTaltL9yULdhzDmDusWk7CIme3S5mYIxBt9Up7J1hnw6GeqfBjkQu2kDyMDK8Mm-zVRlUM6V0w64Psx1zsheJ80MG9p0nIJf8kgTCadXhpUlaDZoERCap9qC6bRX-_rzR9T7GpP6KdKaFj7hkMqbqqcnS1U9uIt-yGEpqRpuT1koCxOAeIOgVVexoQUdY7qpBwq5MEe2FnjVImRB4OGrEpSMAwp0a6Hv2A",
    label: "African Origin",
    icon: "group",
    note: "Shared by 40+ Mentors in your sector",
  },
  {
    image:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuCVZeh65H3-mwGuYfjCq9_AoXGcbxm8t4v6sCK_9PujExnOeHkprSrj1NpXi-Lsygxjh_lRp-ODoQBZ8TN5s4SY92FcGJ4QoQVpMGAq2BdidE3n7Cy8gLNK9rBCDxbY0GwrxzZjCmzBLjjBHhDmi2dwViq_WFoNE5x7aUoBH01FZjUIdDrh7LFfn7J5JHlUm4vCkyXYLbnIdD-6-e3LcB4pSKobfwzv3UA0b_NZoL02mABYaxhUBOsB-g",
    label: "African Origin",
    icon: "history_edu",
    note: "Recommended by CHIOMA",
  },
  {
    image:
      "https://lh3.googleusercontent.com/aida-public/AB6AXuAlVqaxkhZRGgLUxqZPPwO9Mvf9XC8tN-7yGghROPeA2j-daXAjGoPdMC0jhJWIIR8PnIXhwZIoBFNxoZ2mX6r-zYhclluftn9oyxWs7qxzF268RUstR7nfipUgC745YYeclEAuh5msL0tUFbjGLNwJQiQkBAOoHRu4J9XD42BkfU8X0hQGijSBySlgtO70cYRuodH27kQ42RjS9yzEwj4fjMIKtkPbgG5zKVicOk7dl_rZFh9fRTTPQ",
    label: "African Origin",
    icon: "eco",
    note: "Top trending in Agri-tech",
  },
];

// Card shared by the mobile "Curated Insights" list and the desktop grid —
// same InsightItem data, no fabricated titles/stats beyond what's real here.
function InsightCard({
  item,
  isFavorite,
  onToggleFavorite,
  onOpen,
  artIndex = 0,
}: Readonly<{
  item: InsightItem;
  isFavorite: boolean;
  onToggleFavorite: () => void;
  onOpen: () => void;
  artIndex?: number;
}>) {
  const art = CARD_ART[artIndex % CARD_ART.length];
  return (
    <div
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") onOpen();
      }}
      role="button"
      tabIndex={0}
      className="group relative flex cursor-pointer flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container transition-all duration-300 hover:border-primary hover:shadow-lg active:scale-[0.99]"
    >
      <div className="relative h-44 overflow-hidden">
        <img src={art.image} alt="" className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" />
        <span className="absolute left-md top-md inline-flex items-center gap-xs rounded-lg border border-primary/20 bg-surface/90 px-sm py-1 text-[10px] font-bold uppercase tracking-wider text-primary backdrop-blur-sm">
          <Icon name="verified" filled size={14} />
          {art.label}
        </span>
        {item.isAudio && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onOpen();
            }}
            aria-label="Play audio insight"
            className="absolute bottom-md right-md flex h-10 w-10 items-center justify-center rounded-full bg-primary text-on-primary shadow-lg transition-transform hover:scale-110 active:scale-95"
          >
            <Icon name="play_arrow" filled />
          </button>
        )}
      </div>
      <div className="flex flex-1 flex-col p-lg">
        <div className="flex items-start justify-between gap-sm">
          <span className="font-label-sm text-[11px] uppercase tracking-widest text-on-surface-variant">
            {item.isAudio ? "Audio Insight" : "Article"} • {item.durationMinutes}m {item.isAudio ? "" : "Read"}
          </span>
          <button
            aria-label={isFavorite ? "Remove from favorites" : "Save to favorites"}
            onClick={(e) => {
              e.stopPropagation();
              onToggleFavorite();
            }}
            className="tap-target -mr-sm -mt-sm flex items-center justify-center rounded-full text-on-surface-variant transition-colors hover:text-primary"
          >
            <Icon name="bookmark" filled={isFavorite} size={20} />
          </button>
        </div>
        <h3 className="mt-sm line-clamp-2 font-title-md text-title-md leading-tight text-on-surface">{item.title}</h3>
        <p className="mt-md line-clamp-3 font-body-md text-sm leading-relaxed text-on-surface-variant">{item.summary}</p>
        <div className="mt-auto flex items-center gap-sm border-t border-outline-variant/30 pt-md">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-secondary-container text-on-secondary-container">
            <Icon name={art.icon} size={14} />
          </span>
          <span className="text-[12px] text-on-surface-variant">{art.note}</span>
        </div>
      </div>
    </div>
  );
}

export default function InsightLibraryPage() {
  const router = useRouter();
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
  const curated = filtered.slice(0, 3);
  const recommended = filtered.slice(3);

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
    <main className="min-h-full bg-surface pb-24 lg:pb-lg">
      <header className="hidden h-16 items-center justify-between border-b border-outline-variant bg-surface px-lg lg:flex">
        <h1 className="font-headline-lg text-headline-lg text-primary">AfriMentor AI</h1>
        <label className="relative w-80 xl:w-96">
          <span className="sr-only">Search insights, methods, or wisdom</span>
          <Icon name="search" size={20} className="pointer-events-none absolute left-md top-1/2 -translate-y-1/2 text-on-surface-variant" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search insights, methods, or wisdom..."
            className="h-10 w-full rounded-full border-0 bg-surface-container-low pl-11 pr-md text-sm text-on-surface placeholder:text-on-surface-variant/70 focus:ring-2 focus:ring-primary"
          />
        </label>
        <div className="flex items-center gap-md text-on-surface-variant">
          <NotificationPopover />
          <Icon name="settings" />
          <img src="/images/chioma-avatar.png" alt="Chioma" className="h-8 w-8 rounded-full border-2 border-primary object-cover" />
        </div>
      </header>

      <div className="flex flex-col lg:flex-row">
        <aside className="hidden shrink-0 flex-col justify-between border-r border-outline-variant bg-surface-container-low p-lg lg:flex lg:min-h-[calc(100vh-4rem)] lg:w-72">
          <div>
            <h2 className="mb-lg flex items-center gap-sm font-title-md text-title-md text-on-surface">
              <Icon name="filter_list" className="text-primary" />
              Refine Library
            </h2>
            <div className="space-y-lg">
              <div>
                <p className="mb-sm font-label-sm text-[11px] uppercase tracking-widest text-on-surface-variant">Sector</p>
                <div className="space-y-xs">
                  {["Agriculture & Agri-tech", "Creative Economies", "Renewable Energy", "Social Enterprise"].map((sector, index) => (
                    <label key={sector} className="flex cursor-pointer items-center gap-md rounded-lg p-sm text-sm transition-colors hover:bg-surface-variant">
                      <input type="checkbox" defaultChecked={index === 0} className="rounded border-outline text-primary focus:ring-primary" />
                      {sector}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-sm font-label-sm text-[11px] uppercase tracking-widest text-on-surface-variant">Topic</p>
                <div className="flex flex-wrap gap-xs">
                  {["Sustainability", "Community Trust", "Financial Literacy", "Leadership"].map((topic) => (
                    <button key={topic} className="rounded-full border border-outline-variant px-md py-xs text-[11px] transition-colors hover:bg-primary-container hover:text-on-primary-container">
                      {topic}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <p className="mb-sm font-label-sm text-[11px] uppercase tracking-widest text-on-surface-variant">Content Type</p>
                <div className="grid grid-cols-2 gap-sm">
                  {[
                    ["Audio", "mic", "Audio"],
                    ["Text", "article", "Articles"],
                  ].map(([label, icon, text]) => (
                    <button key={label} onClick={() => setActiveFilter(label)} className="flex flex-col items-center gap-xs rounded-xl border border-outline-variant bg-surface p-md text-[11px] transition-colors hover:border-primary">
                      <Icon name={icon} className="text-primary" />
                      {text}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
          <div className="rounded-xl border border-secondary/20 bg-secondary-container p-md text-on-secondary-container">
            <div className="mb-xs flex items-center gap-sm font-label-sm uppercase tracking-wider text-secondary"><Icon name="verified_user" size={18} /> Sankofa Trust</div>
            <p className="text-xs leading-relaxed">All materials are verified for cultural relevance and pan-African origin.</p>
            <p className="mt-sm text-[11px] font-semibold">{ragStats?.documents?.total ?? "Hybrid"} {ragStats?.documents?.total !== undefined ? "documents indexed" : "retrieval connected"}</p>
          </div>
        </aside>

        <div className="min-w-0 flex-1 space-y-xl px-margin-mobile py-md md:px-lg lg:p-lg">
          <section className="relative lg:hidden">
            <label className="relative block">
              <span className="sr-only">Search insights, sectors, or tools</span>
              <Icon name="search" className="pointer-events-none absolute left-md top-1/2 -translate-y-1/2 text-on-surface-variant" />
              <input type="text" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search insights, sectors, or tools..." className="h-12 w-full rounded border-0 bg-surface-container pl-12 pr-md text-sm focus:ring-2 focus:ring-primary" />
            </label>
          </section>

          <section className="-mx-margin-mobile flex gap-sm overflow-x-auto px-margin-mobile py-xs lg:hidden">
            {FILTERS.map((f) => (
              <button key={f.label} onClick={() => setActiveFilter(f.label)} className={`flex items-center gap-xs whitespace-nowrap rounded-full px-md py-sm text-label-sm transition-colors ${activeFilter === f.label ? "bg-primary-container text-on-primary-container shadow-sm" : "bg-surface-container text-on-surface-variant"}`}>
                {f.label}<Icon name={f.icon} size={16} />
              </button>
            ))}
          </section>

          <section className="relative overflow-hidden rounded-2xl border border-primary-container/20 bg-primary-container/10 p-lg">
            <div className="absolute inset-0 opacity-[0.04]" style={{ backgroundImage: "radial-gradient(circle, currentColor 1px, transparent 1px)", backgroundSize: "18px 18px" }} />
            <div className="relative flex flex-col items-center gap-lg md:flex-row">
              <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-primary-container text-on-primary-container"><Icon name="psychology" size={32} /></div>
              <div className="flex-1">
                <div className="mb-xs flex flex-wrap items-center gap-sm"><h2 className="font-title-md text-title-md text-primary">Recommended for you</h2><span className="rounded bg-primary px-sm py-1 text-[10px] font-bold uppercase tracking-tight text-on-primary">AI Reasoning by CHIOMA</span></div>
                <p className="text-sm leading-relaxed text-on-surface-variant">Based on your recent progress in <strong className="text-primary">Community Cooperative Finance</strong>, I&apos;ve curated these insights to help you navigate trust-based growth in urban West African markets.</p>
              </div>
              <button onClick={() => document.getElementById("browse-insights")?.scrollIntoView({ behavior: "smooth" })} className="shrink-0 rounded-full bg-primary px-lg py-md text-sm font-semibold text-on-primary transition-opacity hover:opacity-90">Explore Curated Set</button>
            </div>
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
                <span className="flex items-center gap-xs text-xs font-medium text-primary">
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                  {" Searching vector index..."}
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
        <section id="browse-insights" className="space-y-md">
          <h2 className="font-title-md text-title-md text-on-surface">Curated Insights</h2>
          <div className="grid gap-lg md:grid-cols-2 md:space-y-0 xl:grid-cols-3">
            {insights === null
              ? Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-96 w-full rounded-xl" />)
              : curated.map((item, index) => (
                  <InsightCard
                    key={item.id}
                    item={item}
                    artIndex={index}
                    isFavorite={libraryFavorites.has(item.id)}
                    onToggleFavorite={() => toggleFavorite(item.id)}
                    onOpen={() => setSelectedItem(item)}
                  />
                ))}
          </div>
        </section>

        <section className="space-y-md">
          <div className="flex items-center justify-between">
            <h2 className="font-headline-lg text-headline-lg text-on-surface">Browse All Insights</h2>
          </div>

          {/* Mobile: horizontal scroll cards. Desktop: same real data in the grid above. */}
          <div className="-mx-margin-mobile flex gap-md overflow-x-auto px-margin-mobile pb-sm md:hidden">
            {insights === null
              ? Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-40 w-44 shrink-0 rounded" />)
              : recommended.map((item, i) => (
                  <div
                    key={item.id}
                    onClick={() => setSelectedItem(item)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") setSelectedItem(item);
                    }}
                    role="button"
                    tabIndex={0}
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
                : recommended.map((item, index) => (
                  <InsightCard
                    key={item.id}
                    item={item}
                  artIndex={index + curated.length}
                    isFavorite={libraryFavorites.has(item.id)}
                    onToggleFavorite={() => toggleFavorite(item.id)}
                    onOpen={() => setSelectedItem(item)}
                  />
                ))}
          </div>
        </section>
        </div>
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
