/**
 * AfriMentor AI — Shared API Contract (TypeScript)
 * ==================================================
 * Source of truth for every entity the frontend PWA needs from the backend.
 * `openapi.yaml` in this package mirrors these types field-for-field — if
 * you change one, change the other in the same PR. See README.md for the
 * reconciliation process and known open questions for backend review.
 *
 * Conventions used throughout:
 * - All IDs are opaque strings (UUIDs expected, but frontend must not
 *   assume a specific format).
 * - All timestamps are ISO 8601 strings in UTC (e.g. "2026-07-29T09:15:00Z").
 *   The backend does NOT pre-format timestamps for display (no "09:15 AM"
 *   strings) — that's a frontend formatting concern.
 * - Entities are normalized (foreign keys, not nested objects) to match how
 *   they're actually stored/queried. Nested/composed shapes some screens
 *   want (e.g. a Goal with its Milestones inline) are frontend-side VIEW
 *   types built from multiple entities — see the "View compositions"
 *   section at the bottom, kept separate so backend isn't implicitly
 *   committing to a specific join/embedding shape in every response.
 */

// ---------------------------------------------------------------------------
// User / Profile
// ---------------------------------------------------------------------------

/** The account itself. Auth mechanism (email/phone/OAuth) is intentionally
 * unspecified here — TBD with backend, see README "Open questions". */
export interface User {
  id: string;
  email?: string;
  phone?: string;
  createdAt: string;
  updatedAt: string;
}

/** The mentorship-specific profile captured during Intake (Epic B/Epic C).
 * One-to-one with User via userId. */
export interface Profile {
  userId: string;
  name: string;
  businessName: string;
  location: string;
  sector: string;
  educationLevel: string;
  timeAvailablePerWeek: string;
  constraints: string[];
  /** FK to Persona. Null until the user completes Persona Selection. */
  personaId: string | null;
  createdAt: string;
  updatedAt: string;
}

// ---------------------------------------------------------------------------
// Goal & Milestone
// ---------------------------------------------------------------------------

export interface Goal {
  id: string;
  userId: string;
  title: string;
  /** 0-100. Server-computed from the goal's Milestones — frontend should
   * treat this as read-only, never derive/override it client-side. */
  progressPct: number;
  deadline?: string;
  createdAt: string;
  updatedAt: string;
}

export type MilestoneStatus = "done" | "in_progress" | "blocked" | "upcoming";

export interface Milestone {
  id: string;
  goalId: string;
  title: string;
  status: MilestoneStatus;
  /** Sequence position along the Milestone Road (0-indexed). Required
   * because the UI renders milestones in a fixed, meaningful order that
   * isn't guaranteed by createdAt (a milestone can be inserted later). */
  order: number;
  createdAt: string;
  updatedAt: string;
}

// ---------------------------------------------------------------------------
// Commitment
// ---------------------------------------------------------------------------

export type CommitmentStatus = "done" | "in_progress" | "blocked";

/** A specific, tagged promise tied to a Goal — shown on the Goal Milestone
 * Path screen's "Tagged Commitments" section. Distinct from Milestone:
 * milestones are the fixed structural steps of a goal; commitments are
 * ad-hoc items the mentor/user tag along the way (can be many per goal). */
export interface Commitment {
  id: string;
  goalId: string;
  userId: string;
  title: string;
  status: CommitmentStatus;
  /** Set when status is "blocked" and Chioma has an actionable suggestion
   * (e.g. "I can search local vet-approved suppliers for you."). */
  mentorHelpNote?: string;
  createdAt: string;
  updatedAt: string;
}

// ---------------------------------------------------------------------------
// ChatMessage
// ---------------------------------------------------------------------------

export type ChatSender = "user" | "mentor";

export interface ChatMessage {
  id: string;
  userId: string;
  /** Which persona generated this message, if sender is "mentor". Absent
   * for user-authored messages. */
  personaId?: string;
  sender: ChatSender;
  text: string;
  /** RAG source citation (Epic A) shown under mentor messages, e.g.
   * "Based on TEF curriculum". Absent when the response wasn't grounded
   * in a retrievable source. */
  sourceCitation?: string;
  createdAt: string;
}

// ---------------------------------------------------------------------------
// Persona
// ---------------------------------------------------------------------------

/** The stored persona entity. Deliberately has NO "isRecommended" field —
 * recommendation is a function of (persona, user's sector), not an
 * intrinsic property of the persona itself. See PersonaWithRecommendation
 * in "View compositions" for the shape the Persona Selection screen
 * actually consumes. */
export interface Persona {
  id: string;
  name: string;
  tagline: string;
  /** FK into the Epic H trait schema (US-H3's AchieverPersonalityProfile),
   * once that ships. Optional for now since Epic H may not have delivered
   * real archetype data yet — see that ticket's README for status. */
  archetypeId?: string;
}

// ---------------------------------------------------------------------------
// InsightItem
// ---------------------------------------------------------------------------

export interface InsightItem {
  id: string;
  title: string;
  summary: string;
  category: string;
  durationMinutes: number;
  isAudio: boolean;
  mediaUrl?: string;
  /** e.g. "TEF curriculum" — shown as a badge on Curated Insight cards. */
  sourceCurriculum?: string;
  createdAt: string;
}

/** Per-user favorite join — NOT a field on InsightItem itself, since
 * favorite status is user-specific, not intrinsic to the insight. */
export interface InsightFavorite {
  userId: string;
  insightId: string;
  createdAt: string;
}

// ---------------------------------------------------------------------------
// FeedbackSurvey
// ---------------------------------------------------------------------------

/** NPS-style survey submitted from the Feedback Survey modal. Not present
 * in the frontend's pre-G1.3 mock types at all — this is new. */
export interface FeedbackSurvey {
  id: string;
  userId: string;
  /** 1-10, matches the modal's Likert scale. */
  npsScore: number;
  comment?: string;
  /** Freeform context on what triggered the survey, e.g. a goalId or
   * "weekly_checkin" — TBD exact enum with backend, see README. */
  context?: string;
  submittedAt: string;
}

// ---------------------------------------------------------------------------
// DailyAction
// ---------------------------------------------------------------------------

export type DailyActionStatus = "pending" | "in_progress" | "done" | "needs_help";

export interface DailyAction {
  id: string;
  userId: string;
  goalId: string;
  title: string;
  description: string;
  estimatedMinutes: number;
  /** Semantic category chip shown on the Daily Action card, e.g. "Savings". */
  category: string;
  status: DailyActionStatus;
  /** ISO date (not datetime) this action is scheduled for — one per user
   * per day is the current product assumption; flag with backend if that
   * ever needs to change. */
  date: string;
  createdAt: string;
  updatedAt: string;
}

// ---------------------------------------------------------------------------
// StreakStat
// ---------------------------------------------------------------------------

/** A computed aggregate, not a row with its own id — this is a response
 * DTO from a read endpoint (e.g. GET /users/{userId}/streak), not a
 * persisted entity with CRUD operations. */
export interface StreakStat {
  userId: string;
  currentStreakDays: number;
  longestStreakDays: number;
  actionsCompletedTotal: number;
  /** 7 values, Monday through Sunday, for the Progress Board bar chart.
   * Units TBD with backend (likely "actions completed that day" or a 0-100
   * intensity score) — currently treated as a relative magnitude only. */
  weeklyActivity: number[];
  asOf: string;
}

// ---------------------------------------------------------------------------
// Badge
// ---------------------------------------------------------------------------

/** The badge catalog entry — static-ish, defines what badges exist. */
export interface Badge {
  id: string;
  /** Stable machine-readable identifier, e.g. "consistency_queen". Use this,
   * not the display label, for any client-side logic (icon lookup, etc.) —
   * labels can change without breaking anything referencing `code`. */
  code: string;
  label: string;
  description?: string;
  /** Material Symbols Outlined icon name, matching components/Icon.tsx. */
  iconName?: string;
}

/** Per-user earned/unearned state — separate from the Badge catalog. */
export interface UserBadge {
  userId: string;
  badgeId: string;
  /** Null if not yet earned. Presence of a non-null value IS the "earned"
   * signal — no separate boolean field to keep in sync. */
  earnedAt: string | null;
}

// ---------------------------------------------------------------------------
// View compositions (frontend-side convenience types)
// ---------------------------------------------------------------------------
// These are NOT raw API entities — they're shapes the frontend mock layer
// (and, later, real API response DTOs) compose from the base entities above
// for screens that need joined/nested data. Kept separate so it's always
// clear which fields are "real" persisted entity fields vs. assembled for
// a specific screen's convenience. Backend does not need to match these
// exactly — it needs to expose enough via the base entities (or dedicated
// list endpoints) for the frontend to assemble them.

export interface GoalWithMilestones extends Goal {
  milestones: Milestone[];
}

export interface PersonaWithRecommendation extends Persona {
  isRecommended: boolean;
}

export interface InsightWithFavorite extends InsightItem {
  isFavorite: boolean;
}

export interface BadgeWithEarnedStatus extends Badge {
  earned: boolean;
  earnedAt: string | null;
}
