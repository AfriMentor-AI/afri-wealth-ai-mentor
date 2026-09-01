// Re-export all mock implementations, then override the ones that have
// real backend implementations. This allows us to gradually migrate
// from mock to real APIs without breaking the app.
export * from "./mockApi";

import { apiFetch, getCurrentUserId } from "./session";
import type {
  BadgeWithStatus,
  ChatMessage,
  Commitment,
  Goal,
  HeatmapDay,
  InsightItem,
  Milestone,
  StreakStat,
  WeeklySummaryShare,
} from "./types";

interface BackendMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  is_commitment_candidate: boolean;
  citations: Array<{ label: string }>;
  created_at: string;
}

function toChatMessage(m: BackendMessage, userId: string): ChatMessage {
  return {
    id: m.id,
    userId,
    sender: m.role === "user" ? "user" : "mentor",
    content: m.content,
    citations: m.citations,
    is_commitment_candidate: m.is_commitment_candidate,
    created_at: m.created_at,
  };
}

/** GET /api/v1/chat/sessions/{id}/messages */
export async function fetchChatMessages(chatSessionId?: string): Promise<ChatMessage[]> {
  if (!chatSessionId) return [];
  const res = await apiFetch(`/api/v1/chat/sessions/${chatSessionId}/messages`);
  if (!res.ok) throw new Error(`fetchChatMessages failed: ${res.status}`);
  const body: BackendMessage[] = await res.json();
  const userId = await getCurrentUserId();
  return body.filter((m) => m.role !== "system").map((m) => toChatMessage(m, userId));
}

/** POST /api/v1/chat/sessions/{id}/messages — persists the user turn server-side
 * and returns the mentor's reply. */
export async function sendMessage(chatSessionId: string, text: string): Promise<ChatMessage> {
  const res = await apiFetch(`/api/v1/chat/sessions/${chatSessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content: text }),
  });
  if (!res.ok) throw new Error(`sendMessage failed: ${res.status}`);
  const body: BackendMessage = await res.json();
  return toChatMessage(body, await getCurrentUserId());
}

/** POST /api/v1/chat/sessions/{sessionId}/messages/{messageId}/tag */
export async function tagCommitment(chatSessionId: string, chatMessageId: string, goalId?: string): Promise<Commitment> {
  const res = await apiFetch(`/api/v1/chat/sessions/${chatSessionId}/messages/${chatMessageId}/tag`, {
    method: "POST",
    body: JSON.stringify({ goal_id: goalId }),
  });
  if (!res.ok) throw new Error(`tagCommitment failed: ${res.status}`);
  return (await res.json()) as Commitment;
}

/** POST /api/v1/chat/sessions — creates a new conversation and returns its id. */
export async function startChatSession(personaId?: string): Promise<string> {
  const res = await apiFetch("/api/v1/chat/sessions", {
    method: "POST",
    body: JSON.stringify({ persona_id: personaId ?? null }),
  });
  if (!res.ok) throw new Error(`startChatSession failed: ${res.status}`);
  const body: { id: string } = await res.json();
  return body.id;
}

export interface ChatSessionSummary {
  id: string;
  personaId: string | null;
  lastMessagePreview: string | null;
  lastMessageAt: string | null;
  updatedAt: string;
}

interface BackendConversationSummary {
  id: string;
  persona_id: string | null;
  last_message_preview: string | null;
  last_message_at: string | null;
  updated_at: string;
}

/** GET /api/v1/chat/sessions — every conversation this user has started,
 * across mentors, newest activity first. Powers the multi-mentor
 * conversation list. */
export async function fetchChatSessions(): Promise<ChatSessionSummary[]> {
  const res = await apiFetch("/api/v1/chat/sessions");
  if (!res.ok) throw new Error(`fetchChatSessions failed: ${res.status}`);
  const body: BackendConversationSummary[] = await res.json();
  return body.map((s) => ({
    id: s.id,
    personaId: s.persona_id,
    lastMessagePreview: s.last_message_preview,
    lastMessageAt: s.last_message_at,
    updatedAt: s.updated_at,
  }));
}

// ── Goals & Milestones (goals-milestones-service, card O5.1 / BUG-06) ──────
//
// createGoal/fetchGoals/fetchMilestonesByGoal/fetchGoalById/completeMilestone/
// fetchCommitmentsByGoal were still re-exported from mockApi.ts wholesale —
// never overridden despite goals-milestones-service being live since O2.3/O2.4
// — so goals appeared to save in the UI but were never persisted server-side.

interface BackendGoal {
  id: string;
  user_id: string;
  title: string;
  description: string | null;
  status: string;
  deadline: string | null;
  progress_pct: number;
  created_at: string;
  updated_at: string;
}

function toGoal(g: BackendGoal): Goal {
  return {
    id: g.id,
    userId: g.user_id,
    title: g.title,
    progressPct: g.progress_pct,
    deadline: g.deadline ?? undefined,
    createdAt: g.created_at,
    updatedAt: g.updated_at,
  };
}

interface BackendMilestone {
  id: string;
  goal_id: string;
  title: string;
  status: Milestone["status"];
  order: number;
  created_at: string;
  updated_at: string;
}

function toMilestone(m: BackendMilestone): Milestone {
  return {
    id: m.id,
    goalId: m.goal_id,
    title: m.title,
    status: m.status,
    order: m.order,
    createdAt: m.created_at,
    updatedAt: m.updated_at,
  };
}

interface BackendCommitment {
  id: string;
  goal_id: string;
  user_id: string;
  conversation_id: string;
  message_id: string;
  content: string;
  created_at: string;
}

/** goals-milestones-service's Commitment has no `status` field at all (it's
 * just a tagged note, not a tracked done/in_progress/blocked item the way
 * G1.3's contract models it) — mapped to "in_progress" here rather than
 * inventing a status the backend doesn't actually track. Flagged as a real
 * contract gap in docs/qa/sprint5-regression-report.md, not silently papered
 * over; closing it properly means extending the backend schema, out of scope
 * for this bug fix. */
function toCommitment(c: BackendCommitment): Commitment {
  return {
    id: c.id,
    goalId: c.goal_id,
    title: c.content,
    status: "in_progress",
    sourceChatMessageId: c.message_id,
    createdAt: c.created_at,
    // No updated_at on the backend model either — commitments are write-once
    // once tagged, so created_at is accurate, not a placeholder.
    updatedAt: c.created_at,
  };
}

/** GET /api/v1/goals */
export async function fetchGoals(): Promise<Goal[]> {
  const res = await apiFetch("/api/v1/goals");
  if (!res.ok) throw new Error(`fetchGoals failed: ${res.status}`);
  const body: BackendGoal[] = await res.json();
  return body.map(toGoal);
}

/** GET /api/v1/goals/{goalId} */
export async function fetchGoalById(goalId: string): Promise<Goal | undefined> {
  const res = await apiFetch(`/api/v1/goals/${goalId}`);
  if (res.status === 404) return undefined;
  if (!res.ok) throw new Error(`fetchGoalById failed: ${res.status}`);
  return toGoal(await res.json());
}

/** POST /api/v1/goals */
export async function createGoal(input: { title: string; deadline?: string }): Promise<Goal> {
  const res = await apiFetch("/api/v1/goals", {
    method: "POST",
    body: JSON.stringify({ title: input.title, deadline: input.deadline ?? null }),
  });
  if (!res.ok) throw new Error(`createGoal failed: ${res.status}`);
  return toGoal(await res.json());
}

/** GET /api/v1/goals/{goalId}/milestones */
export async function fetchMilestonesByGoal(goalId: string): Promise<Milestone[]> {
  const res = await apiFetch(`/api/v1/goals/${goalId}/milestones`);
  if (!res.ok) throw new Error(`fetchMilestonesByGoal failed: ${res.status}`);
  const body: BackendMilestone[] = await res.json();
  return body.map(toMilestone);
}

/** POST /api/v1/milestones/{milestoneId}/complete */
export async function completeMilestone(milestoneId: string): Promise<Milestone | undefined> {
  const res = await apiFetch(`/api/v1/milestones/${milestoneId}/complete`, { method: "POST" });
  if (res.status === 404) return undefined;
  if (!res.ok) throw new Error(`completeMilestone failed: ${res.status}`);
  return toMilestone(await res.json());
}

/** GET /api/v1/goals/{goalId}/commitments */
export async function fetchCommitmentsByGoal(goalId: string): Promise<Commitment[]> {
  const res = await apiFetch(`/api/v1/goals/${goalId}/commitments`);
  if (!res.ok) throw new Error(`fetchCommitmentsByGoal failed: ${res.status}`);
  const body: BackendCommitment[] = await res.json();
  return body.map(toCommitment);
}

// ── Insight Library (insight-library-service, O3.2) ────────────────────────
//
// fetchInsights was still re-exported from mockApi.ts wholesale, and
// favoriting only ever dispatched local store state — never persisted
// server-side despite insight-library-service's bookmark endpoints being
// live since O3.2.

interface BackendInsight {
  id: string;
  title: string;
  summary: string;
  category: string;
  duration_minutes: number;
  is_audio: boolean;
  media_url: string | null;
  created_at: string;
  is_favorited: boolean;
}

function toInsight(i: BackendInsight): InsightItem {
  return {
    id: i.id,
    title: i.title,
    summary: i.summary,
    category: i.category,
    durationMinutes: i.duration_minutes,
    isAudio: i.is_audio,
    mediaUrl: i.media_url ?? undefined,
    createdAt: i.created_at,
    isFavorited: i.is_favorited,
  };
}

/** GET /api/v1/insights — the full catalog, each item flagged with whether
 * this user has favorited it. Search/category/audio filtering happens
 * client-side over this list (small, catalog-sized dataset) rather than
 * round-tripping per keystroke. */
export async function fetchInsights(): Promise<InsightItem[]> {
  const res = await apiFetch("/api/v1/insights");
  if (!res.ok) throw new Error(`fetchInsights failed: ${res.status}`);
  const body: BackendInsight[] = await res.json();
  return body.map(toInsight);
}

/** POST/DELETE /api/v1/insights/{id}/bookmark */
export async function setInsightFavorited(insightId: string, favorited: boolean): Promise<void> {
  const res = await apiFetch(`/api/v1/insights/${insightId}/bookmark`, {
    method: favorited ? "POST" : "DELETE",
  });
  if (!res.ok) throw new Error(`setInsightFavorited failed: ${res.status}`);
}

// ── Progress & Gamification (progress-gamification-service, O3.1) ──────────
//
// fetchStreak/fetchBadges were still re-exported from mockApi.ts wholesale,
// the Progress board's heatmap was generated with Math.random() despite the
// service's real /api/v1/progress endpoint returning genuine per-day
// activity, and "Share weekly summary" opened the NPS feedback modal
// instead of calling the real share endpoint.

interface BackendStreak {
  user_id: string;
  current_streak_days: number;
  longest_streak_days: number;
  actions_completed_total: number;
  updated_at: string;
}

function toStreak(s: BackendStreak): StreakStat {
  return {
    userId: s.user_id,
    currentStreakDays: s.current_streak_days,
    longestStreakDays: s.longest_streak_days,
    actionsCompletedTotal: s.actions_completed_total,
    updatedAt: s.updated_at,
  };
}

interface BackendBadge {
  id: string;
  label: string;
  description: string;
  icon_name: string;
  earned_at: string | null;
}

function toBadge(b: BackendBadge): BadgeWithStatus {
  return { id: b.id, label: b.label, description: b.description, iconName: b.icon_name, earnedAt: b.earned_at };
}

interface BackendHeatmapDay {
  date: string;
  count: number;
}

interface BackendProgressSummary {
  streak: BackendStreak;
  heatmap: BackendHeatmapDay[];
  badges: BackendBadge[];
}

export interface ProgressSummary {
  streak: StreakStat;
  heatmap: HeatmapDay[];
  badges: BadgeWithStatus[];
}

/** GET /api/v1/progress/streak */
export async function fetchStreak(): Promise<StreakStat> {
  const res = await apiFetch("/api/v1/progress/streak");
  if (!res.ok) throw new Error(`fetchStreak failed: ${res.status}`);
  return toStreak(await res.json());
}

/** GET /api/v1/progress/badges */
export async function fetchBadges(): Promise<BadgeWithStatus[]> {
  const res = await apiFetch("/api/v1/progress/badges");
  if (!res.ok) throw new Error(`fetchBadges failed: ${res.status}`);
  const body: BackendBadge[] = await res.json();
  return body.map(toBadge);
}

/** GET /api/v1/progress — streak + heatmap + badges in one call. Used by the
 * Progress board so it doesn't issue three separate requests for data the
 * backend already returns together. */
export async function fetchProgressSummary(): Promise<ProgressSummary> {
  const res = await apiFetch("/api/v1/progress");
  if (!res.ok) throw new Error(`fetchProgressSummary failed: ${res.status}`);
  const body: BackendProgressSummary = await res.json();
  return {
    streak: toStreak(body.streak),
    heatmap: body.heatmap.map((h) => ({ date: h.date, count: h.count })),
    badges: body.badges.map(toBadge),
  };
}

export type ProgressActionKind = "daily_action" | "insight_completed" | "savings_goal_met";

/** POST /api/v1/progress/actions — recording the same (day, kind) twice is a
 * server-side no-op, not an error, so callers don't need to guard against
 * double-firing. */
export async function recordProgressAction(kind: ProgressActionKind): Promise<void> {
  const res = await apiFetch("/api/v1/progress/actions", {
    method: "POST",
    body: JSON.stringify({ kind }),
  });
  if (!res.ok) throw new Error(`recordProgressAction failed: ${res.status}`);
}

interface BackendWeeklySummaryShare {
  user_id: string;
  week_start: string;
  week_end: string;
  actions_this_week: number;
  current_streak_days: number;
  badges_earned_this_week: string[];
  share_text: string;
}

/** POST /api/v1/progress/summary/share */
export async function shareWeeklySummary(): Promise<WeeklySummaryShare> {
  const res = await apiFetch("/api/v1/progress/summary/share", { method: "POST" });
  if (!res.ok) throw new Error(`shareWeeklySummary failed: ${res.status}`);
  const body: BackendWeeklySummaryShare = await res.json();
  return {
    userId: body.user_id,
    weekStart: body.week_start,
    weekEnd: body.week_end,
    actionsThisWeek: body.actions_this_week,
    currentStreakDays: body.current_streak_days,
    badgesEarnedThisWeek: body.badges_earned_this_week,
    shareText: body.share_text,
  };
}
