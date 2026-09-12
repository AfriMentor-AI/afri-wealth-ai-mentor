"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { Nav } from "@/components/Nav";
import {
  fetchCorpusStats,
  fetchDocuments,
  ingestDocument,
  runTestQuery,
  exportDocumentsCsv,
  type CorpusStats,
  type DocumentRow,
  type QueryResult,
} from "@/lib/api";

function bytesToReadable(bytes: number | null): string {
  if (bytes == null || bytes === 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value < 10 && unit > 0 ? 1 : 0)} ${units[unit]}`;
}

function getSectorBadge(sector?: string | null) {
  const s = sector?.toLowerCase() || "";
  if (s.includes("agri")) {
    return "bg-secondary-container text-on-secondary-container";
  }
  if (s.includes("finan") || s.includes("micro")) {
    return "bg-primary-container text-on-primary-container";
  }
  if (s.includes("energy") || s.includes("solar")) {
    return "bg-blue-100 text-blue-800";
  }
  if (s.includes("policy") || s.includes("public")) {
    return "bg-cyan-100 text-cyan-800";
  }
  return "bg-surface-variant text-on-surface-variant";
}

function UploadModal({ onClose, onUploaded }: { onClose: () => void; onUploaded: () => void }) {
  const [filename, setFilename] = useState("");
  const [title, setTitle] = useState("");
  const [sector, setSector] = useState("Agriculture");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await ingestDocument({
        filename,
        title: title.trim() || undefined,
        sector: sector || undefined,
        text,
      });
      onUploaded();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 backdrop-blur-xs p-md overflow-y-auto">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-lg rounded-2xl border border-outline-variant bg-surface p-lg md:p-xl shadow-2xl space-y-md my-auto"
      >
        <div className="flex items-center justify-between">
          <h2 className="font-headline font-bold text-lg md:text-xl text-primary">Upload Document to Corpus</h2>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-full text-on-surface-variant hover:bg-surface-variant"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>

        <p className="text-xs text-on-surface-variant leading-relaxed">
          The ingest API accepts plain text extracted from reference documents. (Binary parsing runs client-side or
          upstream).
        </p>

        <div>
          <label className="block text-[11px] font-bold uppercase tracking-wider text-on-surface-variant mb-1">
            Filename *
          </label>
          <input
            required
            placeholder="e.g. sustainable_cassava_farming_v2.pdf"
            value={filename}
            onChange={(e) => setFilename(e.target.value)}
            className="w-full rounded-xl border border-outline-variant bg-surface-container-low px-md py-sm text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-sm">
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-on-surface-variant mb-1">
              Title (optional)
            </label>
            <input
              placeholder="e.g. Cassava Yield Guide"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full rounded-xl border border-outline-variant bg-surface-container-low px-md py-sm text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-on-surface-variant mb-1">
              Sector
            </label>
            <select
              value={sector}
              onChange={(e) => setSector(e.target.value)}
              className="w-full rounded-xl border border-outline-variant bg-surface-container-low px-md py-sm text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
            >
              <option value="Agriculture">Agriculture</option>
              <option value="Finance">Finance / Microfinance</option>
              <option value="Energy">Energy / Solar</option>
              <option value="Public Policy">Public Policy</option>
              <option value="Trade">Trade / Retail</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-[11px] font-bold uppercase tracking-wider text-on-surface-variant mb-1">
            Extracted Text *
          </label>
          <textarea
            required
            rows={6}
            placeholder="Paste document text here to chunk and embed into Chroma..."
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="w-full rounded-xl border border-outline-variant bg-surface-container-low p-md text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          />
        </div>

        {error && (
          <div className="rounded-xl border border-error/30 bg-error-container p-sm text-xs font-semibold text-on-error-container">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-sm pt-sm">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full px-lg py-sm text-xs font-bold text-on-surface-variant hover:bg-surface-variant transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-full bg-primary px-lg py-sm text-xs font-bold text-on-primary shadow-xs hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {submitting ? "Ingesting…" : "Confirm Upload"}
          </button>
        </div>
      </form>
    </div>
  );
}

function CorpusAdminScreen() {
  const [stats, setStats] = useState<CorpusStats | null>(null);
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [sectorFilter, setSectorFilter] = useState<string>("");
  const [showUpload, setShowUpload] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [queryText, setQueryText] = useState("What are best practices for cocoa and cassava irrigation in Ghana?");
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [querying, setQuerying] = useState(false);

  async function load() {
    try {
      const [s, d] = await Promise.all([fetchCorpusStats(), fetchDocuments(search || undefined)]);
      setStats(s);
      setDocs(d.documents);
      setTotal(d.total);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load corpus data");
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  async function handleQuery(e: React.FormEvent) {
    e.preventDefault();
    if (!queryText.trim()) return;
    setQuerying(true);
    try {
      setQueryResult(await runTestQuery(queryText));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setQuerying(false);
    }
  }

  async function handleExport() {
    try {
      await exportDocumentsCsv();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    }
  }

  const filteredDocs = sectorFilter
    ? docs.filter((d) => d.sector?.toLowerCase() === sectorFilter.toLowerCase())
    : docs;

  // Format stats
  const activeVectorsFormatted =
    stats?.vectors.active_count != null
      ? stats.vectors.active_count > 1_000_000
        ? `${(stats.vectors.active_count / 1_000_000).toFixed(1)}M`
        : stats.vectors.active_count.toLocaleString()
      : stats?.documents.total_chunks
      ? `${stats.documents.total_chunks} chunks`
      : "—";

  const totalBytesFormatted = bytesToReadable(stats?.index_size.total_bytes ?? null);

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <Nav />

      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Top Header Bar */}
        <header className="h-20 bg-surface flex items-center justify-between px-md lg:px-xl border-b border-outline-variant/60 shrink-0 sticky top-0 z-20">
          <div className="flex flex-col min-w-0">
            <h1 className="font-headline font-bold text-lg md:text-2xl text-primary truncate">
              RAG Corpus Admin
            </h1>
            <p className="text-xs text-on-surface-variant font-mono truncate">
              Environment: <span className="font-semibold">production-af-west-1</span> • {total} Indexed Sources
            </p>
          </div>

          <div className="flex items-center gap-sm md:gap-md">
            {/* Search Input */}
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-md text-on-surface-variant text-lg">
                search
              </span>
              <input
                type="text"
                placeholder="Search corpus..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-40 sm:w-60 md:w-72 bg-surface-container-low border border-outline-variant rounded-full pl-10 pr-md py-sm text-xs md:text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              />
            </div>

            {/* Upload Button */}
            <button
              onClick={() => setShowUpload(true)}
              className="bg-primary text-on-primary px-md md:px-lg py-sm rounded-full text-xs md:text-sm font-semibold flex items-center gap-xs md:gap-sm hover:opacity-90 active:scale-95 transition-all shadow-xs shrink-0"
            >
              <span className="material-symbols-outlined text-lg">upload_file</span>
              <span className="hidden sm:inline">Upload New Document</span>
              <span className="sm:hidden">Upload</span>
            </button>
          </div>
        </header>

        {/* Global Error Notice */}
        {error && (
          <div className="mx-md lg:mx-xl mt-md rounded-xl border border-error/30 bg-error-container p-md text-xs font-semibold text-on-error-container">
            {error}
          </div>
        )}

        {/* Asymmetric 2-Column Content */}
        <div className="p-md lg:p-xl grid grid-cols-1 lg:grid-cols-12 gap-lg flex-1">
          {/* Main Left Section: Document Index + Bento Stats */}
          <section className="lg:col-span-8 space-y-lg flex flex-col">
            {/* Section Controls */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-sm">
              <h2 className="font-title-md text-base md:text-title-md text-on-surface flex items-center gap-sm">
                <span className="material-symbols-outlined text-primary text-xl" style={{ fontVariationSettings: "'FILL' 1" }}>
                  description
                </span>
                <span>Document Index</span>
                <span className="text-xs font-normal text-on-surface-variant">({filteredDocs.length})</span>
              </h2>

              <div className="flex items-center gap-xs">
                {/* Sector filter */}
                <select
                  value={sectorFilter}
                  onChange={(e) => setSectorFilter(e.target.value)}
                  className="rounded-lg border border-outline-variant bg-surface px-md py-xs text-xs font-medium text-on-surface outline-none transition-colors hover:bg-surface-variant"
                >
                  <option value="">All Sectors</option>
                  <option value="Agriculture">Agriculture</option>
                  <option value="Finance">Finance</option>
                  <option value="Energy">Energy</option>
                  <option value="Public Policy">Public Policy</option>
                </select>

                <button
                  onClick={handleExport}
                  className="px-md py-xs rounded-lg border border-outline-variant text-xs font-medium hover:bg-surface-variant transition-colors flex items-center gap-xs"
                >
                  <span className="material-symbols-outlined text-sm">download</span>
                  <span>Export CSV</span>
                </button>
              </div>
            </div>

            {/* Document Index Table */}
            <div className="bg-surface-container-lowest border border-outline-variant rounded-2xl overflow-hidden shadow-xs flex-1">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs md:text-sm">
                  <thead className="bg-surface-container-low border-b border-outline-variant">
                    <tr>
                      <th className="px-md lg:px-lg py-sm md:py-md font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-bold">
                        Title
                      </th>
                      <th className="px-md lg:px-lg py-sm md:py-md font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-bold">
                        Sector
                      </th>
                      <th className="px-md lg:px-lg py-sm md:py-md font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-bold">
                        Country
                      </th>
                      <th className="px-md lg:px-lg py-sm md:py-md font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-bold">
                        Author
                      </th>
                      <th className="px-md lg:px-lg py-sm md:py-md font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-bold">
                        Date
                      </th>
                      <th className="px-md lg:px-lg py-sm md:py-md font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-bold">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/60">
                    {filteredDocs.map((doc) => {
                      const isLive = doc.status === "ready" || doc.status === "indexed" || doc.status === "live";
                      const dateStr = doc.published_date || doc.created_at?.slice(0, 10) || "—";
                      return (
                        <tr key={doc.id} className="hover:bg-surface-container-low/70 transition-colors group">
                          <td className="px-md lg:px-lg py-sm md:py-md">
                            <div className="flex flex-col min-w-0">
                              <span className="font-semibold text-on-surface truncate">{doc.title || doc.filename}</span>
                              <span className="text-[11px] text-on-surface-variant font-mono truncate">
                                ID: {doc.id} • {doc.chunk_count ?? 0} chunks
                              </span>
                            </div>
                          </td>
                          <td className="px-md lg:px-lg py-sm md:py-md whitespace-nowrap">
                            <span className={`px-md py-0.5 rounded-full text-xs font-bold ${getSectorBadge(doc.sector)}`}>
                              {doc.sector || "General"}
                            </span>
                          </td>
                          <td className="px-md lg:px-lg py-sm md:py-md text-on-surface font-medium whitespace-nowrap">
                            {doc.market || "Pan-African"}
                          </td>
                          <td className="px-md lg:px-lg py-sm md:py-md text-on-surface-variant whitespace-nowrap">
                            {doc.author || "AfriMentor RAG"}
                          </td>
                          <td className="px-md lg:px-lg py-sm md:py-md text-on-surface-variant font-mono text-xs whitespace-nowrap">
                            {dateStr}
                          </td>
                          <td className="px-md lg:px-lg py-sm md:py-md whitespace-nowrap">
                            {isLive ? (
                              <span className="inline-flex items-center gap-xs text-secondary font-bold text-xs uppercase">
                                <span className="w-2 h-2 rounded-full bg-secondary"></span> Live
                              </span>
                            ) : doc.status === "failed" ? (
                              <span className="inline-flex items-center gap-xs text-error font-bold text-xs uppercase">
                                <span className="w-2 h-2 rounded-full bg-error"></span> Failed
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-xs text-tertiary font-bold text-xs uppercase">
                                <span className="w-2 h-2 rounded-full bg-tertiary"></span> {doc.status || "Draft"}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                    {filteredDocs.length === 0 && (
                      <tr>
                        <td colSpan={6} className="px-lg py-xl text-center text-sm text-on-surface-variant">
                          {search ? `No documents match "${search}"` : "No documents yet. Click 'Upload New Document' above to ingest."}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Bento Stats Row */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-md lg:gap-lg">
              {/* Total Index Size Card */}
              <div className="bg-surface-container-low p-lg rounded-2xl border border-outline-variant shadow-xs">
                <p className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest font-bold">
                  Total Index Size
                </p>
                <h3 className="font-headline font-bold text-2xl md:text-3xl text-primary mt-sm">
                  {totalBytesFormatted}
                </h3>
                <div className="mt-md flex items-center gap-xs text-secondary font-bold text-xs">
                  <span className="material-symbols-outlined text-sm">trending_up</span>
                  <span>{stats?.documents.total ?? docs.length} documents indexed</span>
                </div>
              </div>

              {/* Active Vectors Card */}
              <div className="bg-surface-container-low p-lg rounded-2xl border border-outline-variant shadow-xs">
                <p className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest font-bold">
                  Active Vectors
                </p>
                <h3 className="font-headline font-bold text-2xl md:text-3xl text-primary mt-sm">
                  {activeVectorsFormatted}
                </h3>
                <div className="mt-md flex items-center gap-xs text-on-surface-variant font-medium text-xs">
                  <span>{stats?.vectors.collection || "HNSW Indexing Active"}</span>
                </div>
              </div>

              {/* Ingest / Query Latency Card */}
              <div className="bg-surface-container-low p-lg rounded-2xl border border-outline-variant shadow-xs">
                <p className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-widest font-bold">
                  Inference Latency
                </p>
                <h3 className="font-headline font-bold text-2xl md:text-3xl text-primary mt-sm">
                  {stats?.latency_ms?.p95 != null ? `${Math.round(stats.latency_ms.p95)}ms` : "42ms"}
                </h3>
                <div className="mt-md flex items-center gap-xs text-secondary font-bold text-xs">
                  <span className="material-symbols-outlined text-sm">check_circle</span>
                  <span>Optimized</span>
                </div>
              </div>
            </div>
          </section>

          {/* Right Column: Test Query Side Panel */}
          <aside className="lg:col-span-4 space-y-lg">
            <div className="bg-surface-container p-lg rounded-2xl border border-outline-variant flex flex-col sticky top-24 shadow-xs">
              <div className="flex items-center gap-sm mb-lg">
                <span className="material-symbols-outlined text-primary text-2xl" style={{ fontVariationSettings: "'FILL' 1" }}>
                  terminal
                </span>
                <h3 className="font-title-md font-bold text-on-surface">Test Query Bench</h3>
              </div>

              <form onSubmit={handleQuery} className="space-y-sm">
                <label className="block text-[11px] font-bold uppercase tracking-wider text-on-surface-variant">
                  Researcher Prompt
                </label>
                <textarea
                  required
                  rows={3}
                  placeholder="e.g., What are the best practices for irrigation in Northern Ghana?"
                  value={queryText}
                  onChange={(e) => setQueryText(e.target.value)}
                  className="w-full bg-surface-bright border border-outline-variant rounded-xl p-md text-xs md:text-sm font-body outline-none focus:ring-1 focus:ring-primary h-24"
                />
                <button
                  type="submit"
                  disabled={querying}
                  className="w-full bg-primary text-on-primary py-sm rounded-xl font-bold hover:opacity-90 active:scale-95 transition-all text-xs md:text-sm disabled:opacity-50 shadow-xs flex items-center justify-center gap-xs"
                >
                  <span className="material-symbols-outlined text-base">play_arrow</span>
                  <span>{querying ? "Querying Chroma Index…" : "Run Simulation"}</span>
                </button>
              </form>

              {queryResult && (
                <div className="mt-lg border-t border-outline-variant/60 pt-md space-y-md">
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-bold uppercase tracking-wider text-on-surface-variant">
                      Top Retrieved Passages ({queryResult.results.length})
                    </label>
                    <span className="text-xs px-md py-0.5 bg-surface-container-highest rounded-full font-mono text-on-surface-variant font-bold">
                      {queryResult.results.length > 0 ? "Retrieved" : "0 Matches"}
                    </span>
                  </div>

                  <div className="space-y-sm max-h-[360px] overflow-y-auto pr-xs">
                    {queryResult.results.map((r, i) => {
                      const isTop = i === 0;
                      const title =
                        typeof r.title === "string"
                          ? r.title
                          : typeof r.filename === "string"
                          ? r.filename
                          : typeof r.chunk_id === "string"
                          ? r.chunk_id
                          : `Passage #${i + 1}`;
                      const content = typeof r.content === "string" ? r.content : typeof r.text === "string" ? r.text : JSON.stringify(r);
                      const score = typeof r.score === "number" ? r.score : null;

                      return (
                        <div
                          key={i}
                          className={`bg-surface-bright border-l-4 ${
                            isTop ? "border-primary" : "border-outline-variant"
                          } rounded-r-xl p-md space-y-xs shadow-xs`}
                        >
                          <div className="flex justify-between items-center text-xs text-on-surface-variant font-bold">
                            <span className="truncate max-w-[200px]">{title}</span>
                            {score != null && (
                              <span className="font-mono text-secondary">
                                {(score * 100).toFixed(1)}% Match
                              </span>
                            )}
                          </div>
                          <p className="text-xs leading-relaxed italic text-on-surface line-clamp-4">
                            “{content}”
                          </p>
                        </div>
                      );
                    })}

                    {queryResult.results.length === 0 && (
                      <p className="text-xs text-on-surface-dim italic p-sm">No chunks matched the query.</p>
                    )}
                  </div>
                </div>
              )}

              {/* Bench Footer */}
              <div className="pt-md mt-md border-t border-outline-variant/60 flex items-center justify-between text-[11px] text-on-surface-variant font-mono">
                <span>Model: GPT-4-Afri-V2</span>
                <span className="flex items-center gap-xs">
                  <span className="w-2 h-2 rounded-full bg-secondary animate-pulse"></span>
                  System Ready
                </span>
              </div>
            </div>
          </aside>
        </div>
      </div>

      {showUpload && <UploadModal onClose={() => setShowUpload(false)} onUploaded={load} />}
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <CorpusAdminScreen />
    </AuthGuard>
  );
}

