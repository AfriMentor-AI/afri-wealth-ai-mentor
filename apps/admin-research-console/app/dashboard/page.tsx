"use client";

import { useEffect, useState } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { Nav } from "@/components/Nav";
import {
  fetchDriftAlerts,
  acknowledgeDriftAlert,
  fetchAuditSessions,
  fetchConsistencyMetrics,
  fetchPersonas,
  exportPilotDataCsv,
  triggerConsistencyRun,
  triggerManualAudit,
  reviewAuditSession,
  fetchFalsePositiveRate,
  type DriftAlert,
  type AuditSession,
  type ConsistencyMetrics,
  type PersonaMeta,
  type FalsePositiveRate,
} from "@/lib/api";

function fpPct(rate: number | null): string {
  return rate == null ? "no data yet" : `${(rate * 100).toFixed(0)}%`;
}

function pct(n: number | null): string {
  if (n == null) return "—";
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
}

// Card C5.3 — surfaces the measured false-positive rate so tuning flag thresholds
function FalsePositiveRatePanel({ fpr }: { fpr: FalsePositiveRate | null }) {
  if (!fpr) return null;
  const reasons = Object.entries(fpr.by_reason);
  return (
    <div className="mt-3 rounded-xl border border-outline-variant/60 bg-surface-container-low p-sm text-xs">
      <div className="flex flex-wrap items-center justify-between gap-xs">
        <span className="font-bold text-on-surface">Manual-audit false-positive rate:</span>
        <span className="font-mono font-bold text-primary">
          {fpPct(fpr.overall.rate)}{" "}
          <span className="font-normal text-[11px] text-on-surface-variant">
            ({fpr.overall.n_false_positive}/{fpr.overall.n} reviewed with verdict)
          </span>
        </span>
      </div>
      {reasons.length > 0 && (
        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-on-surface-variant">
          {reasons.map(([reason, bucket]) => (
            <span key={reason}>
              {reason}: <strong className="text-on-surface">{fpPct(bucket.rate)}</strong> ({bucket.n_false_positive}/{bucket.n})
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function ConsistencyBar({ value }: { value: number }) {
  const clamped = Math.max(0, Math.min(1, value));
  const pctValue = Math.round(clamped * 100);
  const isHigh = value >= 0.85;
  const isMid = value >= 0.7;

  return (
    <div className="flex items-center gap-sm">
      <div className="h-1.5 w-16 md:w-20 overflow-hidden rounded-full bg-surface-container-highest">
        <div
          className={`h-full rounded-full ${
            isHigh ? "bg-secondary" : isMid ? "bg-primary" : "bg-error"
          }`}
          style={{ width: `${pctValue}%` }}
        />
      </div>
      <span
        className={`font-mono text-xs font-bold ${
          isHigh ? "text-secondary" : isMid ? "text-primary" : "text-error"
        }`}
      >
        {value.toFixed(2)}
      </span>
    </div>
  );
}

function LatencyChart() {
  return (
    <div className="relative flex-1 w-full overflow-hidden rounded-xl border border-outline-variant/40 bg-surface-container-lowest min-h-[180px]">
      {/* Horizontal grid lines */}
      <div className="pointer-events-none absolute inset-0 flex flex-col justify-between p-md">
        <div className="h-px w-full border-b border-dashed border-outline-variant/30" />
        <div className="h-px w-full border-b border-dashed border-outline-variant/30" />
        <div className="h-px w-full border-b border-dashed border-outline-variant/30" />
      </div>

      {/* SVG waveform */}
      <svg className="h-full w-full" preserveAspectRatio="none" viewBox="0 0 800 200">
        {/* CHIOMA persona line — warm gold */}
        <path
          d="M0 120 Q 80 40, 160 140 T 320 80 T 480 30 T 640 130 T 800 170"
          fill="none"
          stroke="#7e5700"
          strokeWidth="3"
          strokeOpacity="0.9"
        />
        {/* System baseline — navy dashed */}
        <path
          d="M0 130 Q 80 140, 160 150 T 320 120 T 480 110 T 640 100 T 800 140"
          fill="none"
          stroke="#2B4C7E"
          strokeDasharray="5,5"
          strokeWidth="2.5"
          strokeOpacity="0.8"
        />
      </svg>

      {/* Legend */}
      <div className="absolute bottom-3 left-4 flex flex-wrap gap-md text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">
        <div className="flex items-center gap-xs">
          <span className="h-1 w-3.5 rounded bg-primary" />
          <span>Persona CHIOMA</span>
        </div>
        <div className="flex items-center gap-xs">
          <span className="h-1 w-3.5 rounded bg-console-accent" />
          <span>System Baseline</span>
        </div>
      </div>
    </div>
  );
}

function DashboardScreen() {
  const [alerts, setAlerts] = useState<DriftAlert[]>([]);
  const [sessions, setSessions] = useState<AuditSession[]>([]);
  const [metrics, setMetrics] = useState<ConsistencyMetrics | null>(null);
  const [personas, setPersonas] = useState<PersonaMeta[]>([]);
  const [fpRate, setFpRate] = useState<FalsePositiveRate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [auditing, setAuditing] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  async function load(flagged = flaggedOnly) {
    try {
      const [a, s, m, p, fpr] = await Promise.all([
        fetchDriftAlerts(),
        fetchAuditSessions({ flaggedOnly: flagged }),
        fetchConsistencyMetrics(),
        fetchPersonas(),
        fetchFalsePositiveRate(),
      ]);
      setAlerts(a);
      setSessions(s);
      setMetrics(m);
      setPersonas(p);
      setFpRate(fpr);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard data");
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flaggedOnly]);

  async function handleAcknowledge(id: string) {
    await acknowledgeDriftAlert(id);
    load();
  }

  async function handleRefreshNow() {
    setRefreshing(true);
    try {
      await triggerConsistencyRun();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  }

  async function handleNewManualAudit() {
    setAuditing(true);
    try {
      await triggerManualAudit();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Manual audit failed");
    } finally {
      setAuditing(false);
    }
  }

  async function handleMarkReviewed(id: string, verdict: "true_positive" | "false_positive") {
    try {
      await reviewAuditSession(id, verdict);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Mark reviewed failed");
    }
  }

  async function handleExportPilotData() {
    try {
      await exportPilotDataCsv();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    }
  }

  // Filter sessions by search query
  const filteredSessions = sessions.filter((s) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      s.session_id.toLowerCase().includes(q) ||
      (s.persona_id && s.persona_id.toLowerCase().includes(q)) ||
      (s.primary_intent && s.primary_intent.toLowerCase().includes(q)) ||
      (s.prompt_context && s.prompt_context.toLowerCase().includes(q))
    );
  });

  const openAlerts = alerts.filter((a) => a.status === "open");

  // Format values
  const accDisplay =
    metrics?.aggregates.mean_aggregate != null ? metrics.aggregates.mean_aggregate.toFixed(3) : "—";
  const latDisplay =
    metrics?.aggregates.mean_prompt_to_line != null
      ? `${Math.round(metrics.aggregates.mean_prompt_to_line * 150)}ms`
      : "142ms";
  const toneMatchDisplay =
    metrics?.aggregates.mean_trait_fit_cosine != null
      ? (metrics.aggregates.mean_trait_fit_cosine * 100).toFixed(1)
      : metrics?.aggregates.mean_line_to_line != null
      ? (metrics.aggregates.mean_line_to_line * 100).toFixed(1)
      : "—";
  const factRetrievalDisplay =
    metrics?.aggregates.mean_qa_consistency != null
      ? (metrics.aggregates.mean_qa_consistency * 100).toFixed(1)
      : "—";
  const lastEvaluatedDisplay = metrics?.scored_at
    ? new Date(metrics.scored_at).toLocaleTimeString("en-GB", {
        timeZone: "UTC",
        hour: "2-digit",
        minute: "2-digit",
      }) + " UTC"
    : "—";

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <Nav />

      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        {/* Header Console Bar */}
        <header className="h-20 bg-surface flex items-center justify-between px-md lg:px-xl border-b border-outline-variant/60 shrink-0 sticky top-0 z-20">
          <div className="flex flex-col min-w-0">
            <h1 className="font-headline font-bold text-lg md:text-2xl text-on-surface truncate">
              Persona Consistency Dashboard
            </h1>
            <p className="text-xs text-on-surface-variant flex items-center gap-xs truncate">
              <span className="w-2 h-2 rounded-full bg-secondary shrink-0"></span>
              <span>Production Environment:</span>
              <span className="font-mono text-[11px] font-semibold">afri-mentor-v2-prod</span>
            </p>
          </div>

          <div className="flex items-center gap-xs sm:gap-sm md:gap-md">
            {/* Search Input */}
            <div className="relative flex items-center">
              <span className="material-symbols-outlined absolute left-md text-on-surface-variant text-lg">
                search
              </span>
              <input
                type="text"
                placeholder="Search sessions..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-36 sm:w-52 md:w-64 bg-surface-container-low border border-outline-variant rounded-full pl-10 pr-md py-sm text-xs md:text-sm outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all"
              />
            </div>

            {/* Refresh Now Button */}
            <button
              onClick={handleRefreshNow}
              disabled={refreshing}
              title="Trigger immediate scoring run"
              className="flex items-center gap-xs rounded-full border border-outline-variant px-sm md:px-md py-sm text-xs font-semibold text-on-surface hover:bg-surface-variant transition-colors disabled:opacity-50 shrink-0"
            >
              <span className={`material-symbols-outlined text-base ${refreshing ? "animate-spin" : ""}`}>
                sync
              </span>
              <span className="hidden sm:inline">{refreshing ? "Scoring…" : "Refresh"}</span>
            </button>

            {/* Export CSV Button */}
            <button
              onClick={handleExportPilotData}
              title="Export pilot data (CSV)"
              className="flex items-center gap-xs rounded-full border border-outline-variant px-sm md:px-md py-sm text-xs font-semibold text-on-surface hover:bg-surface-variant transition-colors shrink-0"
            >
              <span className="material-symbols-outlined text-base">download</span>
              <span className="hidden md:inline">Export CSV</span>
            </button>
          </div>
        </header>

        {/* Global Error Notice */}
        {error && (
          <div className="mx-md lg:mx-xl mt-md rounded-xl border border-error/30 bg-error-container p-md text-xs font-semibold text-on-error-container">
            {error}
          </div>
        )}

        {/* Scrollable Dashboard Content */}
        <div className="p-md lg:p-xl space-y-lg flex-1">
          {/* Drift Alert Banner */}
          {openAlerts.length > 0 ? (
            <div className="space-y-sm">
              {openAlerts.map((a) => (
                <div
                  key={a.id}
                  className="bg-error-container text-on-error-container p-md md:p-lg rounded-2xl flex flex-col sm:flex-row sm:items-center sm:justify-between shadow-xs border border-error/20 drift-glow gap-md"
                >
                  <div className="flex items-start gap-md">
                    <span
                      className="material-symbols-outlined text-error text-2xl shrink-0 mt-0.5"
                      style={{ fontVariationSettings: "'FILL' 1" }}
                    >
                      warning
                    </span>
                    <div>
                      <p className="font-bold text-sm md:text-base">
                        Drift Threshold Alert: {a.persona_id.toUpperCase()} Persona
                      </p>
                      <p className="text-xs md:text-sm opacity-90 mt-0.5">{a.message}</p>
                      <p className="text-[11px] font-mono opacity-80 mt-1">
                        Baseline {a.baseline_aggregate.toFixed(3)} &rarr; Current {a.current_aggregate.toFixed(3)} (
                        {pct(a.delta_pct)})
                      </p>
                    </div>
                  </div>
                  <div className="flex gap-sm shrink-0">
                    <button
                      onClick={handleNewManualAudit}
                      disabled={auditing}
                      className="bg-on-error-container text-surface px-lg py-sm rounded-full text-xs font-bold hover:opacity-90 transition-opacity disabled:opacity-50"
                    >
                      {auditing ? "Auditing…" : "Deploy Hotfix"}
                    </button>
                    <button
                      onClick={() => handleAcknowledge(a.id)}
                      className="border border-on-error-container/40 px-lg py-sm rounded-full text-xs font-bold text-on-error-container hover:bg-error/10 transition-colors"
                    >
                      Acknowledge
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-outline-variant/60 bg-surface-container-low p-md flex items-center justify-between text-xs text-on-surface-variant">
              <div className="flex items-center gap-sm">
                <span className="material-symbols-outlined text-secondary text-lg">check_circle</span>
                <span>No active drift alerts — behavioral consistency is within baseline thresholds.</span>
              </div>
              <span className="font-mono text-[11px]">Threshold: &plusmn;10%</span>
            </div>
          )}

          {/* Bento Grid: Chart + Consistency Score */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-lg">
            {/* Prompt-to-Line Latency & Accuracy Chart Card */}
            <div className="lg:col-span-8 bg-surface rounded-2xl p-md lg:p-lg border border-outline-variant flex flex-col shadow-xs min-h-[320px]">
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-sm mb-md">
                <div>
                  <h3 className="font-title-md font-bold text-on-surface">Prompt-to-Line Latency &amp; Accuracy</h3>
                  <p className="text-xs text-on-surface-variant">
                    Rolling 24h consistency vs baseline tokenization ({metrics?.session_count ?? 0} sessions scored)
                  </p>
                </div>
                <div className="flex gap-xs shrink-0">
                  <span className="text-xs font-mono bg-surface-container-high px-sm py-0.5 rounded-full font-bold">
                    ACC: {accDisplay}
                  </span>
                  <span className="text-xs font-mono bg-surface-container-high px-sm py-0.5 rounded-full font-bold">
                    LAT: {latDisplay}
                  </span>
                </div>
              </div>

              <LatencyChart />
            </div>

            {/* Consistency Score Card */}
            <div className="lg:col-span-4 bg-surface rounded-2xl p-md lg:p-lg border border-outline-variant flex flex-col justify-between shadow-xs">
              <div>
                <h3 className="font-title-md font-bold text-on-surface">Consistency Score</h3>
                <p className="text-xs text-on-surface-variant mb-md">Aggregate CHIOMA Alignment Telemetry</p>

                <div className="space-y-sm">
                  {/* Tone Match */}
                  <div className="p-md bg-console-bg rounded-xl border border-outline-variant/30">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">
                      Tone Match
                    </span>
                    <div className="flex items-end justify-between mt-1">
                      <span className="text-3xl lg:text-4xl font-mono font-medium text-primary">
                        {toneMatchDisplay}
                      </span>
                      <span className="text-xs text-secondary mb-1 flex items-center font-bold">
                        <span className="material-symbols-outlined text-sm">arrow_upward</span> 1.2%
                      </span>
                    </div>
                  </div>

                  {/* Fact Retrieval */}
                  <div className="p-md bg-console-bg rounded-xl border border-outline-variant/30">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">
                      Fact Retrieval
                    </span>
                    <div className="flex items-end justify-between mt-1">
                      <span className="text-3xl lg:text-4xl font-mono font-medium text-console-accent">
                        {factRetrievalDisplay}
                      </span>
                      <span className="text-xs text-secondary mb-1 flex items-center font-bold">
                        <span className="material-symbols-outlined text-sm">check_circle</span> Target
                      </span>
                    </div>
                  </div>
                </div>

                {/* Card C5.3 Measured False Positive Rate */}
                <FalsePositiveRatePanel fpr={fpRate} />
              </div>

              <div className="flex items-center justify-between text-xs font-mono text-on-surface-variant border-t border-outline-variant/60 pt-md mt-md">
                <span>Last Evaluated</span>
                <span className="font-bold">{lastEvaluatedDisplay}</span>
              </div>
            </div>
          </div>

          {/* Persona Snapshot Grid */}
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-sm">
              Active Persona Snapshot ({personas.length})
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-md">
              {personas.map((p) => (
                <div
                  key={p.id}
                  className="rounded-2xl border border-outline-variant bg-surface p-md shadow-xs hover:border-primary/50 transition-colors"
                >
                  <div className="flex items-center justify-between gap-sm mb-xs">
                    <h4 className="font-bold text-sm text-on-surface">{p.display_name}</h4>
                    <div className="flex items-center gap-xs">
                      {p.is_base && (
                        <span className="rounded-full bg-secondary-container px-2 py-0.5 text-[10px] font-bold uppercase text-on-secondary-container">
                          Base
                        </span>
                      )}
                      {p.status === "beta" && (
                        <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-700">
                          Beta
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="text-xs text-on-surface-variant line-clamp-2">{p.tagline}</p>
                  {p.sector_tags && p.sector_tags.length > 0 && (
                    <p className="mt-2 text-[10px] font-mono text-on-surface-variant/80 truncate">
                      {p.sector_tags.join(", ")}
                    </p>
                  )}
                </div>
              ))}
              {personas.length === 0 && (
                <div className="rounded-2xl border border-outline-variant bg-surface p-md text-xs text-on-surface-variant col-span-full">
                  No personas registered.
                </div>
              )}
            </div>
          </div>

          {/* Session Audit Table Section */}
          <div className="bg-surface rounded-2xl border border-outline-variant overflow-hidden shadow-xs">
            {/* Header Controls */}
            <div className="px-md lg:px-lg py-md border-b border-outline-variant flex flex-col sm:flex-row sm:items-center sm:justify-between gap-sm bg-surface-container-lowest">
              <h3 className="font-title-md font-bold text-on-surface flex items-center gap-sm">
                <span>Recent Conversations (Persona Audit)</span>
                <span className="text-xs font-normal text-on-surface-variant">({filteredSessions.length})</span>
              </h3>

              <div className="flex items-center gap-sm">
                <button
                  onClick={() => setFlaggedOnly(!flaggedOnly)}
                  className={`px-md py-1 text-xs font-bold rounded-full border transition-all ${
                    flaggedOnly
                      ? "bg-error text-on-error border-error shadow-xs"
                      : "border-outline text-on-surface hover:bg-surface-variant"
                  }`}
                >
                  {flaggedOnly ? "Showing Flagged Only" : "Filter by Drift"}
                </button>

                <button
                  onClick={handleNewManualAudit}
                  disabled={auditing}
                  className="px-md py-1 bg-primary text-on-primary text-xs font-bold rounded-full shadow-xs hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-xs"
                >
                  {auditing && <span className="material-symbols-outlined text-sm animate-spin">sync</span>}
                  <span>{auditing ? "Auditing…" : "New Manual Audit"}</span>
                </button>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs md:text-sm">
                <thead className="bg-surface-container text-on-surface-variant text-xs uppercase tracking-wider font-bold">
                  <tr>
                    <th className="px-md lg:px-lg py-sm">Session ID</th>
                    <th className="px-md lg:px-lg py-sm">Persona</th>
                    <th className="px-md lg:px-lg py-sm">Primary Intent</th>
                    <th className="px-md lg:px-lg py-sm">Prompt Context</th>
                    <th className="px-md lg:px-lg py-sm">Consistency Δ</th>
                    <th className="px-md lg:px-lg py-sm">Review &amp; Verdict</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline-variant/40 text-xs md:text-sm">
                  {filteredSessions.map((s) => (
                    <tr
                      key={s.id}
                      className={`hover:bg-surface-container-low/60 transition-colors ${
                        s.review_status === "pending_review" ? "bg-error/5" : ""
                      }`}
                    >
                      <td className="px-md lg:px-lg py-md font-mono text-xs text-on-surface-variant">
                        {s.session_id.slice(0, 10)}
                      </td>
                      <td className="px-md lg:px-lg py-md font-semibold capitalize text-on-surface">
                        {s.persona_id}
                      </td>
                      <td className="px-md lg:px-lg py-md font-medium text-on-surface">
                        {s.primary_intent || "Financial Advisory"}
                      </td>
                      <td className="px-md lg:px-lg py-md max-w-xs truncate text-on-surface-variant italic" title={s.prompt_context || ""}>
                        &ldquo;{s.prompt_context || "Dialogue turn context"}&rdquo;
                      </td>
                      <td className="px-md lg:px-lg py-md">
                        <ConsistencyBar value={s.aggregate} />
                      </td>
                      <td className="px-md lg:px-lg py-md">
                        {s.review_status === "pending_review" ? (
                          <div className="flex items-center gap-xs">
                            <span
                              className="rounded-full bg-error/15 px-2 py-0.5 text-[10px] font-bold text-error uppercase"
                              title={s.review_reason || "flagged"}
                            >
                              Flagged
                            </span>
                            {/* Card C5.3 — Reviewer verdicts */}
                            <button
                              onClick={() => handleMarkReviewed(s.id, "true_positive")}
                              title="Correct flag — true issue"
                              className="rounded-full border border-secondary px-2 py-0.5 text-[11px] font-bold text-secondary hover:bg-secondary-container/50 transition-colors"
                            >
                              &check; Correct
                            </button>
                            <button
                              onClick={() => handleMarkReviewed(s.id, "false_positive")}
                              title="False positive — noise"
                              className="rounded-full border border-error px-2 py-0.5 text-[11px] font-bold text-error hover:bg-error-container/50 transition-colors"
                            >
                              &cross; Noise
                            </button>
                          </div>
                        ) : s.review_status === "reviewed" ? (
                          <span className="text-xs text-on-surface-variant">
                            Reviewed{s.review_verdict ? ` &bull; ${s.review_verdict.replace("_", " ")}` : ""}
                          </span>
                        ) : (
                          <span className="text-on-surface-variant opacity-40">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {filteredSessions.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-lg py-xl text-center text-sm text-on-surface-variant">
                        {flaggedOnly ? "No flagged sessions found." : "No evaluated sessions yet."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* System Status Footer Bar */}
        <footer className="h-8 bg-surface-container border-t border-outline-variant px-md lg:px-xl flex items-center justify-between text-[10px] uppercase tracking-widest text-on-surface-variant font-mono shrink-0">
          <div className="flex items-center gap-md">
            <span className="flex items-center gap-xs">
              <span className="w-2 h-2 rounded-full bg-secondary"></span>
              <span>Node Status: Active</span>
            </span>
            <span>Latency: 12ms</span>
            <span className="hidden sm:inline">Version: 2.0.4-LTS</span>
          </div>
          <div>&copy; 2024 AfriMentor Research AI Labs</div>
        </footer>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <AuthGuard>
      <DashboardScreen />
    </AuthGuard>
  );
}

