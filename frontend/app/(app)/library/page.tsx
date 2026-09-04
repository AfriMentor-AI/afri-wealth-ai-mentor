"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { fetchInsights, toggleInsightFavorite } from "@/lib/api";
import type { InsightItem } from "@/lib/types";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAppDispatch, useAppState } from "@/lib/store";
import { InsightReaderModal } from "@/components/InsightReaderModal";

const FILTERS = [
  { label: "Sector", icon: "expand_more" },
  { label: "Topic", icon: "expand_more" },
  { label: "Audio", icon: "headphones" },
  { label: "Text", icon: "description" },
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


  useEffect(() => {
    fetchInsights().then(setInsights);
  }, []);

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
      {/* Desktop filter rail — reuses the same FILTERS/activeFilter state the
          mobile chip row uses, not the mockup's hardcoded checkbox list
          (those sector/topic categories don't exist on InsightItem). */}
      <aside className="hidden shrink-0 flex-col gap-lg lg:flex lg:w-64">
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

