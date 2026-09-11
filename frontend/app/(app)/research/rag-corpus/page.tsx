"use client";

import { useState } from "react";
import { Icon } from "@/components/Icon";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type DocStatus = "live" | "draft";

type CorpusDoc = {
  id: string;
  docId: string;
  title: string;
  sector: string;
  sectorColor: string; // Tailwind bg+text classes
  country: string;
  author: string;
  date: string;
  status: DocStatus;
};

type RetrievedPassage = {
  ref: string;
  score: number;
  text: string;
  isTop: boolean;
};

// ---------------------------------------------------------------------------
// Static data (faithful to design reference)
// ---------------------------------------------------------------------------

const DOCUMENTS: CorpusDoc[] = [
  {
    id: "DOC-4920-GH",
    docId: "DOC-4920-GH",
    title: "Cassava Yield Optimization v2",
    sector: "Agriculture",
    sectorColor: "bg-secondary-container text-on-secondary-container",
    country: "Ghana",
    author: "Dr. Amma Boateng",
    date: "2023-11-12",
    status: "live",
  },
  {
    id: "DOC-8812-NG",
    docId: "DOC-8812-NG",
    title: "Microfinance Literacy Framework",
    sector: "Finance",
    sectorColor: "bg-primary-container text-on-primary-container",
    country: "Nigeria",
    author: "Folake Adeleke",
    date: "2023-12-05",
    status: "draft",
  },
  {
    id: "DOC-1103-KE",
    docId: "DOC-1103-KE",
    title: "Solar Grid Decentralization Tech",
    sector: "Energy",
    sectorColor: "bg-blue-100 text-blue-800",
    country: "Kenya",
    author: "John Kariuki",
    date: "2024-01-14",
    status: "live",
  },
  {
    id: "DOC-5542-ZA",
    docId: "DOC-5542-ZA",
    title: "Urban Water Management Policy",
    sector: "Public Policy",
    sectorColor: "bg-cyan-100 text-cyan-800",
    country: "South Africa",
    author: "Lindiwe Dube",
    date: "2024-02-01",
    status: "live",
  },
];

const RETRIEVED_PASSAGES: RetrievedPassage[] = [
  {
    ref: "DOC-4920-GH · Page 14",
    score: 0.98,
    text: "\"...The adoption of drip irrigation in the Upper East region has shown a 40% increase in cassava tuber size when combined with organic mulching techniques during the harmattan season...\"",
    isTop: true,
  },
  {
    ref: "DOC-3211-GH · Page 02",
    score: 0.89,
    text: "\"...Soil salinity levels must be monitored weekly in the Bawku district to ensure that ground water extraction remains sustainable for long-term agricultural development...\"",
    isTop: false,
  },
  {
    ref: "GLOBAL-AGRI-04 · Page 45",
    score: 0.81,
    text: "\"...Community-led irrigation schemes are significantly more successful than state-managed projects in semi-arid zones of West Africa...\"",
    isTop: false,
  },
];

// ---------------------------------------------------------------------------
// Upload Modal
// ---------------------------------------------------------------------------

function UploadModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-inverse-surface/40 p-md backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-2xl border border-outline-variant bg-surface p-lg shadow-2xl sm:p-xl">
        <h2 className="font-headline-lg text-headline-lg-mobile mb-md text-primary">
          Upload Document
        </h2>
        <label className="flex cursor-pointer flex-col items-center justify-center gap-md rounded-2xl border-2 border-dashed border-outline-variant p-lg transition-colors hover:border-primary sm:p-xl">
          <input type="file" accept=".pdf,.docx" className="sr-only" />
          <Icon name="cloud_upload" size={48} className="text-on-surface-variant" />
          <p className="text-center font-medium text-on-surface">
            Drag and drop PDF or DOCX files here
          </p>
          <p className="font-label-sm text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
            Maximum file size: 50MB
          </p>
        </label>
        <div className="mt-lg flex flex-col-reverse gap-sm sm:mt-xl sm:flex-row sm:justify-end sm:gap-md">
          <button
            onClick={onClose}
            className="rounded-full px-lg py-md text-center font-bold text-on-surface-variant transition-all hover:bg-surface-variant"
          >
            Cancel
          </button>
          <button className="rounded-full bg-primary px-lg py-md font-bold text-on-primary shadow-sm">
            Confirm Upload
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function RagCorpusPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [testQuery, setTestQuery] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [hasRunQuery, setHasRunQuery] = useState(true); // start with results shown

  const filteredDocs = searchQuery
    ? DOCUMENTS.filter(
        (d) =>
          d.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          d.country.toLowerCase().includes(searchQuery.toLowerCase()) ||
          d.sector.toLowerCase().includes(searchQuery.toLowerCase()) ||
          d.author.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : DOCUMENTS;

  return (
    <main className="flex h-full min-w-0 flex-1 flex-col overflow-hidden bg-background">
      {/* ------------------------------------------------------------------ */}
      {/* Header                                                               */}
      {/* ------------------------------------------------------------------ */}
      <header className="flex shrink-0 flex-col gap-md border-b bg-surface px-md py-md md:px-lg md:py-lg">
        {/* Title row */}
        <div className="flex flex-col pl-10 md:pl-0">
          <h2 className="font-headline-lg text-headline-lg-mobile text-primary">
            RAG Corpus Admin
          </h2>
          <p className="font-mono text-xs text-on-surface-variant sm:text-sm">
            Environment: production-af-west-1
          </p>
        </div>
        {/* Search + Upload row */}
        <div className="flex flex-col gap-sm sm:flex-row sm:items-center sm:justify-between sm:gap-md">
          {/* Search */}
          <div className="group relative flex-1 sm:max-w-xs md:max-w-sm lg:max-w-md">
            <input
              type="text"
              placeholder="Search corpus..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full rounded-full border border-outline-variant bg-surface-container-low px-xl py-sm text-sm outline-none transition-all focus:border-transparent focus:ring-2 focus:ring-primary"
            />
            <Icon
              name="search"
              size={20}
              className="absolute left-md top-1/2 -translate-y-1/2 text-on-surface-variant"
            />
          </div>
          {/* Upload CTA */}
          <button
            onClick={() => setShowModal(true)}
            className="flex shrink-0 items-center justify-center gap-sm rounded-full bg-primary px-md py-sm font-semibold text-on-primary shadow-sm transition-all hover:opacity-90 active:scale-95 sm:px-lg sm:py-md"
          >
            <Icon name="upload_file" size={20} />
            <span className="hidden sm:inline">Upload New Document</span>
            <span className="sm:hidden">Upload</span>
          </button>
        </div>
      </header>

      {/* ------------------------------------------------------------------ */}
      {/* Asymmetric two-column content grid                                  */}
      {/* ------------------------------------------------------------------ */}
      <div
        className="flex-1 overflow-y-auto p-md sm:p-lg lg:p-xl [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-outline-variant [&::-webkit-scrollbar-track]:bg-transparent"
      >
        {/* Two-column grid on lg+, single column on mobile/tablet */}
        <div className="grid grid-cols-1 gap-lg lg:grid-cols-12">

          {/* ---------------------------------------------------------------- */}
          {/* Left: Document index + stats                                      */}
          {/* ---------------------------------------------------------------- */}
          <section className="space-y-lg lg:col-span-8">
            {/* Section title + filter/export actions */}
            <div className="flex flex-col gap-sm sm:flex-row sm:items-center sm:justify-between">
              <h3 className="flex items-center gap-sm font-title-md text-title-md text-on-surface">
                <Icon name="description" size={20} className="text-primary" />
                Document Index
              </h3>
              <div className="flex gap-xs">
                <button className="rounded-lg border border-outline-variant px-md py-xs text-sm font-medium transition-colors hover:bg-surface-variant">
                  Filter
                </button>
                <button className="rounded-lg border border-outline-variant px-md py-xs text-sm font-medium transition-colors hover:bg-surface-variant">
                  Export CSV
                </button>
              </div>
            </div>

            {/* Document table — desktop/tablet */}
            <div className="hidden overflow-hidden rounded-2xl border border-outline-variant bg-surface-container-lowest shadow-sm md:block">
              <div className="overflow-x-auto [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-outline-variant [&::-webkit-scrollbar-track]:bg-transparent">
                <table className="w-full min-w-[720px] border-collapse text-left">
                  <thead className="border-b border-outline-variant bg-surface-container-low">
                    <tr>
                      <th className="whitespace-nowrap px-lg py-md font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
                        Title
                      </th>
                      <th className="whitespace-nowrap px-lg py-md font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
                        Sector
                      </th>
                      <th className="whitespace-nowrap px-lg py-md font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
                        Country
                      </th>
                      <th className="whitespace-nowrap px-lg py-md font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
                        Author
                      </th>
                      <th className="whitespace-nowrap px-lg py-md font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
                        Date
                      </th>
                      <th className="whitespace-nowrap px-lg py-md font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
                        Status
                      </th>
                      <th className="whitespace-nowrap px-lg py-md" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant">
                    {filteredDocs.map((doc) => (
                      <tr
                        key={doc.id}
                        className="group cursor-pointer transition-colors hover:bg-surface-container-low"
                      >
                        <td className="whitespace-nowrap px-lg py-md">
                          <div className="flex flex-col">
                            <span className="font-body-md font-semibold text-on-surface">
                              {doc.title}
                            </span>
                            <span className="font-mono text-xs text-on-surface-variant">
                              ID: {doc.docId}
                            </span>
                          </div>
                        </td>
                        <td className="whitespace-nowrap px-lg py-md">
                          <span
                            className={`rounded-full px-md py-xs text-xs font-bold ${doc.sectorColor}`}
                          >
                            {doc.sector}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-lg py-md font-medium text-on-surface">
                          {doc.country}
                        </td>
                        <td className="whitespace-nowrap px-lg py-md text-on-surface-variant">
                          {doc.author}
                        </td>
                        <td className="whitespace-nowrap px-lg py-md font-mono text-on-surface-variant">
                          {doc.date}
                        </td>
                        <td className="whitespace-nowrap px-lg py-md">
                          {doc.status === "live" ? (
                            <span className="flex items-center gap-xs text-xs font-bold uppercase text-secondary">
                              <span className="h-2 w-2 rounded-full bg-secondary" />
                              Live
                            </span>
                          ) : (
                            <span className="flex items-center gap-xs text-xs font-bold uppercase text-tertiary">
                              <span className="h-2 w-2 rounded-full bg-tertiary" />
                              Draft
                            </span>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-lg py-md text-right">
                          <button
                            type="button"
                            aria-label="More options"
                            className="rounded-full p-1 text-on-surface-variant opacity-0 transition-opacity hover:bg-surface-variant group-hover:opacity-100"
                          >
                            <Icon name="more_vert" size={20} />
                          </button>
                        </td>
                      </tr>
                    ))}
                    {filteredDocs.length === 0 && (
                      <tr>
                        <td
                          colSpan={7}
                          className="px-lg py-xl text-center font-body-md text-on-surface-variant"
                        >
                          No documents match &ldquo;{searchQuery}&rdquo;
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Document cards — mobile only */}
            <div className="space-y-sm md:hidden">
              {filteredDocs.length === 0 && (
                <div className="rounded-2xl border border-outline-variant bg-surface-container-lowest p-lg text-center font-body-md text-on-surface-variant">
                  No documents match &ldquo;{searchQuery}&rdquo;
                </div>
              )}
              {filteredDocs.map((doc) => (
                <div
                  key={doc.id}
                  className="cursor-pointer rounded-xl border border-outline-variant bg-surface-container-lowest p-md shadow-sm transition-colors active:bg-surface-container-low"
                >
                  <div className="mb-xs flex items-start justify-between gap-sm">
                    <div className="min-w-0">
                      <p className="font-semibold text-on-surface">{doc.title}</p>
                      <p className="font-mono text-xs text-on-surface-variant">
                        ID: {doc.docId}
                      </p>
                    </div>
                    {doc.status === "live" ? (
                      <span className="flex shrink-0 items-center gap-xs text-xs font-bold uppercase text-secondary">
                        <span className="h-2 w-2 rounded-full bg-secondary" />
                        Live
                      </span>
                    ) : (
                      <span className="flex shrink-0 items-center gap-xs text-xs font-bold uppercase text-tertiary">
                        <span className="h-2 w-2 rounded-full bg-tertiary" />
                        Draft
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-sm">
                    <span
                      className={`rounded-full px-sm py-0.5 text-xs font-bold ${doc.sectorColor}`}
                    >
                      {doc.sector}
                    </span>
                    <span className="text-xs font-medium text-on-surface">
                      {doc.country}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Stats bento row */}
            <div className="grid grid-cols-1 gap-md sm:grid-cols-3 sm:gap-lg">
              {/* Total index size */}
              <div className="rounded-2xl border border-outline-variant bg-surface-container-low p-lg">
                <p className="font-label-sm text-label-sm font-bold uppercase tracking-widest text-on-surface-variant">
                  Total Index Size
                </p>
                <h4 className="mt-sm font-headline-xl text-headline-lg-mobile text-primary sm:text-headline-xl">
                  1.42 GB
                </h4>
                <div className="mt-md flex items-center gap-xs text-xs font-bold text-secondary">
                  <Icon name="trending_up" size={16} />
                  +12% from last week
                </div>
              </div>

              {/* Active vectors */}
              <div className="rounded-2xl border border-outline-variant bg-surface-container-low p-lg">
                <p className="font-label-sm text-label-sm font-bold uppercase tracking-widest text-on-surface-variant">
                  Active Vectors
                </p>
                <h4 className="mt-sm font-headline-xl text-headline-lg-mobile text-primary sm:text-headline-xl">
                  14.2M
                </h4>
                <div className="mt-md text-xs font-medium text-on-surface-variant">
                  HNSW Indexing Active
                </div>
              </div>

              {/* Inference latency */}
              <div className="rounded-2xl border border-outline-variant bg-surface-container-low p-lg">
                <p className="font-label-sm text-label-sm font-bold uppercase tracking-widest text-on-surface-variant">
                  Inference Latency
                </p>
                <h4 className="mt-sm font-headline-xl text-headline-lg-mobile text-primary sm:text-headline-xl">
                  42ms
                </h4>
                <div className="mt-md flex items-center gap-xs text-xs font-bold text-secondary">
                  <Icon name="check_circle" size={16} />
                  Optimized
                </div>
              </div>
            </div>
          </section>

          {/* ---------------------------------------------------------------- */}
          {/* Right: Test Query Bench (sticky panel on desktop)                 */}
          {/* ---------------------------------------------------------------- */}
          <aside className="lg:col-span-4">
            <div className="flex flex-col rounded-2xl border border-outline-variant bg-surface-container p-md sm:p-lg lg:sticky lg:top-0">
              {/* Panel title */}
              <div className="mb-lg flex items-center gap-sm">
                <Icon name="terminal" filled size={22} className="text-primary" />
                <h3 className="font-title-md text-title-md text-on-surface">
                  Test Query Bench
                </h3>
              </div>

              <div className="flex-1 space-y-lg overflow-y-auto">
                {/* Prompt input */}
                <div className="space-y-sm">
                  <label className="font-label-sm text-label-sm font-bold text-on-surface-variant">
                    RESEARCHER PROMPT
                  </label>
                  <textarea
                    value={testQuery}
                    onChange={(e) => setTestQuery(e.target.value)}
                    placeholder="e.g., What are the best practices for irrigation in Northern Ghana?"
                    className="h-24 w-full rounded-xl border border-outline-variant bg-surface-bright p-md font-body-md text-sm outline-none focus:ring-1 focus:ring-primary"
                  />
                  <button
                    onClick={() => setHasRunQuery(true)}
                    className="w-full rounded-lg bg-primary py-sm text-sm font-bold text-on-primary transition-all hover:opacity-90 active:scale-95"
                  >
                    Run Simulation
                  </button>
                </div>

                {/* Retrieved passages */}
                {hasRunQuery && (
                  <div className="space-y-md border-t border-outline-variant pt-lg">
                    <div className="flex flex-col gap-xs sm:flex-row sm:items-center sm:justify-between">
                      <label className="font-label-sm text-label-sm font-bold uppercase text-on-surface-variant">
                        Top Retrieved Passages (3)
                      </label>
                      <span className="rounded-full bg-surface-container-highest px-md py-xs font-mono text-xs">
                        Score: 0.942
                      </span>
                    </div>

                    {RETRIEVED_PASSAGES.map((passage) => (
                      <div
                        key={passage.ref}
                        className={`space-y-xs rounded-r-lg border-l-4 p-md shadow-sm ${
                          passage.isTop
                            ? "border-primary bg-surface-bright"
                            : "border-outline-variant bg-surface-bright"
                        }`}
                      >
                        <div className="flex flex-col gap-xs text-xs font-bold text-on-surface-variant sm:flex-row sm:items-center sm:justify-between">
                          <span>{passage.ref}</span>
                          <span className="font-mono text-secondary">
                            {passage.score.toFixed(2)} Match
                          </span>
                        </div>
                        <p
                          className={`text-sm italic leading-relaxed text-on-surface ${
                            !passage.isTop ? "opacity-80" : ""
                          }`}
                        >
                          {passage.text}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Panel footer */}
              <div className="mt-md flex items-center justify-between border-t border-outline-variant pt-lg font-mono text-xs text-on-surface-variant">
                <span>Model: GPT-4-Afri-V2</span>
                <span className="flex items-center gap-xs">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-secondary" />
                  System Ready
                </span>
              </div>
            </div>
          </aside>
        </div>
      </div>

      {/* Upload modal */}
      {showModal && <UploadModal onClose={() => setShowModal(false)} />}
    </main>
  );
}
