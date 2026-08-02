"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { fetchInsights } from "@/lib/api";
import type { InsightItem } from "@/lib/types";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAppDispatch, useAppState } from "@/lib/store";

const FILTERS = [
  { label: "Sector", icon: "expand_more" },
  { label: "Topic", icon: "expand_more" },
  { label: "Audio", icon: "headphones" },
  { label: "Text", icon: "description" },
];

export default function InsightLibraryPage() {
  const { libraryFavorites } = useAppState();
  const dispatch = useAppDispatch();
  const [insights, setInsights] = useState<InsightItem[] | null>(null);
  const [activeFilter, setActiveFilter] = useState("Sector");

  useEffect(() => {
    fetchInsights().then(setInsights);
  }, []);

  const curated = insights?.slice(0, 2) ?? [];
  const recommended = insights?.slice(2) ?? [];

  return (
    <main className="space-y-lg px-margin-mobile pb-24 pt-md">
      <section className="relative">
        <span className="pointer-events-none absolute inset-y-0 left-md flex items-center text-on-surface-variant">
          <Icon name="search" />
        </span>
        <input
          type="text"
          placeholder="Search insights, sectors, or tools..."
          className="h-12 w-full rounded border-none bg-surface-container pl-12 pr-md font-body-md text-body-md placeholder:text-on-surface-variant/60 focus:outline-none focus:ring-2 focus:ring-primary"
        />
      </section>

      <section className="-mx-margin-mobile flex gap-sm overflow-x-auto px-margin-mobile py-xs">
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
        {insights === null
          ? Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-28 w-full rounded" />)
          : curated.map((item) => (
              <div
                key={item.id}
                className="group relative flex flex-col gap-sm rounded border border-outline-variant/30 bg-surface-container-low p-md transition-all duration-300 hover:border-primary/30"
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
                    aria-label={item.isAudio ? "Play audio insight" : "Read article"}
                    className="rounded-full bg-primary/10 p-sm text-primary"
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
                    aria-label={libraryFavorites.has(item.id) ? "Remove from favorites" : "Save to favorites"}
                    onClick={() => dispatch({ type: "TOGGLE_LIBRARY_FAVORITE", id: item.id })}
                    className="tap-target ml-auto flex items-center justify-center rounded-full text-primary"
                  >
                    <Icon name="favorite" filled={libraryFavorites.has(item.id)} size={18} />
                  </button>
                </div>
              </div>
            ))}
      </section>

      <section className="space-y-md">
        <div className="flex items-center justify-between">
          <h2 className="font-title-md text-title-md text-on-surface">Recommended for you</h2>
          <button className="tap-target font-label-sm text-label-sm text-primary">View all</button>
        </div>
        <div className="-mx-margin-mobile flex gap-md overflow-x-auto px-margin-mobile pb-sm">
          {insights === null
            ? Array.from({ length: 2 }).map((_, i) => <Skeleton key={i} className="h-40 w-44 shrink-0 rounded" />)
            : recommended.map((item, i) => (
                <div key={item.id} className="w-44 shrink-0 overflow-hidden rounded border border-outline-variant/30 bg-surface-container-low">
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
      </section>
    </main>
  );
}
