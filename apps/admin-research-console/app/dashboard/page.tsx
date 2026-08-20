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
  type DriftAlert,
  type AuditSession,
  type ConsistencyMetrics,
  type PersonaMeta,
} from "@/lib/api";

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
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [a, s, m, p] = await Promise.all([
        fetchDriftAlerts(),
        fetchAuditSessions(),
        fetchConsistencyMetrics(),
        fetchPersonas(),
      ]);
      setAlerts(a);
      setSessions(s);
      setMetrics(m);
      setPersonas(p);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard data");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function handleAcknowledge(id: string) {
    await acknowledgeDriftAlert(id);
    load();
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
          <button
            onClick={handleExportPilotData}
            className="rounded border border-border px-3 py-2 text-sm text-on-surface-dim hover:text-on-surface"
          >
            Export pilot data (CSV)
          </button>
        </div>

        {error && <p className="mb-4 text-sm text-danger">{error}</p>}

        <DriftBanner alerts={alerts} onAcknowledge={handleAcknowledge} />

        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-4">
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
                <div className="mb-1 flex items-center justify-between">
                  <p className="font-semibold">{p.display_name}</p>
                  {p.is_base && (
                    <span className="rounded bg-accent/20 px-2 py-0.5 text-xs text-accent">Base</span>
                  )}
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
          <h2 className="mb-3 text-sm font-semibold text-on-surface-dim">
            Recent conversations (persona audit)
          </h2>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-raised text-xs uppercase text-on-surface-dim">
                <tr>
                  <th className="px-3 py-2">Session ID</th>
                  <th className="px-3 py-2">Persona</th>
                  <th className="px-3 py-2">Primary intent</th>
                  <th className="px-3 py-2">Prompt context</th>
                  <th className="px-3 py-2">Consistency Δ</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.session_id} className="border-t border-border">
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
                  </tr>
                ))}
                {sessions.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-on-surface-dim">
                      No scored sessions yet.
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
