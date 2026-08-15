// Single point of contact between UI components and data.
// Every function here currently resolves from mockData. When the backend
// (Epic O/D services) is live, only THIS file changes — swap each function's
// body for a fetch() against the real API using the G1.3 contract
// (contract/openapi.yaml documents the intended real endpoint per
// function below). No component should ever import mockData directly.

import {
  mockBadges,
  mockChatMessages,
  mockCommitments,
  mockDailyAction,
  mockGoals,
  mockInsights,
  mockMilestones,
  mockPersonas,
  mockProfile,
  mockStreak,
  mockUser,
  mockUserBadges,
} from "./mockData";
import type {
  BadgeWithStatus,
  ChatMessage,
  Commitment,
  DailyAction,
  FeedbackSurvey,
  Goal,
  InsightItem,
  Milestone,
  Persona,
  Profile,
  StreakStat,
  User,
} from "./types";

// Simulated latency so loading/skeleton states are real and tested,
// not skipped because mock data resolves instantly.
const LATENCY_MS = 250;
function resolveAfterLatency<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), LATENCY_MS));
}

/** GET /users/me */
export async function fetchCurrentUser(): Promise<User> {
  return resolveAfterLatency(mockUser);
}

/** GET /users/me/profile */
export async function fetchProfile(): Promise<Profile> {
  return resolveAfterLatency(mockProfile);
}

/** GET /personas */
export async function fetchPersonas(): Promise<Persona[]> {
  return resolveAfterLatency(mockPersonas);
}

/** GET /goals */
export async function fetchGoals(): Promise<Goal[]> {
  return resolveAfterLatency(mockGoals);
}

/** GET /goals/{goalId} */
export async function fetchGoalById(goalId: string): Promise<Goal | undefined> {
  return resolveAfterLatency(mockGoals.find((g) => g.id === goalId));
}

/** GET /goals/{goalId}/milestones — Milestone is normalized (its own
 * collection keyed by goalId) per the contract, not nested inside Goal. */
export async function fetchMilestonesByGoal(goalId: string): Promise<Milestone[]> {
  return resolveAfterLatency(
    mockMilestones.filter((m) => m.goalId === goalId).sort((a, b) => a.order - b.order)
  );
}

/** GET /goals/{goalId}/commitments */
export async function fetchCommitmentsByGoal(goalId: string): Promise<Commitment[]> {
  return resolveAfterLatency(mockCommitments.filter((c) => c.goalId === goalId));
}

/** GET /daily-action/today */
export async function fetchDailyAction(): Promise<DailyAction> {
  return resolveAfterLatency(mockDailyAction);
}

/** GET /chat/messages */
// Accepts an optional options parameter to support future filtering/pagination
// and to match call sites that may pass an argument. Keeping it optional so
// existing calls with no args continue to work.
export async function fetchChatMessages(_opts?: unknown): Promise<ChatMessage[]> {
  console.info("[mock] fetchChatMessages options:", _opts);
  return resolveAfterLatency(mockChatMessages);
}

/** GET /insights */
export async function fetchInsights(): Promise<InsightItem[]> {
  return resolveAfterLatency(mockInsights);
}

/** GET /progress/streak */
export async function fetchStreak(): Promise<StreakStat> {
  return resolveAfterLatency(mockStreak);
}

/** POST /feedback */
export async function submitFeedback(input: { npsScore: number; comment?: string }): Promise<FeedbackSurvey> {
  const survey: FeedbackSurvey = {
    id: `fb-${Date.now()}`,
    userId: mockUser.id,
    npsScore: input.npsScore,
    comment: input.comment,
    submittedAt: new Date().toISOString(),
  };
  // Real endpoint persists this server-side; mock just logs it so it's
  // visible that a real, contract-shaped object was actually built.
  console.info("[mock] submitted FeedbackSurvey:", survey);
  return resolveAfterLatency(survey);
}

/** GET /progress/badges — joins the Badge catalog against this user's
 * UserBadge earned/locked state, same as the real endpoint will. */
export async function fetchBadges(): Promise<BadgeWithStatus[]> {
  const joined: BadgeWithStatus[] = mockBadges.map((badge) => {
    const userBadge = mockUserBadges.find((ub) => ub.badgeId === badge.id);
    return { ...badge, earnedAt: userBadge?.earnedAt ?? null };
  });
  return resolveAfterLatency(joined);
}


// ---------------------------------------------------------------------------
// Additional mock POST/command operations used by the UI. These are simple
// stubs that return contract-shaped objects so pages/components importing
// them can build. When the real backend exists, replace with fetch() calls.
// ---------------------------------------------------------------------------

export async function sendMessage(chatSessionId: string, text: string): Promise<ChatMessage>;
export async function sendMessage(input: { text: string; personaId?: string }): Promise<ChatMessage>;
export async function sendMessage(a: string | { text: string; personaId?: string }, b?: string): Promise<ChatMessage> {
  let personaId: string | undefined;
  let messageText: string;
  if (typeof a === "string") {
    // Called as sendMessage(chatSessionId, text)
    messageText = b ?? "";
    // chatSessionId is available as `a` if needed for more realistic mocks
    personaId = undefined;
  } else {
    // Called as sendMessage({ text, personaId })
    messageText = a.text;
    personaId = a.personaId;
  }

  const msg: ChatMessage = {
    id: `msg-${Date.now()}`,
    userId: mockUser.id,
    sender: "mentor",
    content: `(mock reply) Received: ${messageText}`,
    personaId: personaId,
    created_at: new Date().toISOString(),
  };
  return resolveAfterLatency(msg);
}

export async function tagCommitment(chatSessionId: string, chatMessageId: string, goalId?: string): Promise<Commitment>;
export async function tagCommitment(chatMessageId: string): Promise<Commitment>;
export async function tagCommitment(a: string, b?: string, c?: string): Promise<Commitment> {
  // Support two call shapes:
  // - tagCommitment(chatMessageId)
  // - tagCommitment(chatSessionId, chatMessageId, goalId?)
  let chatMessageId: string;
  let goalId: string | undefined;
  if (b === undefined) {
    // called as tagCommitment(chatMessageId)
    chatMessageId = a;
  } else {
    // called as tagCommitment(chatSessionId, chatMessageId, goalId?)
    chatMessageId = b;
    goalId = c;
  }

  const commitment: Commitment = {
    id: `commit-${Date.now()}`,
    goalId: goalId ?? mockGoals[0]?.id ?? "",
    title: `Tagged from message ${chatMessageId}`,
    status: "in_progress",
    sourceChatMessageId: chatMessageId,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  return resolveAfterLatency(commitment);
}

export async function completeMilestone(milestoneId: string): Promise<Milestone | undefined> {
  const m = mockMilestones.find((mm) => mm.id === milestoneId);
  if (!m) return resolveAfterLatency(undefined);
  const updated: Milestone = { ...m, status: "done", updatedAt: new Date().toISOString() };
  return resolveAfterLatency(updated);
}

export async function createGoal(input: { title: string; deadline?: string }): Promise<Goal> {
  const goal: Goal = {
    id: `goal-${Date.now()}`,
    userId: mockUser.id,
    title: input.title,
    progressPct: 0,
    deadline: input.deadline,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  return resolveAfterLatency(goal);
}

// Accept a flexible intake shape (often the UI passes a lightweight
// IntakeAnswers object). Use a permissive parameter type so callers that
// omit userId/personaId still type-check during build; the mock will fill
// defaults for missing fields. Use `unknown` instead of `any` to satisfy
// the linter and narrow safely below.
export async function submitIntake(intake: Partial<Profile> | Record<string, unknown>): Promise<Profile> {
  const now = new Date().toISOString();
  const i = intake as Partial<Profile>;

  const profile: Profile = {
    userId: i.userId ?? "local-user",
    name: i.name ?? "",
    businessName: i.businessName ?? "",
    location: i.location ?? "",
    sector: i.sector ?? "",
    educationLevel: i.educationLevel ?? "",
    timeAvailablePerWeek: i.timeAvailablePerWeek ?? "",
    constraints: (i.constraints as string[]) ?? [],
    personaId: i.personaId ?? null,
    createdAt: now,
    updatedAt: now,
  };
  return resolveAfterLatency(profile);
}

// Starts a new chat session and returns its session id. The UI can then
// call fetchChatMessages(sessionId) or fetchChatMessages() to seed the
  // conversation from mock data.
export async function startChatSession(personaId?: string): Promise<string> {
  // In a real backend this would create a session and return its id. Here
  // produce a deterministic-ish mock id that encodes the persona if present.
  const sessionId = personaId ? `session-${personaId}-${Date.now()}` : `session-${Date.now()}`;
  return resolveAfterLatency(sessionId);
}