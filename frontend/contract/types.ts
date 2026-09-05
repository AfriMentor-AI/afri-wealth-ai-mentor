/**
 * AfriMentor AI — Shared Frontend/Backend API Contract
 * =====================================================
 * G1.3: TypeScript source of truth for every entity the UI needs.
 * Mirrored 1:1 into `openapi.yaml` in this same folder — if you change a
 * shape here, change it there too (see that file's header comment).
 *
 * Consumed by the frontend today via `lib/types.ts`, which re-exports
 * everything from this module — the frontend mock layer (`lib/api.ts`,
 * `lib/mockData.ts`) imports from `@/lib/types`, so it's genuinely
 * building against this contract, not a parallel shape that happens to
 * look similar.
 *
 * Status: STUB. Field names and shapes are a strong starting point for
 * Sprint 2 backend work, not a final spec — expect this to move once
 * Olusegun's review surfaces real backend constraints (DB choice,
 * auth model, pagination approach, etc.).
 *
 * Conventions used throughout:
 * - `id` fields are opaque string identifiers (UUIDs in practice). Never
 *   assume format beyond "string" — don't parse or construct them.
 * - Timestamps are ISO 8601 strings (`"2026-07-28T09:15:00Z"`), always UTC.
 * - Fields ending in `Id` are foreign keys to another entity's `id`.
 * - Every top-level entity that's independently fetchable/persistable has
 *   `id`, and `createdAt`/`updatedAt` where mutation over time is expected.
 */

// ---------------------------------------------------------------------------
// Shared primitive aliases (purely for documentation — these are just
// strings at runtime, TypeScript gives no extra runtime safety here)
// ---------------------------------------------------------------------------

/** Opaque unique identifier. Treat as an opaque string; do not parse. */
export type ID = string;

/** ISO 8601 datetime string, always UTC (e.g. "2026-07-28T09:15:00Z"). */
export type ISODateTime = string;

/** ISO 8601 date-only string (e.g. "2026-07-28"). */
export type ISODate = string;

// ---------------------------------------------------------------------------
// User / Profile
// ---------------------------------------------------------------------------

/**
 * The authentication/account identity. Deliberately separate from
 * `Profile` — `User` is "who's logged in," `Profile` is "the business
 * context they gave us during Intake." Keeping these separate means auth
 * can evolve (email vs. phone vs. SSO) without reshaping business data.
 */
export interface User {
  id: ID;
  /** Phone number OR email, whichever the eventual auth method uses. At
   * least one of these two must be present. */
  phoneNumber?: string;
  email?: string;
  /** BCP-47 locale tag, e.g. "en-GH". Defaults to "en" if unset. */
  locale?: string;
  createdAt: ISODateTime;
}

/** The business/intake context collected in the 4-step Intake flow. */
export interface Profile {
  userId: ID;
  name: string;
  businessName: string;
  location: string;
  sector: string;
  educationLevel: string;
  timeAvailablePerWeek: string;
  constraints: string[];
  /** FK to the Persona currently assigned to this user. Nullable until
   * Persona Selection is completed. */
  personaId: ID | null;
  createdAt: ISODateTime;
  updatedAt: ISODateTime;
}

// ---------------------------------------------------------------------------
// Persona
// ---------------------------------------------------------------------------

export interface Persona {
  id: ID;
  name: string;
  tagline: string;
  /** Whether to show the "Recommended for you" badge for the CURRENT
   * user. This is user-specific, computed server-side from Profile.sector
   * — it is NOT a static property of the Persona itself. When this moves
   * off mock data, expect it on a per-request DTO
   * (e.g. `PersonaWithRecommendation`), not the base Persona resource. */
  isRecommended: boolean;
  /** Optional FK into Epic H's trait-model schema (US-H3), once that
   * exists. Left optional/untyped-further here deliberately — Epic H
   * owns that shape, this contract just reserves the linkage point. */
  traitProfileId?: ID;
}

// ---------------------------------------------------------------------------
// Goal / Milestone / Commitment
// ---------------------------------------------------------------------------

export interface Goal {
  id: ID;
  userId: ID;
  title: string;
  /** Server-computed from this goal's milestones — the client should
   * treat this as read-only, never derive/send it. */
  progressPct: number;
  deadline?: ISODate;
  createdAt: ISODateTime;
  updatedAt: ISODateTime;
}

export type MilestoneStatus = "done" | "in_progress" | "blocked" | "upcoming";

export interface Milestone {
  id: ID;
  goalId: ID;
  title: string;
  status: MilestoneStatus;
  /** Sequence position within the goal's milestone road, 0-indexed.
   * Explicit rather than array-order so reordering is a single-field
   * update, not a full-list rewrite. */
  order: number;
  createdAt: ISODateTime;
  updatedAt: ISODateTime;
}

export type CommitmentStatus = "done" | "in_progress" | "blocked";

/** A specific, tagged promise the user made in conversation with Chioma,
 * surfaced on the Goal Milestone Path screen ("Tagged Commitments"). */
export interface Commitment {
  id: ID;
  goalId: ID;
  title: string;
  status: CommitmentStatus;
  /** Present only when status is "blocked" — a mentor-suggested next step. */
  mentorHelpNote?: string;
  /** FK to the ChatMessage this commitment was tagged from, if any —
   * lets the UI deep-link back to the conversation that created it. */
  sourceChatMessageId?: ID;
  createdAt: ISODateTime;
  updatedAt: ISODateTime;
}

// ---------------------------------------------------------------------------
// Chat
// ---------------------------------------------------------------------------

export type ChatSender = "user" | "mentor";

export interface ChatMessage {
  id: ID;
  userId: ID;
  /** Which Persona was "speaking" for mentor messages. Omitted/ignored
   * for sender: "user" messages. */
  personaId?: ID;
  sender: ChatSender;
  content: string;
  /**
   * Structured list of citations into the RAG corpus, allowing for multiple
   * sources. The UI may choose to display only the first or most relevant one.
   */
  citations?: Array<{ label: string }>;
  /**
   * True if the user's message was flagged as a potential commitment,
   * prompting the "Tag It" UI.
   */
  is_commitment_candidate?: boolean;
  created_at: ISODateTime;
}

// ---------------------------------------------------------------------------
// Insight Library
// ---------------------------------------------------------------------------

export interface InsightItem {
  id: ID;
  title: string;
  summary: string;
  category: string;
  durationMinutes: number;
  isAudio: boolean;
  /** URL to the audio/article asset. Absent in mock data today; required
   * once real content exists. */
  mediaUrl?: string;
  createdAt: ISODateTime;
}

/** Per-user favorite marker — modeled as a separate join concept rather
 * than a boolean on InsightItem itself, since favorites are user-specific
 * and InsightItem is shared/global content. */
export interface InsightFavorite {
  userId: ID;
  insightId: ID;
  createdAt: ISODateTime;
}

// ---------------------------------------------------------------------------
// Feedback Survey
// ---------------------------------------------------------------------------

/** One submission of the Feedback Survey modal (NPS-style, 1-10). */
export interface FeedbackSurvey {
  id: ID;
  userId: ID;
  /** 1-10 "likelihood to recommend" score, per the reference screen. */
  npsScore: number;
  comment?: string;
  submittedAt: ISODateTime;
}

// ---------------------------------------------------------------------------
// Daily Action
// ---------------------------------------------------------------------------

export interface DailyAction {
  id: ID;
  userId: ID;
  /** The specific calendar day this action is FOR — not when it was
   * created. Lets "today's action" be a simple date lookup. */
  date: ISODate;
  title: string;
  description: string;
  estimatedMinutes: number;
  linkedGoalId: ID;
  done: boolean;
  createdAt: ISODateTime;
  updatedAt: ISODateTime;
}

// ---------------------------------------------------------------------------
// Streak / Badges
// ---------------------------------------------------------------------------

/** Aggregate stat, one per user — not independently creatable, always
 * fetched (and recomputed server-side) as a whole. */
export interface StreakStat {
  userId: ID;
  currentStreakDays: number;
  longestStreakDays: number;
  actionsCompletedTotal: number;
  updatedAt: ISODateTime;
}

export interface Badge {
  id: ID;
  label: string;
  description?: string;
  /** Material Symbols icon name, matching the Icon component's `name` prop. */
  iconName?: string;
}

/** Per-user earned/locked state for a Badge — same reasoning as
 * InsightFavorite: Badge is a shared catalog entry, earning it is
 * user-specific. */
export interface UserBadge {
  userId: ID;
  badgeId: ID;
  /** Present only once earned; absent/null means still locked. */
  earnedAt: ISODateTime | null;
}

/** Badge catalog entry joined with the current user's earned/locked
 * state — what GET /progress/badges actually returns. Mirrors the
 * `BadgeWithStatus` schema in openapi.yaml. */
export type BadgeWithStatus = Badge & { earnedAt: ISODateTime | null };

// ---------------------------------------------------------------------------
// RAG Corpus (Knowledge & Retrieval)
// ---------------------------------------------------------------------------

export interface RagChunkMetadata {
  title?: string;
  author?: string;
  sector?: string;
  market?: string;
  source_origin?: string;
  channel?: string;
  filename?: string;
  content_type?: string;
  tier?: number;
}

export interface RagChunk {
  chunk_id: string;
  doc_id?: string;
  content: string;
  score: number;
  metadata: RagChunkMetadata;
  retrieval_method?: string;
}

export interface RagQueryResponse {
  query: string;
  results: RagChunk[];
  total: number;
}

export interface RagCorpusStats {
  documents: {
    total: number;
    total_chunks: number;
    by_status: Record<string, number>;
    by_country: Record<string, number>;
    by_sector: Record<string, number>;
    by_tier?: Record<string, number>;
  };
  vectors: {
    active_count: number | null;
    collection: string | null;
    embedding_dim: number;
  };
  index_size: {
    document_bytes: number;
    vector_bytes: number | null;
    total_bytes: number | null;
  };
  latency_ms?: Record<string, number>;
}

