// Re-export all mock implementations, then override the ones that have
// real backend implementations. This allows us to gradually migrate
// from mock to real APIs without breaking the app.
export * from "./mockApi";
export * from "./voice";

import { apiFetch, getCurrentUserId } from "./session";
import type {
  ChatMessage,
  Commitment,
  Goal,
  Milestone,
  Profile,
  StreakStat,
  BadgeWithStatus,
  InsightItem,
  RagQueryResponse,
  RagCorpusStats,
  Persona,
  DailyAction,
  FeedbackSurvey,
} from "./types";
import { mockProfile, mockInsights, mockPersonas, mockDailyAction } from "./mockData";

interface BackendMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  is_commitment_candidate: boolean;
  citations: Array<{ label: string }>;
  created_at: string;
}

export function stripThinkTags(text: string): string {
  if (!text) return "";
  return text
    .replace(/<think>(?:[\s\S]*?<\/think>|[\s\S]*$)/gi, "")
    .replace(/<\/think>/gi, "")
    .replace(/<br\s*\/?>/gi, "\n")
    .trimStart();
}

function toChatMessage(m: BackendMessage, userId: string): ChatMessage {
  return {
    id: m.id,
    userId,
    sender: m.role === "user" ? "user" : "mentor",
    content: stripThinkTags(m.content),
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

/** POST /api/v1/chat/sessions/{id}/messages/stream — streams assistant tokens
 * via SSE.
 *
 * - `onToken(chunk)` is called for each incremental text chunk.
 * - `onComplete(message)` is called once with the fully-persisted ChatMessage.
 * - Returns a cleanup function that aborts the stream if called early.
 */
export function sendMessageStream(
  chatSessionId: string,
  text: string,
  onToken: (chunk: string) => void,
  onComplete: (message: ChatMessage) => void,
  onError?: (err: Error) => void,
): () => void {
  const controller = new AbortController();

  (async () => {
    const userId = await getCurrentUserId();
    const res = await apiFetch(`/api/v1/chat/sessions/${chatSessionId}/messages/stream`, {
      method: "POST",
      body: JSON.stringify({ content: text }),
      signal: controller.signal,
    } as RequestInit & { signal: AbortSignal });

    if (!res.ok) {
      onError?.(new Error(`sendMessageStream failed: ${res.status}`));
      return;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      onError?.(new Error("No response body"));
      return;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last (potentially incomplete) line in the buffer
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("event: token")) continue; // event type line
          if (line.startsWith("event: complete")) continue;
          if (!line.startsWith("data: ")) continue;

          const jsonStr = line.slice("data: ".length).trim();
          if (!jsonStr) continue;

          try {
            const parsed = JSON.parse(jsonStr) as Record<string, unknown>;
            if ("text" in parsed && typeof parsed.text === "string") {
              onToken(parsed.text);
            } else if ("id" in parsed) {
              // This is the complete event payload — build the final ChatMessage
              const msg: BackendMessage = {
                id: parsed.id as string,
                role: "assistant",
                content: parsed.content as string,
                is_commitment_candidate: (parsed.is_commitment_candidate as boolean) ?? false,
                citations: (parsed.citations as Array<{ label: string }>) ?? [],
                created_at: new Date().toISOString(),
              };
              onComplete(toChatMessage(msg, userId));
            }
          } catch {
            // Malformed SSE data line — ignore
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        onError?.(err as Error);
      }
    } finally {
      reader.releaseLock();
    }
  })();

  return () => controller.abort();
}

/** POST /api/v1/chat/sessions/{sessionId}/messages/{messageId}/tag */
export async function tagCommitment(chatSessionId: string, chatMessageId: string, goalId?: string): Promise<Commitment> {
  const res = await apiFetch(`/api/v1/chat/sessions/${chatSessionId}/messages/${chatMessageId}/tag`, {
    method: "POST",
    body: JSON.stringify({ goal_id: goalId }),
  });
  // 409 means this message was already tagged — treat as success (idempotent)
  if (res.status === 409) return { id: "", status: "in_progress" } as unknown as Commitment;
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
    description: g.description ?? undefined,
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
export async function createGoal(input: {
  title: string;
  description?: string;
  deadline?: string;
}): Promise<Goal> {
  const res = await apiFetch("/api/v1/goals", {
    method: "POST",
    body: JSON.stringify({
      title: input.title,
      description: input.description ?? null,
      deadline: input.deadline ?? null,
    }),
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

// ---------------------------------------------------------------------------
// Intake & Profiling (intake-profiling-service)
// ---------------------------------------------------------------------------

interface BackendDiagnosticProfile {
  user_id: string;
  name: string;
  business_name: string;
  location: string;
  sector: string;
  education_level: string;
  time_available_per_week: string;
  constraints: string[];
  updated_at: string;
}

function toProfile(d: BackendDiagnosticProfile, personaId: string | null = null): Profile {
  return {
    userId: d.user_id,
    name: d.name,
    businessName: d.business_name,
    location: d.location || "",
    sector: d.sector,
    educationLevel: d.education_level,
    timeAvailablePerWeek: d.time_available_per_week,
    constraints: d.constraints || [],
    personaId,
    createdAt: d.updated_at,
    updatedAt: d.updated_at,
  };
}

/**
 * POST /api/v1/intake/sessions
 * Submits the 4-step answers and completes the intake session in intake-profiling-service.
 */
export async function submitIntake(
  intake: Partial<Profile> | Record<string, unknown>
): Promise<Profile> {
  const i = intake as Record<string, unknown>;
  const sector = (i.sector as string) || "Trader";
  const educationLevel = (i.educationLevel || i.education_level || "Secondary school") as string;
  const timeAvailablePerWeek = (i.timeAvailablePerWeek || i.time_available_per_week || "6-10 hours") as string;
  const constraints = (i.constraints as string[]) || [];
  const name = (i.name as string) || "User";
  const businessName = (i.businessName || i.business_name || "My Business") as string;
  const location = (i.location as string) || "";

  // 1. Start or resume intake session
  const sessionRes = await apiFetch("/api/v1/intake/sessions", {
    method: "POST",
  });
  if (!sessionRes.ok) {
    throw new Error(`Failed to start intake session: ${sessionRes.status}`);
  }
  const sessionData = await sessionRes.json();
  const sessionId = sessionData.id;

  // 2. Submit answers for each step
  await apiFetch(`/api/v1/intake/sessions/${sessionId}/answers`, {
    method: "POST",
    body: JSON.stringify({
      step: "sector",
      payload: { sector },
    }),
  });

  await apiFetch(`/api/v1/intake/sessions/${sessionId}/answers`, {
    method: "POST",
    body: JSON.stringify({
      step: "education_time",
      payload: {
        education_level: educationLevel,
        time_available_per_week: timeAvailablePerWeek,
      },
    }),
  });

  await apiFetch(`/api/v1/intake/sessions/${sessionId}/answers`, {
    method: "POST",
    body: JSON.stringify({
      step: "constraints",
      payload: { constraints },
    }),
  });

  await apiFetch(`/api/v1/intake/sessions/${sessionId}/answers`, {
    method: "POST",
    body: JSON.stringify({
      step: "confirm",
      payload: {
        name,
        business_name: businessName,
        location,
      },
    }),
  });

  // 3. Complete session
  const completeRes = await apiFetch(`/api/v1/intake/sessions/${sessionId}/complete`, {
    method: "POST",
  });
  if (!completeRes.ok && completeRes.status !== 409) {
    throw new Error(`Failed to complete intake session: ${completeRes.status}`);
  }

  // 4. Retrieve diagnostic profile or fallback to local representation
  const userId = await getCurrentUserId();
  try {
    const profileRes = await apiFetch(`/api/v1/profiles/${userId}/diagnostic`);
    if (profileRes.ok) {
      const profileData: BackendDiagnosticProfile = await profileRes.json();
      return toProfile(profileData);
    }
  } catch {
    // Non-fatal, construct Profile below
  }

  const now = new Date().toISOString();
  return {
    userId,
    name,
    businessName,
    location,
    sector,
    educationLevel,
    timeAvailablePerWeek,
    constraints,
    personaId: null,
    createdAt: sessionData.started_at || now,
    updatedAt: now,
  };
}

/** GET /api/v1/profiles/{userId}/diagnostic */
export async function fetchProfile(): Promise<Profile> {
  const userId = await getCurrentUserId();
  try {
    const res = await apiFetch(`/api/v1/profiles/${userId}/diagnostic`);
    if (res.ok) {
      const data: BackendDiagnosticProfile = await res.json();
      return toProfile(data);
    }
  } catch {
    // Fall back to mock profile if backend profile is not yet initialized
  }
  return mockProfile;
}

// ---------------------------------------------------------------------------
// Progress & Gamification (progress-gamification-service)
// ---------------------------------------------------------------------------

interface BackendStreak {
  user_id: string;
  current_streak_days: number;
  longest_streak_days: number;
  actions_completed_total: number;
  updated_at: string;
}

function toStreakStat(b: BackendStreak): StreakStat {
  return {
    userId: b.user_id,
    currentStreakDays: b.current_streak_days,
    longestStreakDays: b.longest_streak_days,
    actionsCompletedTotal: b.actions_completed_total,
    updatedAt: b.updated_at,
  };
}

interface BackendBadge {
  id: string;
  label: string;
  description: string;
  icon_name: string;
  earned_at: string | null;
}

function toBadgeWithStatus(b: BackendBadge): BadgeWithStatus {
  return {
    id: b.id,
    label: b.label,
    description: b.description,
    iconName: b.icon_name,
    earnedAt: b.earned_at,
  };
}

export interface BackendHeatmapDay {
  date: string;
  count: number;
}

interface BackendProgressSummary {
  streak: BackendStreak;
  heatmap: BackendHeatmapDay[];
  badges: BackendBadge[];
}

/** GET /api/v1/progress - fetches summary in 1 call */
export async function fetchProgressSummary(): Promise<{
  streak: StreakStat;
  badges: BadgeWithStatus[];
  heatmap: BackendHeatmapDay[];
}> {
  try {
    const res = await apiFetch("/api/v1/progress");
    if (res.ok) {
      const data: BackendProgressSummary = await res.json();
      return {
        streak: toStreakStat(data.streak),
        badges: (data.badges || []).map(toBadgeWithStatus),
        heatmap: data.heatmap || [],
      };
    }
  } catch (err) {
    console.warn("fetchProgressSummary error:", err);
  }
  const userId = await getCurrentUserId();
  return {
    streak: {
      userId,
      currentStreakDays: 0,
      longestStreakDays: 0,
      actionsCompletedTotal: 0,
      updatedAt: new Date().toISOString(),
    },
    badges: [],
    heatmap: [],
  };
}

/** GET /api/v1/progress/streak */
export async function fetchStreak(): Promise<StreakStat> {
  try {
    const res = await apiFetch("/api/v1/progress/streak");
    if (res.ok) {
      const data: BackendStreak = await res.json();
      return toStreakStat(data);
    }
  } catch (err) {
    console.warn("fetchStreak error, fallback to default:", err);
  }
  const userId = await getCurrentUserId();
  return {
    userId,
    currentStreakDays: 0,
    longestStreakDays: 0,
    actionsCompletedTotal: 0,
    updatedAt: new Date().toISOString(),
  };
}

/** GET /api/v1/progress/badges */
export async function fetchBadges(): Promise<BadgeWithStatus[]> {
  try {
    const res = await apiFetch("/api/v1/progress/badges");
    if (res.ok) {
      const data: BackendBadge[] = await res.json();
      return data.map(toBadgeWithStatus);
    }
  } catch (err) {
    console.warn("fetchBadges error:", err);
  }
  return [];
}

/** GET /api/v1/progress/heatmap */
export async function fetchHeatmap(): Promise<BackendHeatmapDay[]> {
  try {
    const res = await apiFetch("/api/v1/progress/heatmap");
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("fetchHeatmap error:", err);
  }
  return [];
}

/** POST /api/v1/progress/actions */
export async function recordAction(
  kind: "daily_action" | "insight_completed" | "savings_goal_met" = "daily_action"
): Promise<{
  streak: StreakStat;
  newlyEarnedBadges: Array<{ badgeId: string; label: string }>;
}> {
  const res = await apiFetch("/api/v1/progress/actions", {
    method: "POST",
    body: JSON.stringify({ kind }),
  });
  if (!res.ok) {
    throw new Error(`recordAction failed: ${res.status}`);
  }
  const data = await res.json();
  return {
    streak: toStreakStat(data.streak),
    newlyEarnedBadges: (data.newly_earned_badges || []).map(
      (b: { badge_id: string; label: string }) => ({
        badgeId: b.badge_id,
        label: b.label,
      })
    ),
  };
}

// ---------------------------------------------------------------------------
// Insight Library (insight-library-service)
// ---------------------------------------------------------------------------

export interface BackendInsightItem {
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

function toInsightItem(b: BackendInsightItem): InsightItem {
  return {
    id: b.id,
    title: b.title,
    summary: b.summary,
    category: b.category,
    durationMinutes: b.duration_minutes,
    isAudio: b.is_audio,
    mediaUrl: b.media_url ?? undefined,
    createdAt: b.created_at,
  };
}

/** GET /api/v1/insights */
export async function fetchInsights(options?: {
  search?: string;
  category?: string;
  isAudio?: boolean;
}): Promise<InsightItem[]> {
  try {
    const params = new URLSearchParams();
    if (options?.search) params.set("search", options.search);
    if (options?.category) params.set("category", options.category);
    if (options?.isAudio !== undefined) params.set("is_audio", String(options.isAudio));

    const query = params.toString() ? `?${params.toString()}` : "";
    const res = await apiFetch(`/api/v1/insights${query}`);
    if (res.ok) {
      const data: BackendInsightItem[] = await res.json();
      return data.map(toInsightItem);
    }
  } catch (err) {
    console.warn("fetchInsights error, fallback to mock:", err);
  }
  return mockInsights;
}

/** POST or DELETE /api/v1/insights/{insightId}/favorite */
export async function toggleInsightFavorite(insightId: string, shouldFavorite: boolean): Promise<boolean> {
  const method = shouldFavorite ? "POST" : "DELETE";
  let res = await apiFetch(`/api/v1/insights/${insightId}/favorite`, { method });
  if (!res.ok && res.status === 404) {
    res = await apiFetch(`/api/v1/insights/${insightId}/bookmark`, { method });
  }
  return res.ok;
}

// ---------------------------------------------------------------------------
// RAG Corpus Service (rag-corpus-service, port 8005)
// ---------------------------------------------------------------------------

/** POST /api/v1/rag/query - retrieve relevant knowledge chunks for a query */
export async function queryRag(
  queryText: string,
  options?: { topK?: number; filters?: Record<string, unknown> }
): Promise<RagQueryResponse> {
  try {
    const res = await apiFetch("/api/v1/rag/query", {
      method: "POST",
      body: JSON.stringify({
        query: queryText,
        top_k: options?.topK ?? 4,
        filters: options?.filters,
      }),
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("queryRag error, returning empty results:", err);
  }
  return { query: queryText, results: [], total: 0 };
}

/** GET /api/v1/rag/stats - fetch corpus and index telemetry */
export async function fetchRagStats(): Promise<RagCorpusStats | null> {
  try {
    const res = await apiFetch("/api/v1/rag/stats");
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("fetchRagStats error:", err);
  }
  return null;
}

// ---------------------------------------------------------------------------
// Persona Prompt Service (persona-prompt-service, port 8004)
// ---------------------------------------------------------------------------

export interface BackendPersonaMeta {
  id: string;
  slug: string;
  display_name: string;
  tagline: string;
  sector_tags: string[];
  template_file: string;
  is_base: boolean;
  status: "stable" | "beta";
}

function toPersona(b: BackendPersonaMeta): Persona {
  return {
    id: b.slug || b.id,
    name: b.display_name,
    tagline: b.tagline,
    isRecommended: b.is_base || false,
  };
}

/** GET /api/v1/personas - catalogue of mentor personas */
export async function fetchPersonas(): Promise<Persona[]> {
  try {
    const res = await apiFetch("/api/v1/personas");
    if (res.ok) {
      const data: BackendPersonaMeta[] = await res.json();
      if (data && data.length > 0) {
        return data.map(toPersona);
      }
    }
  } catch (err) {
    console.warn("fetchPersonas error, fallback to mock:", err);
  }
  return mockPersonas;
}

/** POST /api/v1/personas/{personaId}/select - binds a persona to a chat session */
export async function selectPersona(personaId: string, sessionId: string): Promise<boolean> {
  try {
    const res = await apiFetch(`/api/v1/personas/${personaId}/select`, {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId }),
    });
    return res.ok;
  } catch (err) {
    console.warn("selectPersona error:", err);
    return false;
  }
}

// ---------------------------------------------------------------------------
// Feedback Service (feedback-service, port 8009)
// ---------------------------------------------------------------------------

interface BackendFeedbackResponse {
  id: string;
  user_id: string;
  nps_score: number;
  comment: string | null;
  voice_note_url: string | null;
  trigger: string;
  context_ref: string | null;
  submitted_at: string;
}

/** POST /api/v1/feedback - submit user rating & comments */
export async function submitFeedback(input: {
  npsScore: number;
  comment?: string;
  voiceNoteUrl?: string;
  trigger?: string;
  contextRef?: string;
}): Promise<FeedbackSurvey> {
  const userId = await getCurrentUserId();
  try {
    const res = await apiFetch("/api/v1/feedback", {
      method: "POST",
      body: JSON.stringify({
        nps_score: input.npsScore,
        comment: input.comment ?? null,
        voice_note_url: input.voiceNoteUrl ?? null,
        trigger: input.trigger ?? "manual",
        context_ref: input.contextRef ?? null,
      }),
    });
    if (res.ok) {
      const data: BackendFeedbackResponse = await res.json();
      return {
        id: data.id,
        userId: data.user_id,
        npsScore: data.nps_score,
        comment: data.comment ?? undefined,
        submittedAt: data.submitted_at,
      };
    }
  } catch (err) {
    console.warn("submitFeedback error, fallback to client survey:", err);
  }
  return {
    id: `fb-${Date.now()}`,
    userId,
    npsScore: input.npsScore,
    comment: input.comment,
    submittedAt: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Daily Action (chat-orchestration-service)
// ---------------------------------------------------------------------------

interface BackendDailyAction {
  id: string;
  user_id: string;
  action_text: string;
  is_completed: boolean;
  created_at: string;
}

/** GET /api/v1/chat/daily-action - fetch user's personalized daily action */
export async function fetchDailyAction(): Promise<DailyAction> {
  try {
    const res = await apiFetch("/api/v1/chat/daily-action");
    if (res.ok) {
      const data: BackendDailyAction = await res.json();
      const dateStr = data.created_at ? data.created_at.split("T")[0] : new Date().toISOString().split("T")[0];
      return {
        id: data.id,
        userId: data.user_id,
        date: dateStr,
        title: data.action_text,
        description: data.action_text,
        estimatedMinutes: 10,
        linkedGoalId: "goal-daily",
        done: data.is_completed,
        createdAt: data.created_at,
        updatedAt: data.created_at,
      };
    }
  } catch (err) {
    console.warn("fetchDailyAction error, fallback to mock:", err);
  }
  return mockDailyAction;
}

// ---------------------------------------------------------------------------
// Notification Service (notification-service, port 8012)
// ---------------------------------------------------------------------------

export interface AppNotification {
  id: string;
  userId: string;
  kind: string;
  title: string;
  body: string;
  createdAt: string;
  readAt: string | null;
  deliveredAt: string;
}

interface BackendNotification {
  id: string;
  user_id: string;
  kind: string;
  title: string;
  body: string;
  created_at: string;
  read_at: string | null;
  delivered_at: string;
}

function toAppNotification(b: BackendNotification): AppNotification {
  return {
    id: b.id,
    userId: b.user_id,
    kind: b.kind,
    title: b.title,
    body: b.body,
    createdAt: b.created_at,
    readAt: b.read_at,
    deliveredAt: b.delivered_at,
  };
}

/** GET /api/v1/notifications - list notifications for current user */
export async function fetchNotifications(): Promise<AppNotification[]> {
  try {
    const res = await apiFetch("/api/v1/notifications");
    if (res.ok) {
      const data: BackendNotification[] = await res.json();
      return data.map(toAppNotification);
    }
  } catch (err) {
    console.warn("fetchNotifications error:", err);
  }
  return [];
}

/** POST /api/v1/notifications/{id}/read - mark a notification as read */
export async function markNotificationRead(notificationId: string): Promise<boolean> {
  try {
    const res = await apiFetch(`/api/v1/notifications/${notificationId}/read`, { method: "POST" });
    return res.ok;
  } catch (err) {
    console.warn("markNotificationRead error:", err);
    return false;
  }
}

/** POST /api/v1/notifications/read-all - mark all unread notifications as read */
export async function markAllNotificationsRead(): Promise<boolean> {
  try {
    const res = await apiFetch("/api/v1/notifications/read-all", { method: "POST" });
    return res.ok;
  } catch (err) {
    console.warn("markAllNotificationsRead error:", err);
    return false;
  }
}