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

// Card C5.3 — surfaces the measured false-positive rate so tuning the flag
// thresholds (CONSISTENCY_REVIEW_FLOOR / DRIFT_THRESHOLD_PCT, app/config.py)
// is a decision made against real numbers, not a guess. Broken out by reason
// because the floor and the drift threshold are two separate knobs.
function FalsePositiveRatePanel({ fpr }: { fpr: FalsePositiveRate | null }) {
  if (!fpr) return null;
  const reasons = Object.entries(fpr.by_reason);
  return (
    <div className="mb-6 rounded-md border border-border bg-surface-raised px-4 py-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold">Manual-audit false-positive rate</p>
        <p className="text-sm">
          {fpPct(fpr.overall.rate)}{" "}
          <span className="text-xs text-on-surface-dim">
            ({fpr.overall.n_false_positive}/{fpr.overall.n} reviewed sessions with a verdict)
          </span>
        </p>
      </div>
      {reasons.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs text-on-surface-dim">
          {reasons.map(([reason, bucket]) => (
            <span key={reason}>
              {reason}: {fpPct(bucket.rate)} ({bucket.n_false_positive}/{bucket.n})
            </span>
          ))}
        </div>
      )}
      {fpr.overall.n === 0 && (
        <p className="mt-1 text-xs text-on-surface-dim">
          No reviewed sessions carry a verdict yet — use the ✓/✗ buttons below as flagged
          sessions are reviewed.
        </p>
      )}
    </div>
  );
}

function pct(n: number | null): string {
  if (n == null) return "—";
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
}

function DriftBanner({ alerts, onAcknowledge }: { alerts: DriftAlert[]; onAcknowledge: (id: string) => void }) {
  const open = alerts.filter((a) => a.status === "open");
  if (open.length === 0) {
    return (
      <div className="mb-6 rounded-md border border-border bg-surface-raised px-4 py-3 text-sm text-on-surface-dim">
        No open drift alerts.
      </div>
    );
  }
  return (
    <div className="mb-6 space-y-2">
      {open.map((a) => (
        <div key={a.id} className="rounded-md border border-danger/40 bg-danger/10 px-4 py-3">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-danger">
                Drift Threshold Alert: {a.persona_id.toUpperCase()} Persona
              </p>
              <p className="mt-1 text-sm text-on-surface-dim">{a.message}</p>
              <p className="mt-1 text-xs text-on-surface-dim">
                Baseline {a.baseline_aggregate.toFixed(3)} → current {a.current_aggregate.toFixed(3)} (
                {pct(a.delta_pct)})
              </p>
            </div>
            <button
              onClick={() => onAcknowledge(a.id)}
              className="shrink-0 rounded border border-border px-3 py-1.5 text-xs text-on-surface-dim hover:text-on-surface"
            >
              Acknowledge
            </button>
          </div>
        </div>
      ))}
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
  // Card C4.2 — "Filter by Drift" toggle and "New Manual Audit" in-flight flag.
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [auditing, setAuditing] = useState(false);

  // Reads flaggedOnly through a param (not the closure) so the poll below can be
  // re-armed on toggle and always fetch the currently-selected filter.
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
    // Card C4.1 — poll so the aggregate/alignment tiles stay live as the
    // interval scheduler scores new sessions. 30s sits well under the backend's
    // ~2-min recompute and is cheap (four small GETs). Re-armed when the
    // "Filter by Drift" toggle flips (card C4.2) so the poll keeps the filter.
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

  // Card C4.2 — "New Manual Audit": re-score the sample on demand, auto-flagging
  // sessions for review, then reload so the freshly-flagged rows show up.
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

  // Card C4.2 — "Mark reviewed": close the human-review loop on a flagged row.
  // Card C5.3 — verdict is the ground truth the false-positive rate above is
  // computed from; the ✓/✗ buttons pass it directly rather than requiring a
  // separate step a reviewer could skip.
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

  return (
    <div>
      <Nav />
      <main className="mx-auto max-w-6xl px-6 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-xl font-semibold">Persona Consistency Dashboard</h1>
          <div className="flex items-center gap-2">
            <button
              onClick={handleNewManualAudit}
              disabled={auditing}
              className="rounded border border-accent px-3 py-2 text-sm text-accent hover:bg-accent/10 disabled:opacity-50"
            >
              {auditing ? "Auditing…" : "New Manual Audit"}
            </button>
            <button
              onClick={handleRefreshNow}
              disabled={refreshing}
              className="rounded border border-border px-3 py-2 text-sm text-on-surface-dim hover:text-on-surface disabled:opacity-50"
            >
              {refreshing ? "Refreshing…" : "Refresh now"}
            </button>
            <button
              onClick={handleExportPilotData}
              className="rounded border border-border px-3 py-2 text-sm text-on-surface-dim hover:text-on-surface"
            >
              Export pilot data (CSV)
            </button>
          </div>
        </div>

        {error && <p className="mb-4 text-sm text-danger">{error}</p>}

        <DriftBanner alerts={alerts} onAcknowledge={handleAcknowledge} />

        <FalsePositiveRatePanel fpr={fpRate} />

        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="rounded-md border border-border bg-surface-raised p-4">
            <p className="text-xs uppercase tracking-wide text-on-surface-dim">Aggregate consistency</p>
            <p className="mt-1 text-2xl font-semibold">
              {metrics?.aggregates.mean_aggregate != null ? metrics.aggregates.mean_aggregate.toFixed(3) : "—"}
            </p>
            <p className="mt-1 text-xs text-on-surface-dim">
              {metrics?.session_count ?? 0} sessions scored
            </p>
          </div>
          <div className="rounded-md border border-border bg-surface-raised p-4">
            <p className="text-xs uppercase tracking-wide text-on-surface-dim">CHIOMA persona alignment</p>
            <p className="mt-1 text-2xl font-semibold">
              {metrics?.aggregates.mean_trait_fit_cosine != null
                ? metrics.aggregates.mean_trait_fit_cosine.toFixed(3)
                : "—"}
            </p>
            <p className="mt-1 text-xs text-on-surface-dim">trait-fit cosine</p>
          </div>
          <div className="rounded-md border border-border bg-surface-raised p-4">
            <p className="text-xs uppercase tracking-wide text-on-surface-dim">Prompt→line</p>
            <p className="mt-1 text-2xl font-semibold">
              {metrics?.aggregates.mean_prompt_to_line != null
                ? metrics.aggregates.mean_prompt_to_line.toFixed(3)
                : "—"}
            </p>
          </div>
          <div className="rounded-md border border-border bg-surface-raised p-4">
            <p className="text-xs uppercase tracking-wide text-on-surface-dim">Line→line</p>
            <p className="mt-1 text-2xl font-semibold">
              {metrics?.aggregates.mean_line_to_line != null
                ? metrics.aggregates.mean_line_to_line.toFixed(3)
                : "—"}
            </p>
          </div>
          <div className="rounded-md border border-border bg-surface-raised p-4">
            <p className="text-xs uppercase tracking-wide text-on-surface-dim">QA consistency</p>
            <p className="mt-1 text-2xl font-semibold">
              {metrics?.aggregates.mean_qa_consistency != null
                ? metrics.aggregates.mean_qa_consistency.toFixed(3)
                : "—"}
            </p>
          </div>
        </div>

        <div className="mb-6">
          <h2 className="mb-3 text-sm font-semibold text-on-surface-dim">Persona snapshot</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {personas.map((p) => (
              <div key={p.id} className="rounded-md border border-border bg-surface-raised p-4">
                <div className="mb-1 flex items-center justify-between gap-2">
                  <p className="font-semibold">{p.display_name}</p>
                  <div className="flex shrink-0 items-center gap-1">
                    {p.is_base && (
                      <span className="rounded bg-accent/20 px-2 py-0.5 text-xs text-accent">Base</span>
                    )}
                    {p.status === "beta" && (
                      <span className="rounded bg-amber-500/20 px-2 py-0.5 text-xs text-amber-500">
                        Beta
                      </span>
                    )}
                  </div>
                </div>
                <p className="text-sm text-on-surface-dim">{p.tagline}</p>
                <p className="mt-2 text-xs text-on-surface-dim">{p.sector_tags.join(", ")}</p>
              </div>
            ))}
            {personas.length === 0 && (
              <p className="text-sm text-on-surface-dim">No personas returned.</p>
            )}
          </div>
        </div>

        <div>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-on-surface-dim">
              Recent conversations (persona audit)
            </h2>
            <label className="flex cursor-pointer items-center gap-2 text-xs text-on-surface-dim">
              <input
                type="checkbox"
                checked={flaggedOnly}
                onChange={(e) => setFlaggedOnly(e.target.checked)}
                className="h-3.5 w-3.5 accent-accent"
              />
              Filter by Drift
            </label>
          </div>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-raised text-xs uppercase text-on-surface-dim">
                <tr>
                  <th className="px-3 py-2">Session ID</th>
                  <th className="px-3 py-2">Persona</th>
                  <th className="px-3 py-2">Primary intent</th>
                  <th className="px-3 py-2">Prompt context</th>
                  <th className="px-3 py-2">Consistency Δ</th>
                  <th className="px-3 py-2">Review</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.id} className="border-t border-border">
                    <td className="px-3 py-2 font-mono text-xs">{s.session_id.slice(0, 8)}</td>
                    <td className="px-3 py-2 text-on-surface-dim">{s.persona_id}</td>
                    <td className="px-3 py-2">{s.primary_intent || "—"}</td>
                    <td className="max-w-xs truncate px-3 py-2 text-on-surface-dim" title={s.prompt_context || ""}>
                      {s.prompt_context || "—"}
                    </td>
                    <td
                      className={`px-3 py-2 font-medium ${
                        s.consistency_delta_pct != null && Math.abs(s.consistency_delta_pct) >= 10
                          ? "text-danger"
                          : "text-on-surface"
                      }`}
                    >
                      {pct(s.consistency_delta_pct)}
                    </td>
                    <td className="px-3 py-2">
                      {s.review_status === "pending_review" ? (
                        <div className="flex items-center gap-2">
                          <span
                            className="rounded bg-danger/20 px-2 py-0.5 text-xs text-danger"
                            title={s.review_reason || ""}
                          >
                            Pending{s.review_reason ? ` · ${s.review_reason}` : ""}
                          </span>
                          {/* Card C5.3 — the verdict IS the mark-reviewed action, not a
                              separate step: a reviewer who judges the flag correct or
                              wrong records that in the same click. */}
                          <button
                            onClick={() => handleMarkReviewed(s.id, "true_positive")}
                            title="Correct flag — genuine issue"
                            className="shrink-0 rounded border border-border px-2 py-1 text-xs text-on-surface-dim hover:text-on-surface"
                          >
                            ✓ Correct
                          </button>
                          <button
                            onClick={() => handleMarkReviewed(s.id, "false_positive")}
                            title="False positive — flag was noise"
                            className="shrink-0 rounded border border-border px-2 py-1 text-xs text-on-surface-dim hover:text-on-surface"
                          >
                            ✗ False positive
                          </button>
                        </div>
                      ) : s.review_status === "reviewed" ? (
                        <span className="text-xs text-on-surface-dim" title={s.review_reason || ""}>
                          Reviewed{s.review_reason ? ` · ${s.review_reason}` : ""}
                          {s.review_verdict ? ` · ${s.review_verdict.replace("_", " ")}` : ""}
                        </span>
                      ) : (
                        <span className="text-on-surface-dim">—</span>
                      )}
                    </td>
                  </tr>
                ))}
                {sessions.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-3 py-6 text-center text-on-surface-dim">
                      {flaggedOnly ? "No flagged sessions." : "No scored sessions yet."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
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
