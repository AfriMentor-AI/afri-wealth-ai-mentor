"use client";

import { useEffect, useMemo, useState } from "react";
import { Icon } from "@/components/Icon";
import { fetchInsights, recordProgressAction, setInsightFavorited } from "@/lib/api";
import type { InsightItem } from "@/lib/types";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAppDispatch, useAppState } from "@/lib/store";

function filterIcon(label: string): string {
  if (label === "All") return "apps";
  if (label === "Audio") return "headphones";
  if (label === "Text") return "description";
  return "sell";
}

// Card shared by the mobile "Curated Insights" list, the mobile "Recommended"
// horizontal scroller, and the desktop grid — same InsightItem data and same
// favorite/expand behavior everywhere, no separate less-featured mobile card.
function InsightCard({
  item,
  isFavorite,
  onToggleFavorite,
  isExpanded,
  onToggleExpand,
  compact = false,
}: {
  item: InsightItem;
  isFavorite: boolean;
  onToggleFavorite: () => void;
  isExpanded: boolean;
  onToggleExpand: () => void;
  compact?: boolean;
}) {
  return (
    <div
      className={`group relative flex flex-col gap-sm rounded border border-outline-variant/30 bg-surface-container-low p-md transition-all duration-300 hover:border-primary/30 md:rounded-xl md:p-lg ${
        compact ? "w-44 shrink-0 p-sm md:w-44 md:rounded md:p-sm" : ""
      }`}
    >
      <div className="flex items-start justify-between gap-sm">
        <div className="flex min-w-0 flex-col gap-xs">
          <span className="inline-flex w-fit items-center gap-xs rounded-full bg-secondary-container px-sm py-1 text-[10px] font-bold uppercase tracking-wider text-on-secondary-container">
            <Icon name="sell" size={14} />
            {item.category}
          </span>
          <h3 className={`font-title-md pt-xs leading-tight text-on-surface ${compact ? "text-[13px] font-semibold" : "text-title-md"}`}>
            {item.title}
          </h3>
        </div>
        <button
          aria-label={isExpanded ? "Collapse" : item.isAudio ? "Play audio insight" : "Read article"}
          onClick={onToggleExpand}
          className="tap-target shrink-0 rounded-full bg-primary/10 p-sm text-primary"
        >
          <Icon name={isExpanded ? "expand_less" : item.isAudio ? "play_circle" : "menu_book"} filled={item.isAudio && !isExpanded} />
        </button>
      </div>

      {!compact && !isExpanded && (
        <p className="font-body-md text-body-md text-on-surface-variant line-clamp-2">{item.summary}</p>
      )}

      {isExpanded && (
        <div className="rounded bg-surface-container p-sm">
          <p className="font-body-md text-body-md text-on-surface">{item.summary}</p>
          {item.mediaUrl && item.isAudio && (
            <audio controls src={item.mediaUrl} className="mt-sm w-full" />
          )}
          {item.mediaUrl && !item.isAudio && (
            <a
              href={item.mediaUrl}
              target="_blank"
              rel="noreferrer"
              className="mt-sm inline-flex items-center gap-xs font-label-sm text-label-sm text-primary underline"
            >
              Open full article
              <Icon name="open_in_new" size={14} />
            </a>
          )}
        </div>
      )}

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
          onClick={onToggleFavorite}
          className="tap-target ml-auto flex items-center justify-center rounded-full text-primary"
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
  const [activeFilter, setActiveFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [readIds, setReadIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchInsights().then((items) => {
      setInsights(items);
      dispatch({ type: "SET_LIBRARY_FAVORITES", ids: items.filter((i) => i.isFavorited).map((i) => i.id) });
    });
  }, [dispatch]);

  const categories = useMemo(
    () => Array.from(new Set((insights ?? []).map((i) => i.category))).sort(),
    [insights]
  );
  const filterOptions = useMemo(() => ["All", ...categories, "Audio", "Text"], [categories]);

  const filtered = (insights ?? []).filter((item) => {
    if (search) {
      const q = search.toLowerCase();
      if (!item.title.toLowerCase().includes(q) && !item.summary.toLowerCase().includes(q)) return false;
    }
    if (activeFilter === "All") return true;
    if (activeFilter === "Audio") return item.isAudio;
    if (activeFilter === "Text") return !item.isAudio;
    return item.category === activeFilter;
  });
  const curated = filtered.slice(0, 2);
  const recommended = filtered.slice(2);

  async function toggleFavorite(id: string) {
    const wasFavorite = libraryFavorites.has(id);
    dispatch({ type: "TOGGLE_LIBRARY_FAVORITE", id });
    try {
      await setInsightFavorited(id, !wasFavorite);
    } catch (error) {
      console.error("Failed to update favorite:", error);
      dispatch({ type: "TOGGLE_LIBRARY_FAVORITE", id });
    }
  }

  function toggleExpand(id: string) {
    const willExpand = expandedId !== id;
    setExpandedId(willExpand ? id : null);
    if (willExpand && !readIds.has(id)) {
      setReadIds((prev) => new Set(prev).add(id));
      recordProgressAction("insight_completed").catch((error) =>
        console.error("Failed to record insight_completed action:", error)
      );
    }
  }

  return (
    <main className="pb-24 pt-md md:flex md:min-h-full md:gap-lg md:px-lg md:pb-lg md:pt-lg">
      {/* Desktop filter rail — dynamic categories drawn from the real fetched
          catalog (Pricing/Savings/Bookkeeping/... today), not a fixed
          Sector/Topic taxonomy the data doesn't actually have. */}
      <aside className="hidden shrink-0 flex-col gap-lg lg:flex lg:w-64">
        <h3 className="flex items-center gap-sm font-title-md text-title-md text-on-surface">
          <Icon name="filter_list" className="text-primary" />
          Refine Library
        </h3>
        <div className="flex flex-col gap-xs">
          {filterOptions.map((f) => (
            <button
              key={f}
              onClick={() => setActiveFilter(f)}
              className={`flex items-center gap-md rounded-lg p-sm text-left font-body-md transition-colors ${
                activeFilter === f
                  ? "bg-primary-container text-on-primary-container"
                  : "text-on-surface hover:bg-surface-container-low"
              }`}
            >
              <Icon name={filterIcon(f)} size={18} />
              {f}
            </button>
          ))}
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
          {filterOptions.map((f) => (
            <button
              key={f}
              onClick={() => setActiveFilter(f)}
              className={`flex items-center gap-xs whitespace-nowrap rounded-full px-md py-sm font-label-sm text-label-sm transition-colors ${
                activeFilter === f
                  ? "bg-primary-container text-on-primary-container shadow-sm"
                  : "bg-surface-container text-on-surface-variant hover:bg-surface-variant"
              }`}
            >
              {f}
              <Icon name={filterIcon(f)} size={16} />
            </button>
          ))}
        </section>

        <section className="space-y-md">
          <h2 className="font-title-md text-title-md text-on-surface">Curated Insights</h2>
          <div className="md:grid md:grid-cols-2 md:gap-md md:space-y-0 xl:grid-cols-3">
            {insights === null ? (
              Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-28 w-full rounded md:h-40" />)
            ) : curated.length === 0 ? (
              <p className="font-body-md text-on-surface-variant">No insights match this filter yet.</p>
            ) : (
              curated.map((item) => (
                <InsightCard
                  key={item.id}
                  item={item}
                  isFavorite={libraryFavorites.has(item.id)}
                  onToggleFavorite={() => toggleFavorite(item.id)}
                  isExpanded={expandedId === item.id}
                  onToggleExpand={() => toggleExpand(item.id)}
                />
              ))
            )}
          </div>
        </section>

        <section className="space-y-md">
          <div className="flex items-center justify-between">
            <h2 className="font-title-md text-title-md text-on-surface">Recommended for you</h2>
          </div>

          {/* Mobile: horizontal scroll, reusing the same InsightCard (real
              favorite + play/read) as the desktop grid below — no separate
              stripped-down mobile-only card. */}
          <div className="-mx-margin-mobile flex gap-md overflow-x-auto px-margin-mobile pb-sm md:hidden">
            {insights === null
              ? Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-40 w-44 shrink-0 rounded" />)
              : recommended.map((item) => (
                  <InsightCard
                    key={item.id}
                    item={item}
                    compact
                    isFavorite={libraryFavorites.has(item.id)}
                    onToggleFavorite={() => toggleFavorite(item.id)}
                    isExpanded={expandedId === item.id}
                    onToggleExpand={() => toggleExpand(item.id)}
                  />
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
                    isExpanded={expandedId === item.id}
                    onToggleExpand={() => toggleExpand(item.id)}
                  />
                ))}
          </div>
        </section>
      </div>
    </main>
  );
}
