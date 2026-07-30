// Single point of contact between UI components and data.
// Every function here currently resolves from mockData. When the backend
// (Epic O/D services) is live, only THIS file changes — swap each function's
// body for a fetch() against the real API using the G1.3 contract. No
// component should ever import mockData directly.

import {
  mockBadges,
  mockChatMessages,
  mockCommitments,
  mockDailyAction,
  mockGoals,
  mockInsights,
  mockPersonas,
  mockProfile,
  mockStreak,
} from "./mockData";
import type {
  Badge,
  ChatMessage,
  Commitment,
  DailyAction,
  Goal,
  InsightItem,
  Persona,
  Profile,
  StreakStat,
} from "./types";

// Simulated latency so loading/skeleton states are real and tested,
// not skipped because mock data resolves instantly.
const LATENCY_MS = 250;
function resolveAfterLatency<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), LATENCY_MS));
}

export async function fetchProfile(): Promise<Profile> {
  return resolveAfterLatency(mockProfile);
}

export async function fetchPersonas(): Promise<Persona[]> {
  return resolveAfterLatency(mockPersonas);
}

export async function fetchGoals(): Promise<Goal[]> {
  return resolveAfterLatency(mockGoals);
}

export async function fetchGoalById(goalId: string): Promise<Goal | undefined> {
  return resolveAfterLatency(mockGoals.find((g) => g.id === goalId));
}

export async function fetchCommitmentsByGoal(goalId: string): Promise<Commitment[]> {
  return resolveAfterLatency(mockCommitments.filter((c) => c.goalId === goalId));
}

export async function fetchDailyAction(): Promise<DailyAction> {
  return resolveAfterLatency(mockDailyAction);
}

export async function fetchChatMessages(): Promise<ChatMessage[]> {
  return resolveAfterLatency(mockChatMessages);
}

export async function fetchInsights(): Promise<InsightItem[]> {
  return resolveAfterLatency(mockInsights);
}

export async function fetchStreak(): Promise<StreakStat> {
  return resolveAfterLatency(mockStreak);
}

export async function fetchBadges(): Promise<Badge[]> {
  return resolveAfterLatency(mockBadges);
}
