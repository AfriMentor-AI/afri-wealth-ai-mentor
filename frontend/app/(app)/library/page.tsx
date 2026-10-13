"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { AppFrame, KenteStrip } from "@/components/shell/AppSidebar";
import { InsightReaderModal } from "@/components/InsightReaderModal";
import { fetchInsights, toggleInsightFavorite, queryRag, fetchRagStats } from "@/lib/api";
import type { InsightItem, RagChunk, RagCorpusStats } from "@/lib/types";
import { useAppDispatch, useAppState } from "@/lib/store";
import { MENTORS, mentorFor } from "@/lib/mentors";
import { img } from "@/lib/stitchImages";

const ART = Object.values(MENTORS).map((m) => m.portrait);
const TOP = ["Sector", "Audio", "Text", "RAG Corpus"] as const;
const SECTORS = ["Agriculture & Agri-tech", "Creative Economies", "Renewable Energy", "Social Enterprise"];
const TOPICS = ["Sustainability", "Community Trust", "Financial Literacy", "Leadership"];
const STRIPE = ["bg-persona-market-queen", "bg-persona-tech-founder", "bg-persona-trader", "bg-persona-rural-hustler", "bg-persona-creative"];

function Thumb({ item, i, className }: { item: InsightItem; i: number; className: string }) {
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={item.thumbnailUrl || img(ART[i % ART.length])} alt="" loading="lazy" onError={(e) => { (e.currentTarget as HTMLImageElement).src = img(ART[i % ART.length]); }} className={className} />;
}

function Card({ item, i, fav, onFav, onOpen }: { item: InsightItem; i: number; fav: boolean; onFav: () => void; onOpen: () => void }) {
  return (
    <article onClick={onOpen} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), onOpen())} role="button" tabIndex={0}
      className="group relative flex cursor-pointer flex-col overflow-hidden rounded-3xl border border-outline-variant bg-surface-container-lowest p-5 shadow-sm transition-all hover:shadow-lg focus-visible:ring-2 focus-visible:ring-primary">
      <span className={`absolute inset-x-0 top-0 h-1.5 ${STRIPE[i % STRIPE.length]}`} />
      <div className="mt-1 flex items-center justify-between gap-2">
        <span className="rounded-full bg-surface-container-low px-3 py-1 font-eyebrow text-[10px] uppercase text-primary">{item.category}</span>
        <button type="button" aria-label={fav ? "Remove from favorites" : "Save to favorites"} onClick={(e) => { e.stopPropagation(); onFav(); }} className="flex h-9 w-9 items-center justify-center rounded-full text-on-surface-variant hover:text-primary"><Icon name="bookmark" filled={fav} size={22} /></button>
      </div>
      <div className="mt-3 flex gap-4">
        <Thumb item={item} i={i} className="h-20 w-20 shrink-0 rounded-xl object-cover" />
        <h3 className="line-clamp-3 font-title-md text-[20px] leading-7 text-on-surface">{item.title}</h3>
      </div>
      <p className="mt-3 line-clamp-3 font-body-md text-[15px] leading-6 text-on-surface-variant">{item.summary}</p>
      <div className="mt-auto flex items-center justify-between border-t border-outline-variant/50 pt-4 mt-4">
        <span className="flex items-center gap-1 font-caption text-caption text-on-surface-variant"><Icon name="schedule" size={14} /> {item.durationMinutes} min {item.isAudio ? "listen" : "read"}</span>
        <span className="flex items-center gap-1 rounded-full bg-surface-container-low px-3 py-1 font-label-sm text-label-sm text-primary"><Icon name={item.isAudio ? "play_arrow" : "menu_book"} size={16} filled={item.isAudio} /> {item.isAudio ? "Audio" : "Read"}</span>
      </div>
    </article>
  );
}

export default function LibraryPage() {
  const router = useRouter();
  const { libraryFavorites, profile, selectedPersona } = useAppState();
  const dispatch = useAppDispatch();
  const mentor = mentorFor(selectedPersona);
  const [insights, setInsights] = useState<InsightItem[] | null>(null);
  const [selected, setSelected] = useState<InsightItem | null>(null);
  const [filter, setFilter] = useState<string>("Sector");
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState<string | null>(null);
  const [rag, setRag] = useState<RagChunk[]>([]);
  const [ragBusy, setRagBusy] = useState(false);
  const [stats, setStats] = useState<RagCorpusStats | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    fetchInsights().then(setInsights).catch(() => { setInsights([]); setLoadError(true); });
    fetchRagStats().then(setStats).catch(() => {});
  }, []);

  useEffect(() => {
    const term = search.trim();
    if (!term && filter !== "RAG Corpus") { setRag([]); return; }
    const t = setTimeout(() => {
      setRagBusy(true);
      queryRag(term || "trade finance micro enterprise", { topK: 4 }).then((r) => setRag(r.results || [])).catch(() => setRag([])).finally(() => setRagBusy(false));
    }, 350);
    return () => clearTimeout(t);
  }, [search, filter]);

  const discuss = (c: RagChunk) => {
    const title = c.metadata?.title || c.metadata?.filename || "Corpus Intelligence";
    dispatch({ type: "SET_CHAT_DRAFT", draft: `I saw this verified intelligence on "${title}": "${c.content.slice(0, 140)}...". How should I apply this practically in my enterprise?` });
    router.push("/chat");
  };

  const filtered = useMemo(() => (insights ?? []).filter((it) => {
    if (search) {
      const q = search.toLowerCase();
      if (!it.title.toLowerCase().includes(q) && !it.summary.toLowerCase().includes(q) && !it.category.toLowerCase().includes(q)) return false;
    }
    if (sector) {
      const sec = sector.toLowerCase(), cat = it.category.toLowerCase();
      if (!(cat.includes(sec) || sec.includes(cat) || (sec.includes("agri") && (cat.includes("agri") || cat.includes("pricing") || cat.includes("sector"))))) return false;
    }
    if (filter === "Audio") return it.isAudio;
    if (filter === "Text") return !it.isAudio;
    return true;
  }), [insights, search, sector, filter]);

  const featured = filtered[0];
  const rest = filtered.slice(1);

  const toggleFav = async (id: string) => {
    const was = libraryFavorites.has(id);
    dispatch({ type: "TOGGLE_LIBRARY_FAVORITE", id });
    try { await toggleInsightFavorite(id, !was); } catch (e) { console.warn("Could not sync favorite to backend:", e); }
  };

  const chip = (on: boolean) => `whitespace-nowrap rounded-full px-4 py-2 font-label-sm text-label-sm transition-colors ${on ? "bg-primary text-on-primary" : "bg-surface-container-low text-on-surface hover:bg-surface-container"}`;

  return (
    <AppFrame title="Library">
      <KenteStrip />
      <div className="mx-auto max-w-6xl px-5 pb-16 pt-6 md:px-10 md:pt-10">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="font-eyebrow text-eyebrow uppercase text-on-surface-variant"><span className="text-sunburst-gold">●</span> Elder archive · Trade corridors</p>
            <h1 className="mt-2 font-headline-xl-mobile text-headline-xl-mobile text-on-surface md:font-headline-xl md:text-[48px] md:leading-[54px]">Library &amp; ancestral playbooks</h1>
            <p className="mt-2 max-w-2xl font-body-lg text-body-lg text-on-surface-variant">Verified frameworks, pricing lore and battle-tested merchant playbooks across African trade corridors.</p>
          </div>
          <span className="flex items-center gap-2 rounded-full border border-outline-variant bg-surface-container-lowest px-4 py-2 font-label-sm text-label-sm text-primary"><Icon name="verified" size={18} /> {stats?.documents?.total !== undefined ? `${stats.documents.total} documents indexed` : "Council verified lore"}</span>
        </header>

        <label className="relative mt-6 block">
          <span className="sr-only">Search insights, methods or guild wisdom</span>
          <Icon name="search" className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search insights, methods, or guild wisdom (e.g. susu buffers, FX hedge)…" className="h-14 w-full rounded-2xl border border-outline-variant bg-surface-container-lowest pl-12 pr-4 font-body-md text-body-md text-on-surface outline-none placeholder:text-on-surface-variant/60 focus:border-primary focus:ring-2 focus:ring-primary/20" />
        </label>

        <div className="-mx-5 mt-4 flex gap-2 overflow-x-auto px-5 pb-1 md:mx-0 md:flex-wrap md:px-0">
          {TOP.map((f) => <button key={f} type="button" onClick={() => setFilter(f)} className={chip(filter === f)}>{f === "Sector" ? "All playbooks" : f === "Text" ? "Articles" : f}</button>)}
          <span className="mx-1 hidden w-px bg-outline-variant md:block" />
          {SECTORS.map((s) => <button key={s} type="button" onClick={() => setSector(sector === s ? null : s)} className={chip(sector === s)}>{s}</button>)}
          {TOPICS.map((t) => <button key={t} type="button" onClick={() => setSearch(search.toLowerCase() === t.toLowerCase() ? "" : t)} className={chip(search.toLowerCase() === t.toLowerCase())}>{t}</button>)}
        </div>

        {(filter === "RAG Corpus" || ragBusy || (search.trim() && rag.length > 0)) && (
          <section className="mt-8">
            <div className="flex items-center justify-between">
              <h2 className="flex items-center gap-2 font-title-md text-title-md text-on-surface"><Icon name="database" className="text-primary" /> {filter === "RAG Corpus" ? "Knowledge corpus" : "Grounded corpus intelligence"}</h2>
              {ragBusy && <span className="flex items-center gap-2 font-caption text-caption text-primary"><span className="h-3 w-3 animate-spin rounded-full border-2 border-primary border-t-transparent" /> Searching…</span>}
            </div>
            {rag.length > 0 ? (
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                {rag.map((c, i) => {
                  const meta = c.metadata || {};
                  const pct = Math.min(100, Math.round(c.score * 100));
                  return (
                    <div key={c.chunk_id || i} className="flex flex-col justify-between rounded-2xl border border-outline-variant bg-surface-container-low p-5">
                      <div>
                        <div className="flex items-start justify-between gap-2">
                          <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 font-eyebrow text-[10px] uppercase text-primary"><Icon name="auto_stories" size={12} />{meta.source_origin || "Verified corpus"}</span>
                          {pct > 0 && <span className="rounded-full bg-gold-mist px-2 py-0.5 font-eyebrow text-[10px] uppercase text-sunburst-gold">{pct}% match</span>}
                        </div>
                        <h3 className="mt-2 font-label-sm text-[15px] font-bold text-on-surface">{meta.title || meta.filename || "Enterprise strategy intelligence"}</h3>
                        {meta.sector && <p className="font-caption text-caption text-on-surface-variant">Sector: {meta.sector}{meta.market ? ` • Market: ${meta.market}` : ""}</p>}
                        <p className="mt-2 line-clamp-3 rounded-lg bg-surface-container-lowest p-3 font-quote text-[15px] italic leading-6 text-on-surface-variant">“{c.content}”</p>
                      </div>
                      <div className="mt-4 flex items-center justify-between border-t border-outline-variant/40 pt-3">
                        <button type="button" onClick={() => discuss(c)} className="flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1.5 font-label-sm text-label-sm text-primary hover:bg-primary/20"><Icon name="chat" size={16} /> Discuss in chat</button>
                        <span className="font-caption text-[11px] text-on-surface-variant">Method: {c.retrieval_method || "hybrid"}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : !ragBusy ? (
              <p className="mt-4 rounded-2xl border border-dashed border-outline-variant p-5 text-center font-body-md text-[14px] text-on-surface-variant">No matching documents found{search ? ` for “${search}”` : ""}. Try “pricing”, “loan” or “savings”.</p>
            ) : null}
          </section>
        )}

        {insights === null ? (
          <div className="mt-8 grid gap-5 md:grid-cols-2">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="h-60 animate-pulse rounded-3xl bg-surface-container-low" />)}</div>
        ) : (
          <>
            {loadError && <p role="alert" className="mt-8 rounded-xl bg-error-container px-4 py-3 font-label-sm text-label-sm text-on-error-container">Couldn’t load the library. Check your connection and refresh.</p>}
            {featured && (
              <section className="mt-8">
                <div className="mb-3 flex items-center justify-between"><p className="flex items-center gap-2 font-eyebrow text-eyebrow uppercase text-on-surface-variant"><Icon name="auto_awesome" size={16} className="text-sunburst-gold" /> Recommended for you</p></div>
                <article className="relative overflow-hidden rounded-3xl border border-outline-variant bg-surface-container-lowest p-6 shadow-sm md:p-8">
                  <span className="kente-band absolute inset-x-0 top-0 h-1.5" />
                  <div className="grid gap-6 md:grid-cols-[1fr_280px]">
                    <div>
                      <div className="flex flex-wrap items-center gap-2"><span className="rounded-full bg-gold-mist px-3 py-1 font-eyebrow text-[10px] uppercase text-sunburst-gold">Guild masterpiece</span><span className="rounded-full bg-surface-container-low px-3 py-1 font-eyebrow text-[10px] uppercase text-primary">{featured.category}</span><span className="font-caption text-caption text-on-surface-variant">{featured.durationMinutes} min {featured.isAudio ? "listen" : "read"}</span></div>
                      <h2 className="mt-4 font-title-md text-[28px] leading-9 text-on-surface md:text-[34px] md:leading-[42px]">{featured.title}</h2>
                      <div className="mt-4 rounded-2xl bg-gold-mist p-4">
                        <p className="font-eyebrow text-[10px] uppercase text-sunburst-gold">Why this, from {mentor.name.split(" ")[0]}</p>
                        <p className="mt-1 font-quote text-[17px] italic leading-7 text-on-surface">“{profile?.sector ? `Chosen for your ${profile.sector} work — ` : ""}{featured.summary}”</p>
                      </div>
                      <div className="mt-5 flex flex-wrap items-center gap-3">
                        {featured.isAudio && <button type="button" onClick={() => setSelected(featured)} className="flex h-12 items-center gap-2 rounded-full bg-primary px-6 font-label-sm text-[15px] font-bold text-on-primary"><Icon name="play_arrow" filled /> Listen ({featured.durationMinutes}:00)</button>}
                        <button type="button" onClick={() => setSelected(featured)} className="flex h-12 items-center gap-2 rounded-full bg-sunburst-gold px-6 font-label-sm text-[15px] font-bold text-ink shadow-md">Read full framework <Icon name="arrow_forward" size={18} /></button>
                        <button type="button" aria-label={libraryFavorites.has(featured.id) ? "Remove from favorites" : "Save to favorites"} onClick={() => toggleFav(featured.id)} className="flex h-12 w-12 items-center justify-center rounded-full bg-surface-container-low text-on-surface"><Icon name="bookmark" filled={libraryFavorites.has(featured.id)} /></button>
                      </div>
                    </div>
                    <div className="hidden md:block"><Thumb item={featured} i={0} className="aspect-[4/5] w-full rounded-2xl object-cover" /></div>
                  </div>
                </article>
              </section>
            )}

            <section className="mt-10">
              <h2 className="font-title-md text-[26px] leading-8 text-on-surface">Curated insights &amp; guild blueprints</h2>
              <p className="font-caption text-caption text-on-surface-variant">Operational tools translated from generational commerce</p>
              {filtered.length === 0 ? (
                <p className="mt-5 rounded-2xl border border-dashed border-outline-variant p-8 text-center font-body-md text-body-md text-on-surface-variant">Nothing matches those filters yet.</p>
              ) : (
                <div className="mt-5 grid gap-5 md:grid-cols-2">
                  {rest.map((it, i) => <Card key={it.id} item={it} i={i + 1} fav={libraryFavorites.has(it.id)} onFav={() => toggleFav(it.id)} onOpen={() => setSelected(it)} />)}
                </div>
              )}
            </section>
          </>
        )}

        <div className="mt-12 flex items-center gap-4 rounded-2xl border border-outline-variant bg-surface-container-low p-5">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gold-mist text-sunburst-gold"><Icon name="verified_user" /></span>
          <p className="font-body-md text-[14px] leading-5 text-on-surface-variant"><span className="font-bold text-on-surface">Verified ancestral lore.</span> All materials are verified for cultural relevance and pan-African origin.</p>
        </div>
      </div>

      <InsightReaderModal item={selected} isFavorite={selected ? libraryFavorites.has(selected.id) : false} onClose={() => setSelected(null)} onToggleFavorite={() => selected && toggleFav(selected.id)} />
    </AppFrame>
  );
}
