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
  if (bytes == null) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value < 10 && unit > 0 ? 1 : 0)} ${units[unit]}`;
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-md border border-border bg-surface-raised p-4">
      <p className="text-xs uppercase tracking-wide text-on-surface-dim">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
      {sub && <p className="mt-1 text-xs text-on-surface-dim">{sub}</p>}
    </div>
  );
}

function UploadModal({ onClose, onUploaded }: { onClose: () => void; onUploaded: () => void }) {
  const [filename, setFilename] = useState("");
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await ingestDocument({ filename, title: title || undefined, text });
      onUploaded();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/60 px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-lg rounded-md border border-border bg-surface-raised p-6"
      >
        <h2 className="mb-1 text-base font-semibold">Add document</h2>
        <p className="mb-4 text-xs text-on-surface-dim">
          The ingest API takes plain text, not a PDF/DOCX upload — paste extracted text
          below. (Binary file parsing isn&apos;t implemented in rag-corpus-service.)
        </p>
        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-on-surface-dim">
          Filename
        </label>
        <input
          required
          value={filename}
          onChange={(e) => setFilename(e.target.value)}
          className="mb-3 w-full rounded border border-border bg-surface-inset px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-on-surface-dim">
          Title (optional)
        </label>
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="mb-3 w-full rounded border border-border bg-surface-inset px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <label className="mb-1 block text-xs font-medium uppercase tracking-wide text-on-surface-dim">
          Text
        </label>
        <textarea
          required
          rows={6}
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="mb-4 w-full rounded border border-border bg-surface-inset px-3 py-2 text-sm outline-none focus:border-accent"
        />
        {error && <p className="mb-3 text-sm text-danger">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded px-4 py-2 text-sm text-on-surface-dim">
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded bg-accent px-4 py-2 text-sm font-semibold text-on-accent disabled:opacity-60"
          >
            {submitting ? "Uploading…" : "Upload"}
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
  const [showUpload, setShowUpload] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [queryText, setQueryText] = useState("");
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

  return (
    <div>
      <Nav />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-xl font-semibold">RAG Corpus Admin</h1>
          <div className="flex gap-2">
            <button
              onClick={handleExport}
              className="rounded border border-border px-3 py-2 text-sm text-on-surface-dim hover:text-on-surface"
            >
              Export CSV
            </button>
            <button
              onClick={() => setShowUpload(true)}
              className="rounded bg-accent px-3 py-2 text-sm font-semibold text-on-accent"
            >
              Add document
            </button>
          </div>
        </div>

        {error && <p className="mb-4 text-sm text-danger">{error}</p>}

        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCard
            label="Total index size"
            value={bytesToReadable(stats?.index_size.total_bytes ?? null)}
            sub={`${stats?.documents.total ?? 0} documents`}
          />
          <StatCard
            label="Active vectors"
            value={stats?.vectors.active_count?.toLocaleString() ?? "—"}
            sub={stats?.vectors.collection ?? "collection unknown"}
          />
          <StatCard
            label="Ingest p95 latency"
            value={stats?.latency_ms?.p95 != null ? `${Math.round(stats.latency_ms.p95)}ms` : "—"}
          />
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-on-surface-dim">
                Document index ({total})
              </h2>
              <input
                placeholder="Search title, author, filename…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="rounded border border-border bg-surface-inset px-3 py-1.5 text-sm outline-none focus:border-accent"
              />
            </div>
            <div className="overflow-x-auto rounded-md border border-border">
              <table className="w-full text-left text-sm">
                <thead className="bg-surface-raised text-xs uppercase text-on-surface-dim">
                  <tr>
                    <th className="px-3 py-2">Title</th>
                    <th className="px-3 py-2">Sector</th>
                    <th className="px-3 py-2">Country</th>
                    <th className="px-3 py-2">Author</th>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((d) => (
                    <tr key={d.id} className="border-t border-border">
                      <td className="px-3 py-2">{d.title || d.filename}</td>
                      <td className="px-3 py-2 text-on-surface-dim">{d.sector || "—"}</td>
                      <td className="px-3 py-2 text-on-surface-dim">{d.market || "—"}</td>
                      <td className="px-3 py-2 text-on-surface-dim">{d.author || "—"}</td>
                      <td className="px-3 py-2 text-on-surface-dim">
                        {d.published_date || d.created_at.slice(0, 10)}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`rounded px-2 py-0.5 text-xs ${
                            d.status === "ready"
                              ? "bg-accent/20 text-accent"
                              : d.status === "failed"
                                ? "bg-danger/20 text-danger"
                                : "bg-warn/20 text-warn"
                          }`}
                        >
                          {d.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {docs.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-3 py-6 text-center text-on-surface-dim">
                        No documents yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h2 className="mb-3 text-sm font-semibold text-on-surface-dim">Test query bench</h2>
            <form onSubmit={handleQuery} className="rounded-md border border-border bg-surface-raised p-4">
              <textarea
                required
                rows={3}
                placeholder="Try a retrieval query…"
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                className="mb-3 w-full rounded border border-border bg-surface-inset px-3 py-2 text-sm outline-none focus:border-accent"
              />
              <button
                type="submit"
                disabled={querying}
                className="w-full rounded bg-accent py-2 text-sm font-semibold text-on-accent disabled:opacity-60"
              >
                {querying ? "Querying…" : "Run query"}
              </button>
            </form>
            {queryResult && (
              <div className="mt-3 space-y-2">
                {queryResult.results.map((r, i) => (
                  <div key={i} className="rounded border border-border bg-surface-inset p-3 text-xs">
                    <pre className="whitespace-pre-wrap break-words">{JSON.stringify(r, null, 2)}</pre>
                  </div>
                ))}
                {queryResult.results.length === 0 && (
                  <p className="text-xs text-on-surface-dim">No matches.</p>
                )}
              </div>
            )}
          </div>
        </div>
      </main>

      {showUpload && (
        <UploadModal onClose={() => setShowUpload(false)} onUploaded={load} />
      )}
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
