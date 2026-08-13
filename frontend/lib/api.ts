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
  console.info("[mock] fetchChatMessages opts:", _opts);
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
