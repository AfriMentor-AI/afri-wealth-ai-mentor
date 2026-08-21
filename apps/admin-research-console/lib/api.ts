import { apiFetch } from "./session";

// ── RAG Corpus Admin (rag-corpus-service, card C2.2) ────────────────────────

export interface DocumentRow {
  id: string;
  filename: string;
  source_origin: string;
  figure_id: string | null;
  market: string | null;
  language: string;
  status: string;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  title: string | null;
  author: string | null;
  sector: string | null;
  content_type: string | null;
  published_date: string | null;
  source_url: string | null;
  channel: string | null;
  byte_size: number;
}

export interface CorpusStats {
  documents: {
    total: number;
    total_chunks: number;
    by_status: Record<string, number>;
    by_country: Record<string, number>;
    by_sector: Record<string, number>;
  };
  vectors: { active_count: number | null; collection: string | null; embedding_dim: number };
  index_size: {
    document_bytes: number;
    vector_bytes: number | null;
    total_bytes: number | null;
    vector_bytes_is_estimate: boolean;
  };
  latency_ms: Record<string, number>;
}

export interface QueryResult {
  query: string;
  results: Array<Record<string, unknown>>;
  total: number;
}

export async function fetchDocuments(q?: string): Promise<{ documents: DocumentRow[]; total: number }> {
  const qs = q ? `?q=${encodeURIComponent(q)}` : "";
  const res = await apiFetch(`/api/v1/rag/documents${qs}`);
  if (!res.ok) throw new Error(`fetchDocuments failed: ${res.status}`);
  const documents: DocumentRow[] = await res.json();
  const total = Number(res.headers.get("X-Total-Count") ?? documents.length);
  return { documents, total };
}

export async function fetchCorpusStats(): Promise<CorpusStats> {
  const res = await apiFetch("/api/v1/rag/stats");
  if (!res.ok) throw new Error(`fetchCorpusStats failed: ${res.status}`);
  return res.json();
}

export async function ingestDocument(body: {
  filename: string;
  text: string;
  title?: string;
  author?: string;
  sector?: string;
}): Promise<DocumentRow> {
  const res = await apiFetch("/api/v1/rag/documents", { method: "POST", body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`ingestDocument failed: ${res.status}`);
  return res.json();
}

export async function runTestQuery(query: string, topK = 3): Promise<QueryResult> {
  const res = await apiFetch("/api/v1/rag/query", {
    method: "POST",
    body: JSON.stringify({ query, top_k: topK }),
  });
  if (!res.ok) throw new Error(`runTestQuery failed: ${res.status}`);
  return res.json();
}

/** Every export endpoint requires the console's bearer token (X-User-Roles
 * gate at the service, Authorization at the gateway) — a plain `<a href>`
 * navigation never sends either, since the token lives in localStorage, not
 * a cookie. Fetch it authenticated instead, then hand the browser a Blob to
 * save under a real filename (Content-Disposition isn't honored on
 * object: URLs, so the name has to come from here). */
export async function downloadCsv(path: string, filename: string): Promise<void> {
  const res = await apiFetch(path);
  if (!res.ok) throw new Error(`Export failed: ${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function exportDocumentsCsv(): Promise<void> {
  return downloadCsv("/api/v1/rag/documents/export.csv", "rag-documents.csv");
}

export function exportPilotDataCsv(): Promise<void> {
  return downloadCsv("/api/v1/research/export/pilot-data.csv", "pilot-data-export.csv");
}

// ── Persona Consistency Dashboard (research-evaluation-service, card O4.1) ──

export interface DriftAlert {
  id: string;
  job_run_id: string;
  persona_id: string;
  baseline_aggregate: number;
  current_aggregate: number;
  delta_pct: number;
  message: string;
  status: string;
  created_at: string;
  acknowledged_at: string | null;
}

export interface AuditSession {
  session_id: string;
  persona_id: string;
  primary_intent: string | null;
  prompt_context: string | null;
  consistency_delta_pct: number | null;
  aggregate: number;
  scored_at: string | null;
}

export interface RollingMetric {
  score: number;
  raw_score: number;
  prior_score: number | null;
  delta_pct: number | null;
  trend_direction: "up" | "down" | "flat" | null;
  sample_count: number;
}

export interface Rolling24hMetrics {
  window_hours: number;
  sample_count: number;
  last_evaluated: string | null;
  tone_match: RollingMetric;
  fact_retrieval: RollingMetric;
}

export interface ConsistencyMetrics {
  job_run_id: string | null;
  session_count: number;
  scored_at: string | null;
  aggregates: {
    mean_prompt_to_line: number;
    mean_line_to_line: number;
    mean_qa_consistency: number;
    mean_aggregate: number;
    // Card C4.1 — CHIOMA trait-fit alignment + composite blend. Optional so the
    // console keeps rendering against a backend that has not shipped C4.1 yet.
    mean_trait_fit_cosine?: number;
    mean_composite?: number;
    mean_tone_match?: number;
    mean_fact_retrieval?: number;
  };
  rolling_24h?: Rolling24hMetrics;
  sessions: Array<{
    conversation_id: string;
    persona_id: string;
    prompt_to_line: number;
    line_to_line: number;
    qa_consistency: number;
    aggregate: number;
    trait_fit_cosine?: number | null;
    composite_score?: number | null;
    tone_match_score?: number | null;
    fact_retrieval_score?: number | null;
    turn_count: number;
    scored_at: string | null;
  }>;
}

export async function fetchDriftAlerts(status?: string): Promise<DriftAlert[]> {
  const qs = status ? `?status=${status}` : "";
  const res = await apiFetch(`/api/v1/research/drift-alerts${qs}`);
  if (!res.ok) throw new Error(`fetchDriftAlerts failed: ${res.status}`);
  return (await res.json()).alerts;
}

export async function acknowledgeDriftAlert(id: string): Promise<void> {
  const res = await apiFetch(`/api/v1/research/drift-alerts/${id}/acknowledge`, { method: "POST" });
  if (!res.ok) throw new Error(`acknowledgeDriftAlert failed: ${res.status}`);
}

export async function fetchAuditSessions(minAbsDeltaPct?: number): Promise<AuditSession[]> {
  const qs = minAbsDeltaPct != null ? `?min_abs_delta_pct=${minAbsDeltaPct}` : "";
  const res = await apiFetch(`/api/v1/research/audit-sessions${qs}`);
  if (!res.ok) throw new Error(`fetchAuditSessions failed: ${res.status}`);
  return (await res.json()).sessions;
}

export async function fetchConsistencyMetrics(): Promise<ConsistencyMetrics> {
  const res = await apiFetch("/api/v1/metrics/consistency");
  if (!res.ok) throw new Error(`fetchConsistencyMetrics failed: ${res.status}`);
  return res.json();
}

export async function fetchRolling24hMetrics(): Promise<Rolling24hMetrics> {
  const res = await apiFetch("/api/v1/research/metrics/rolling-24h");
  if (!res.ok) throw new Error(`fetchRolling24hMetrics failed: ${res.status}`);
  return res.json();
}

/** Card C4.1 — force an immediate scoring run behind the dashboard's "Refresh
 * now" button. Admin-gated at the service; the bearer token rides along via
 * apiFetch. Returns the job summary the endpoint emits. */
export async function triggerConsistencyRun(): Promise<Record<string, unknown>> {
  const res = await apiFetch("/api/v1/research/consistency/run", { method: "POST" });
  if (!res.ok) throw new Error(`triggerConsistencyRun failed: ${res.status}`);
  return res.json();
}

// ── Personas (persona-prompt-service) ───────────────────────────────────────

export interface PersonaMeta {
  id: string;
  slug: string;
  display_name: string;
  tagline: string;
  sector_tags: string[];
  template_file: string;
  is_base: boolean;
}

export async function fetchPersonas(): Promise<PersonaMeta[]> {
  const res = await apiFetch("/api/v1/personas");
  if (!res.ok) throw new Error(`fetchPersonas failed: ${res.status}`);
  return res.json();
}
