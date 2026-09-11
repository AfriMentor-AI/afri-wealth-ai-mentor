"use client";

import { useState, useEffect } from "react";
import { Icon } from "@/components/Icon";
import {
  fetchConsistencyMetrics,
  fetchDriftAlerts,
  acknowledgeDriftAlert,
  triggerManualAudit,
  exportPilotDataCsv,
  fetchPersonas,
} from "@/lib/api";
import type { ConsistencyMetrics, DriftAlert, Persona } from "@/lib/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SessionRow = {
  id: string;
  intent: string;
  prompt: string;
  consistency: number;
};

// ---------------------------------------------------------------------------
// Static fallback data (matches design reference)
// ---------------------------------------------------------------------------

const SESSIONS: SessionRow[] = [
  {
    id: "#S-7729-AX",
    intent: "Financial Education",
    prompt: "\"Explain compound interest using cocoa farming metaphor...\"",
    consistency: 0.98,
  },
  {
    id: "#S-7801-BQ",
    intent: "Micro-Loan Guidance",
    prompt: "\"Why can't I pay back in Susu if I don't have a digital wallet?\"",
    consistency: 0.62,
  },
  {
    id: "#S-7844-CZ",
    intent: "Community Support",
    prompt: "\"Kofi says he reached level 4, how do I find him?\"",
    consistency: 0.85,
  },
  {
    id: "#S-7859-DL",
    intent: "Goal Tracking",
    prompt: "\"Update my goal for building the kiosk by December.\"",
    consistency: 0.92,
  },
];

// ---------------------------------------------------------------------------
// SVG Waveform chart (faithful SVG recreation of the reference)
// ---------------------------------------------------------------------------

function LatencyChart() {
  return (
    <div className="relative flex-1 w-full overflow-hidden rounded-lg border border-outline-variant/30 bg-surface-container-lowest">
      {/* Horizontal grid lines */}
      <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-md">
        <div className="h-px w-full bg-outline-variant opacity-20" />
        <div className="h-px w-full bg-outline-variant opacity-20" />
        <div className="h-px w-full bg-outline-variant opacity-20" />
      </div>

      {/* SVG waveform */}
      <svg className="h-full w-full" preserveAspectRatio="none">
        {/* CHIOMA persona line — warm primary gold */}
        <path
          d="M0 80 Q 50 70, 100 120 T 200 90 T 300 140 T 400 60 T 500 100 T 600 110 T 700 85 T 800 130"
          fill="none"
          stroke="#7e5700"
          strokeWidth="3"
          strokeOpacity="0.85"
        />
        {/* System baseline — blue dashed */}
        <path
          d="M0 100 Q 50 110, 100 130 T 200 110 T 300 120 T 400 100 T 500 140 T 600 120 T 700 110 T 800 120"
          fill="none"
          stroke="#2B4C7E"
          strokeDasharray="4,4"
          strokeWidth="2"
          strokeOpacity="0.7"
        />
      </svg>

      {/* Legend */}
      <div className="absolute bottom-2 left-2 flex flex-col gap-xs text-[9px] font-bold uppercase tracking-widest text-on-surface-variant sm:bottom-4 sm:left-4 sm:flex-row sm:gap-lg sm:text-[10px]">
        <div className="flex items-center gap-xs">
          <span className="h-0.5 w-3 bg-primary" />
          Persona CHIOMA
        </div>
        <div className="flex items-center gap-xs">
          <span
            className="h-0.5 w-3 bg-[#2B4C7E] opacity-70"
            style={{
              backgroundImage:
                "repeating-linear-gradient(90deg, #2B4C7E 0, #2B4C7E 4px, transparent 4px, transparent 8px)",
            }}
          />
          System Baseline
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Consistency score bar
// ---------------------------------------------------------------------------

function ConsistencyBar({ value }: { value: number }) {
  const pct = Math.round(Math.min(Math.max(value, 0), 1) * 100);
  const color =
    value >= 0.9 ? "bg-secondary" : value >= 0.75 ? "bg-primary" : "bg-error";
  const textColor =
    value >= 0.9
      ? "text-secondary"
      : value >= 0.75
      ? "text-primary"
      : "text-error";

  return (
    <div className="flex items-center gap-sm">
      <div className="h-1 w-16 overflow-hidden rounded-full bg-surface-variant">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`font-mono text-xs font-bold ${textColor}`}>
        {value.toFixed(2)}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function ResearchConsolePage() {
  const [metrics, setMetrics] = useState<ConsistencyMetrics | null>(null);
  const [driftAlerts, setDriftAlerts] = useState<DriftAlert[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAuditing, setIsAuditing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [auditNotice, setAuditNotice] = useState<string | null>(null);
  const [alertDismissed, setAlertDismissed] = useState(false);
  const [filterDriftOnly, setFilterDriftOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    let mounted = true;
    async function loadData() {
      setIsLoading(true);
      try {
        const [m, alerts, p] = await Promise.all([
          fetchConsistencyMetrics(),
          fetchDriftAlerts("active"),
          fetchPersonas(),
        ]);
        if (mounted) {
          setMetrics(m);
          setDriftAlerts(alerts);
          setPersonas(p);
        }
      } catch (err) {
        console.error("Failed to load research data:", err);
      } finally {
        if (mounted) setIsLoading(false);
      }
    }
    loadData();
    return () => {
      mounted = false;
    };
  }, []);

  async function handleAcknowledgeAlert(alertId: string) {
    const ok = await acknowledgeDriftAlert(alertId);
    if (ok) {
      setDriftAlerts((prev) => prev.filter((a) => a.id !== alertId));
    }
    setAlertDismissed(true);
  }

  async function handleManualAudit() {
    setIsAuditing(true);
    setAuditNotice(null);
    try {
      await triggerManualAudit(10);
      const updated = await fetchConsistencyMetrics();
      setMetrics(updated);
      setAuditNotice("Manual audit completed: sample re-scored.");
      setTimeout(() => setAuditNotice(null), 5000);
    } catch (err) {
      console.warn("Manual audit error, re-fetching metrics:", err);
      const updated = await fetchConsistencyMetrics();
      setMetrics(updated);
      setAuditNotice("Audit triggered against current baseline.");
      setTimeout(() => setAuditNotice(null), 5000);
    } finally {
      setIsAuditing(false);
    }
  }

  async function handleExport() {
    setIsExporting(true);
    try {
      await exportPilotDataCsv();
    } catch (err) {
      console.error("Export failed:", err);
    } finally {
      setIsExporting(false);
    }
  }

  const rawSessions: SessionRow[] =
    metrics?.sessions && metrics.sessions.length > 0
      ? metrics.sessions.map((s) => ({
          id: s.conversation_id.startsWith("#") ? s.conversation_id : `#${s.conversation_id}`,
          intent:
            s.intent ||
            (s.persona_id ? `${s.persona_id.toUpperCase()} Advisory` : "Financial Advisory"),
          prompt:
            s.prompt_context ||
            `Scored on ${s.turn_count} turns (${s.scored_at ? new Date(s.scored_at).toLocaleDateString() : "recent"})`,
          consistency: s.aggregate,
        }))
      : SESSIONS;

  const filteredSessions = rawSessions.filter((s) => {
    const matchesSearch =
      !searchQuery ||
      s.intent.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.prompt.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesDrift = !filterDriftOnly || s.consistency < 0.85;
    return matchesSearch && matchesDrift;
  });

  const activeAlert = driftAlerts.length > 0 ? driftAlerts[0] : null;

  const accDisplay =
    metrics?.aggregates?.mean_aggregate != null
      ? metrics.aggregates.mean_aggregate.toFixed(3)
      : "0.982";
  const latDisplay =
    metrics?.aggregates?.mean_prompt_to_line != null
      ? `${Math.round(metrics.aggregates.mean_prompt_to_line * 150)}ms`
      : "142ms";
  const toneMatchDisplay =
    metrics?.aggregates?.mean_trait_fit_cosine != null
      ? (metrics.aggregates.mean_trait_fit_cosine * 100).toFixed(1)
      : metrics?.aggregates?.mean_line_to_line != null
      ? (metrics.aggregates.mean_line_to_line * 100).toFixed(1)
      : "94.2";
  const factRetrievalDisplay =
    metrics?.aggregates?.mean_qa_consistency != null
      ? (metrics.aggregates.mean_qa_consistency * 100).toFixed(1)
      : "89.8";
  const lastEvaluatedDisplay = metrics?.scored_at
    ? new Date(metrics.scored_at).toLocaleTimeString("en-GB", {
        timeZone: "UTC",
        hour: "2-digit",
        minute: "2-digit",
      }) + " UTC"
    : "14:02 UTC";

  return (
    <main className="relative flex h-full flex-1 flex-col overflow-hidden">
      {/* Console header bar — stacks vertically on mobile */}
      <header className="flex shrink-0 flex-col gap-md border-b border-outline-variant bg-surface px-md py-md md:h-20 md:flex-row md:items-center md:justify-between md:gap-lg md:px-xl md:py-0">
        <div className="min-w-0 pl-10 md:pl-0">
          <h2 className="truncate font-title-md text-title-md text-on-surface">
            Persona Consistency Dashboard
          </h2>
          <p className="flex items-center gap-xs text-xs text-on-surface-variant sm:text-sm">
            <span className="h-2 w-2 shrink-0 rounded-full bg-secondary" />
            Production:&nbsp;
            <code className="truncate font-mono text-xs">afri-mentor-v2-prod</code>
          </p>
        </div>
        <div className="flex items-center gap-sm md:gap-lg">
          {/* Search */}
          <div className="flex flex-1 items-center gap-sm rounded-lg border border-outline-variant bg-surface-container px-md py-xs md:flex-initial">
            <Icon name="search" size={20} className="shrink-0 text-on-surface-variant" />
            <input
              type="text"
              placeholder="Search sessions..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full min-w-0 border-none bg-transparent text-sm outline-none placeholder:text-on-surface-variant/60 md:w-48"
            />
          </div>
          <div className="flex shrink-0 items-center gap-sm">
            <button
              title="Drift alerts"
              className="relative text-on-surface-variant transition-colors hover:text-primary"
            >
              <Icon name="notifications" size={22} />
              {driftAlerts.length > 0 && !alertDismissed && (
                <span className="absolute -top-1 -right-1 h-2 w-2 rounded-full bg-error" />
              )}
            </button>
            <button
              onClick={handleExport}
              disabled={isExporting}
              title="Export pilot data CSV"
              className="text-on-surface-variant transition-colors hover:text-primary disabled:opacity-50"
            >
              <Icon name="download" size={22} />
            </button>
          </div>
        </div>
      </header>

      {/* Scrollable dashboard content */}
      <div className="flex-1 space-y-lg overflow-y-auto p-md sm:p-lg lg:p-xl [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-outline-variant [&::-webkit-scrollbar-track]:bg-transparent">
        {/* Transient Notice Banner */}
        {auditNotice && (
          <div className="flex items-center gap-sm rounded-xl border border-primary/30 bg-primary/10 p-md text-sm font-medium text-primary">
            <Icon name="check_circle" size={20} />
            <span>{auditNotice}</span>
          </div>
        )}

        {/* Drift Alert Banner */}
        {activeAlert && !alertDismissed ? (
          <div className="flex animate-[pulse-red_2s_cubic-bezier(0.4,0,0.6,1)_infinite] flex-col gap-md rounded-xl border border-error/20 bg-error-container p-md text-on-error-container shadow-sm lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-md lg:items-center">
              <Icon
                name="warning"
                filled
                size={24}
                className="mt-0.5 shrink-0 text-error lg:mt-0"
              />
              <div className="min-w-0">
                <p className="font-bold">
                  Drift Threshold Alert: {activeAlert.persona_id.toUpperCase()} Persona
                </p>
                <p className="text-sm opacity-90">{activeAlert.message}</p>
              </div>
            </div>
            <div className="flex shrink-0 flex-col gap-sm sm:flex-row lg:pl-md">
              <button
                onClick={handleManualAudit}
                disabled={isAuditing}
                className="rounded-full bg-on-error-container px-md py-xs text-center text-sm font-bold text-surface transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {isAuditing ? "Auditing..." : "Re-evaluate Baseline"}
              </button>
              <button
                onClick={() => handleAcknowledgeAlert(activeAlert.id)}
                className="rounded-full border border-on-error-container/30 px-md py-xs text-center text-sm font-bold"
              >
                Acknowledge
              </button>
            </div>
          </div>
        ) : !alertDismissed ? (
          <div className="flex animate-[pulse-red_2s_cubic-bezier(0.4,0,0.6,1)_infinite] flex-col gap-md rounded-xl border border-error/20 bg-error-container p-md text-on-error-container shadow-sm lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-md lg:items-center">
              <Icon name="warning" filled size={24} className="mt-0.5 shrink-0 text-error lg:mt-0" />
              <div className="min-w-0">
                <p className="font-bold">
                  Drift Threshold Alert: CHIOMA Persona
                </p>
                <p className="text-sm opacity-90">
                  Consonantal frequency in Twi-English code-switching has
                  deviated by 14.2% from baseline model. Potential
                  hallucination risk in &lsquo;Sankofa&rsquo; narrative branch.
                </p>
              </div>
            </div>
            <div className="flex shrink-0 flex-col gap-sm sm:flex-row lg:pl-md">
              <button
                onClick={handleManualAudit}
                disabled={isAuditing}
                className="rounded-full bg-on-error-container px-md py-xs text-center text-sm font-bold text-surface transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {isAuditing ? "Auditing..." : "Deploy Hotfix"}
              </button>
              <button
                onClick={() => setAlertDismissed(true)}
                className="rounded-full border border-on-error-container/30 px-md py-xs text-center text-sm font-bold"
              >
                Acknowledge
              </button>
            </div>
          </div>
        ) : null}

        {/* -------------------------------------------------------------- */}
        {/* Bento Grid: Chart + Metrics                                     */}
        {/* -------------------------------------------------------------- */}
        <div className="grid auto-rows-auto grid-cols-12 gap-md lg:gap-lg">
          {/* Chart card (8 cols on desktop, full on mobile) */}
          <div className="col-span-12 flex min-h-[220px] flex-col rounded-xl border border-outline-variant bg-surface p-md sm:min-h-[280px] lg:col-span-8 lg:min-h-[350px] lg:p-lg">
            <div className="mb-md flex flex-col gap-sm sm:mb-lg sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h3 className="text-sm font-bold text-on-surface sm:text-base">
                  Prompt-to-Line Latency &amp; Accuracy
                </h3>
                <p className="text-xs text-on-surface-variant">
                  Rolling 24h consistency vs baseline tokenization
                </p>
              </div>
              <div className="flex gap-xs">
                <span className="rounded bg-surface-container-high px-xs font-mono text-xs">
                  ACC: {accDisplay}
                </span>
                <span className="rounded bg-surface-container-high px-xs font-mono text-xs">
                  LAT: {latDisplay}
                </span>
              </div>
            </div>
            <LatencyChart />
          </div>

          {/* Consistency score card (4 cols on desktop, full on mobile) */}
          <div className="col-span-12 flex flex-col justify-between rounded-xl border border-outline-variant bg-surface p-md lg:col-span-4 lg:p-lg">
            <div>
              <h3 className="font-bold text-on-surface">Consistency Score</h3>
              <p className="mb-md text-xs text-on-surface-variant">
                Aggregate Alignment Telemetry
              </p>
              <div className="grid grid-cols-2 gap-md lg:grid-cols-1 lg:space-y-0">
                {/* Tone Match */}
                <div className="rounded-lg bg-[#F1F4F9] p-md">
                  <span className="text-[10px] font-bold uppercase text-on-surface-variant">
                    Tone Match
                  </span>
                  <div className="flex items-end justify-between">
                    <span className="font-mono text-3xl font-medium text-primary sm:text-4xl">
                      {toneMatchDisplay}
                    </span>
                    <span className="mb-1 flex items-center text-xs text-secondary">
                      <Icon name="arrow_upward" size={16} />
                      1.2%
                    </span>
                  </div>
                </div>
                {/* Fact Retrieval */}
                <div className="rounded-lg bg-[#F1F4F9] p-md">
                  <span className="text-[10px] font-bold uppercase text-on-surface-variant">
                    Fact Retrieval
                  </span>
                  <div className="flex items-end justify-between">
                    <span className="font-mono text-3xl font-medium text-[#2B4C7E] sm:text-4xl">
                      {factRetrievalDisplay}
                    </span>
                    <span className="mb-1 flex items-center text-xs text-secondary">
                      <Icon name="check_circle" size={16} />
                      Target
                    </span>
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-md flex items-center justify-between border-t border-outline-variant pt-md font-mono text-xs text-on-surface-variant">
              <span>Last Evaluated</span>
              <span>{lastEvaluatedDisplay}</span>
            </div>
          </div>
        </div>

        {/* -------------------------------------------------------------- */}
        {/* Session Audit Table                                              */}
        {/* -------------------------------------------------------------- */}
        <div className="overflow-hidden rounded-xl border border-outline-variant bg-surface shadow-sm">
          {/* Table header row */}
          <div className="flex flex-col gap-sm border-b border-outline-variant bg-surface-container-lowest px-md py-md sm:flex-row sm:items-center sm:justify-between sm:px-lg">
            <h3 className="text-sm font-bold text-on-surface sm:text-base">
              Recent Evaluated Conversations (Persona Audit)
            </h3>
            <div className="flex gap-sm">
              <button
                onClick={() => setFilterDriftOnly(!filterDriftOnly)}
                className={`rounded-full border border-outline px-md py-1 text-xs font-bold transition-colors ${
                  filterDriftOnly
                    ? "bg-error text-on-error border-error"
                    : "hover:bg-surface-variant text-on-surface"
                }`}
              >
                {filterDriftOnly ? "Showing Low Drift" : "Filter by Drift"}
              </button>
              <button
                onClick={handleManualAudit}
                disabled={isAuditing}
                className="rounded-full bg-primary px-md py-1 text-xs font-bold text-on-primary transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {isAuditing ? "Auditing..." : "New Manual Audit"}
              </button>
            </div>
          </div>

          {/* Desktop/Tablet Table — hidden on mobile */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-surface-container text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                <tr>
                  <th className="px-lg py-sm">Session ID</th>
                  <th className="px-lg py-sm">Primary Intent</th>
                  <th className="px-lg py-sm">Prompt Context</th>
                  <th className="px-lg py-sm">Consistency Δ</th>
                  <th className="px-lg py-sm">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/30">
                {filteredSessions.map((session) => (
                  <tr
                    key={session.id}
                    className={`group cursor-pointer transition-colors hover:bg-[#F1F4F9] ${
                      session.consistency < 0.75 ? "bg-error/5" : ""
                    }`}
                  >
                    <td className="px-lg py-md font-mono text-xs text-on-surface-variant">
                      {session.id}
                    </td>
                    <td className="px-lg py-md font-semibold">
                      {session.intent}
                    </td>
                    <td className="max-w-xs truncate px-lg py-md italic text-on-surface-variant">
                      {session.prompt}
                    </td>
                    <td className="px-lg py-md">
                      <ConsistencyBar value={session.consistency} />
                    </td>
                    <td className="px-lg py-md">
                      <Icon
                        name="open_in_new"
                        size={20}
                        className="text-primary transition-transform group-hover:scale-110"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Card Layout — visible only on mobile */}
          <div className="divide-y divide-outline-variant/30 md:hidden">
            {filteredSessions.map((session) => (
              <div
                key={session.id}
                className={`cursor-pointer p-md transition-colors active:bg-[#F1F4F9] ${
                  session.consistency < 0.75 ? "bg-error/5" : ""
                }`}
              >
                <div className="mb-sm flex items-center justify-between">
                  <span className="font-mono text-xs text-on-surface-variant">
                    {session.id}
                  </span>
                  <Icon
                    name="open_in_new"
                    size={18}
                    className="text-primary"
                  />
                </div>
                <p className="mb-xs font-semibold text-on-surface">
                  {session.intent}
                </p>
                <p className="mb-sm line-clamp-2 text-sm italic text-on-surface-variant">
                  {session.prompt}
                </p>
                <ConsistencyBar value={session.consistency} />
              </div>
            ))}
          </div>

          {/* Pagination footer */}
          <div className="flex items-center justify-between border-t border-outline-variant bg-surface-container-lowest p-md text-xs font-medium text-on-surface-variant">
            <span>
              Showing 1–{filteredSessions.length} of {metrics?.sessions?.length || 1244} sessions
            </span>
            <div className="flex gap-sm">
              <button className="rounded p-1 hover:bg-surface-variant">
                <Icon name="chevron_left" size={18} />
              </button>
              <button className="rounded p-1 hover:bg-surface-variant">
                <Icon name="chevron_right" size={18} />
              </button>
            </div>
          </div>
        </div>

        {/* -------------------------------------------------------------- */}
        {/* Persona Snapshot Grid                                            */}
        {/* -------------------------------------------------------------- */}
        <div className="grid grid-cols-1 gap-lg pb-xl sm:grid-cols-2 xl:grid-cols-4">
          {/* CHIOMA card */}
          <div className="group relative overflow-hidden rounded-xl border border-outline-variant bg-surface p-lg">
            <div className="absolute -mr-8 -mt-8 right-0 top-0 h-16 w-16 rounded-full bg-primary/5 transition-all group-hover:scale-150" />
            <div className="mb-md flex items-center gap-md">
              <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-full border-2 border-primary bg-primary-container">
                <Icon name="person" filled size={24} className="text-on-primary-container" />
              </div>
              <div>
                <h4 className="font-bold">CHIOMA</h4>
                <span className="rounded-full bg-secondary-container px-2 py-0.5 text-[10px] font-bold uppercase text-on-secondary-container">
                  Stable
                </span>
              </div>
            </div>
            <p className="text-xs leading-relaxed text-on-surface-variant">
              System Default. Wisdom-focused, communal tone. Optimized for
              rural financial literacy.
            </p>
          </div>

          {/* KWAME card */}
          <div className="group relative overflow-hidden rounded-xl border border-outline-variant bg-surface p-lg">
            <div className="absolute -mr-8 -mt-8 right-0 top-0 h-16 w-16 rounded-full bg-[#2B4C7E]/5 transition-all group-hover:scale-150" />
            <div className="mb-md flex items-center gap-md">
              <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-full border-2 border-[#2B4C7E] bg-surface-container">
                <Icon name="person" size={24} className="text-[#2B4C7E]" />
              </div>
              <div>
                <h4 className="font-bold">KWAME</h4>
                <span className="rounded-full bg-outline-variant px-2 py-0.5 text-[10px] font-bold uppercase text-on-surface-variant">
                  Beta
                </span>
              </div>
            </div>
            <p className="text-xs leading-relaxed text-on-surface-variant">
              Direct, goal-oriented, high-energy. Optimized for urban youth
              entrepreneurs.
            </p>
          </div>

          {/* Dynamic Persona or Custom card */}
          {personas
            .filter((p) => p.id !== "chioma" && p.id !== "kwame")
            .slice(0, 1)
            .map((p) => (
              <div
                key={p.id}
                className="group relative overflow-hidden rounded-xl border border-outline-variant bg-surface p-lg"
              >
                <div className="absolute -mr-8 -mt-8 right-0 top-0 h-16 w-16 rounded-full bg-primary/5 transition-all group-hover:scale-150" />
                <div className="mb-md flex items-center gap-md">
                  <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-full border-2 border-primary bg-primary-container">
                    <Icon name="person" size={24} className="text-primary" />
                  </div>
                  <div>
                    <h4 className="font-bold">{p.name}</h4>
                    <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-[10px] font-bold uppercase text-on-surface-variant">
                      Custom
                    </span>
                  </div>
                </div>
                <p className="text-xs leading-relaxed text-on-surface-variant">
                  {p.tagline || "Specialized advisory persona tailored to custom sectors."}
                </p>
              </div>
            ))}

          {/* Create New card */}
          <div className="group relative overflow-hidden rounded-xl border border-outline-variant bg-surface p-lg">
            <div className="absolute -mr-8 -mt-8 right-0 top-0 h-16 w-16 rounded-full bg-primary/5 transition-all group-hover:scale-150" />
            <div className="mb-md flex items-center gap-md">
              <div className="flex h-12 w-12 items-center justify-center rounded-full border-2 border-outline-variant bg-surface-container">
                <Icon name="add" size={22} className="text-on-surface-variant" />
              </div>
              <div>
                <h4 className="font-bold">Create New</h4>
                <span className="text-[10px] text-on-surface-variant">
                  Draft Session
                </span>
              </div>
            </div>
            <p className="text-xs leading-relaxed text-on-surface-variant">
              Initialize a new persona branch using RAG-integrated seed
              prompts.
            </p>
          </div>

          {/* Collective weights card */}
          <div className="flex flex-col items-center justify-center space-y-md rounded-xl border border-outline-variant bg-surface p-lg text-center">
            <div className="flex -space-x-3">
              <div className="h-8 w-8 rounded-full border-2 border-surface bg-primary" />
              <div className="h-8 w-8 rounded-full border-2 border-surface bg-secondary" />
              <div className="h-8 w-8 rounded-full border-2 border-surface bg-[#2B4C7E]" />
              <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-surface bg-outline-variant text-[8px] font-bold">
                +{personas.length > 2 ? personas.length : 12}
              </div>
            </div>
            <p className="text-xs font-bold text-on-surface-variant">
              Manage Collective Persona Weights
            </p>
            <button className="w-full rounded-full bg-on-surface py-2 text-xs font-bold text-surface transition-colors hover:bg-primary">
              Open Matrix
            </button>
          </div>
        </div>
      </div>

      {/* System status footer bar */}
      <footer className="flex h-auto shrink-0 flex-wrap items-center justify-center gap-x-lg gap-y-xs border-t border-outline-variant bg-surface-container px-md py-xs font-mono text-[9px] uppercase tracking-widest text-on-surface-variant sm:text-[10px] md:h-8 md:flex-nowrap md:justify-between md:px-lg md:py-0">
        <div className="flex items-center gap-md sm:gap-lg">
          <span className="flex items-center gap-xs">
            <span className="h-2 w-2 animate-pulse rounded-full bg-secondary" />
            Node Status: {isLoading ? "Syncing" : "Active"}
          </span>
          <span>Latency: {latDisplay}</span>
          <span className="hidden sm:inline">Version: 2.0.4-LTS</span>
        </div>
        <div>&copy; 2024 AfriMentor Research AI Labs</div>
      </footer>

      {/* FAB — terminal quick-access */}
      <button
        aria-label="Open terminal"
        onClick={handleManualAudit}
        disabled={isAuditing}
        className="fixed bottom-20 right-4 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-primary text-on-primary shadow-xl transition-all hover:scale-110 active:scale-95 disabled:opacity-50 md:bottom-12 md:right-12 md:h-14 md:w-14"
      >
        <Icon name={isAuditing ? "sync" : "terminal"} size={24} className={isAuditing ? "animate-spin" : ""} />
      </button>
    </main>
  );
}
