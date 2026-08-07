// Single point of contact between UI components and data.
// Auth, Intake and Goals & Milestones are live (card O2.4) — everything else here
// still resolves from mockData until its backend ships. No component should ever
// import mockData directly.

import {
  mockBadges,
  mockChatMessages,
  mockDailyAction,
  mockInsights,
  mockPersonas,
  mockStreak,
  mockUser,
  mockUserBadges,
} from "./mockData";
import { apiFetch, getCurrentUserId } from "./session";
import type {
  BadgeWithStatus,
  ChatMessage,
  Commitment,
  CommitmentStatus,
  DailyAction,
  FeedbackSurvey,
  Goal,
  InsightItem,
  Milestone,
  MilestoneStatus,
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

async function parseOrThrow(res: Response, action: string): Promise<unknown> {
  if (!res.ok) throw new Error(`${action} failed: ${res.status}`);
  return res.status === 204 ? null : res.json();
}

// ---------------------------------------------------------------------------
// Auth & User (live — auth-user-service via the gateway)
// ---------------------------------------------------------------------------

/** GET /api/v1/auth/me */
export async function fetchCurrentUser(): Promise<User> {
  const res = await apiFetch("/api/v1/auth/me");
  const dto = (await parseOrThrow(res, "fetch current user")) as {
    id: string;
    email: string;
    created_at: string;
  };
  return { id: dto.id, email: dto.email, createdAt: dto.created_at };
}

// ---------------------------------------------------------------------------
// Intake & Profiling (live — intake-profiling-service via the gateway)
// ---------------------------------------------------------------------------

interface DiagnosticProfileDto {
  user_id: string;
  name: string;
  business_name: string;
  location: string;
  sector: string;
  education_level: string;
  time_available_per_week: string;
  constraints: string[];
  persona_id: string | null;
  created_at: string;
  updated_at: string;
}

function toProfile(dto: DiagnosticProfileDto): Profile {
  return {
    userId: dto.user_id,
    name: dto.name,
    businessName: dto.business_name,
    location: dto.location,
    sector: dto.sector,
    educationLevel: dto.education_level,
    timeAvailablePerWeek: dto.time_available_per_week,
    constraints: dto.constraints,
    personaId: dto.persona_id,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}

/** GET /api/v1/profiles/{userId}/diagnostic — null until Intake has been completed. */
export async function fetchProfile(): Promise<Profile | null> {
  const userId = await getCurrentUserId();
  const res = await apiFetch(`/api/v1/profiles/${userId}/diagnostic`);
  if (res.status === 404) return null;
  const dto = (await parseOrThrow(res, "fetch diagnostic profile")) as DiagnosticProfileDto;
  return toProfile(dto);
}

export interface IntakeAnswers {
  sector: string;
  educationLevel: string;
  timeAvailablePerWeek: string;
  constraints: string[];
  name: string;
  businessName: string;
  location: string;
}

/** Drives the full 4-step intake flow — start a session, submit each step's
 * answer, then complete it — and returns the resulting diagnostic profile.
 * POST /api/v1/intake/sessions, .../answers (x4), .../complete */
export async function submitIntake(answers: IntakeAnswers): Promise<Profile> {
  const sessionRes = await apiFetch("/api/v1/intake/sessions", { method: "POST" });
  const session = (await parseOrThrow(sessionRes, "start intake session")) as { id: string };

  const steps: Array<{ step: string; payload: Record<string, unknown> }> = [
    { step: "sector", payload: { sector: answers.sector } },
    {
      step: "education_time",
      payload: {
        education_level: answers.educationLevel,
        time_available_per_week: answers.timeAvailablePerWeek,
      },
    },
    { step: "constraints", payload: { constraints: answers.constraints } },
    {
      step: "confirm",
      payload: { name: answers.name, business_name: answers.businessName, location: answers.location },
    },
  ];
  for (const { step, payload } of steps) {
    const res = await apiFetch(`/api/v1/intake/sessions/${session.id}/answers`, {
      method: "POST",
      body: JSON.stringify({ step, payload }),
    });
    await parseOrThrow(res, `submit intake step "${step}"`);
  }

  const completeRes = await apiFetch(`/api/v1/intake/sessions/${session.id}/complete`, {
    method: "POST",
  });
  await parseOrThrow(completeRes, "complete intake session");

  const userId = await getCurrentUserId();
  const profileRes = await apiFetch(`/api/v1/profiles/${userId}/diagnostic`);
  const dto = (await parseOrThrow(profileRes, "fetch diagnostic profile")) as DiagnosticProfileDto;
  return toProfile(dto);
}

/** GET /api/v1/personas */
export async function fetchPersonas(): Promise<Persona[]> {
  return resolveAfterLatency(mockPersonas);
}

// ---------------------------------------------------------------------------
// Goals, Milestones & Commitments (live — goals-milestones-service via the gateway)
// ---------------------------------------------------------------------------

interface GoalDto {
  id: string;
  user_id: string;
  title: string;
  deadline: string | null;
  progress_pct: number;
  created_at: string;
  updated_at: string;
}

function toGoal(dto: GoalDto): Goal {
  return {
    id: dto.id,
    userId: dto.user_id,
    title: dto.title,
    progressPct: dto.progress_pct,
    deadline: dto.deadline ?? undefined,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}

interface MilestoneDto {
  id: string;
  goal_id: string;
  title: string;
  status: MilestoneStatus;
  order: number;
  created_at: string;
  updated_at: string;
}

function toMilestone(dto: MilestoneDto): Milestone {
  return {
    id: dto.id,
    goalId: dto.goal_id,
    title: dto.title,
    status: dto.status,
    order: dto.order,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}

interface CommitmentDto {
  id: string;
  goal_id: string;
  title: string;
  status: CommitmentStatus;
  mentor_help_note: string | null;
  source_chat_message_id: string | null;
  created_at: string;
  updated_at: string;
}

function toCommitment(dto: CommitmentDto): Commitment {
  return {
    id: dto.id,
    goalId: dto.goal_id,
    title: dto.title,
    status: dto.status,
    mentorHelpNote: dto.mentor_help_note ?? undefined,
    sourceChatMessageId: dto.source_chat_message_id ?? undefined,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  };
}

/** GET /api/v1/goals */
export async function fetchGoals(): Promise<Goal[]> {
  const res = await apiFetch("/api/v1/goals");
  const dtos = (await parseOrThrow(res, "fetch goals")) as GoalDto[];
  return dtos.map(toGoal);
}

/** GET /api/v1/goals/{goalId} */
export async function fetchGoalById(goalId: string): Promise<Goal | undefined> {
  const res = await apiFetch(`/api/v1/goals/${goalId}`);
  if (res.status === 404) return undefined;
  const dto = (await parseOrThrow(res, "fetch goal")) as GoalDto;
  return toGoal(dto);
}

/** POST /api/v1/goals */
export async function createGoal(input: { title: string; deadline?: string }): Promise<Goal> {
  const res = await apiFetch("/api/v1/goals", {
    method: "POST",
    body: JSON.stringify({ title: input.title, deadline: input.deadline ?? null }),
  });
  const dto = (await parseOrThrow(res, "create goal")) as GoalDto;
  return toGoal(dto);
}

/** GET /api/v1/goals/{goalId}/milestones — Milestone is normalized (its own
 * collection keyed by goalId) per the contract, not nested inside Goal. */
export async function fetchMilestonesByGoal(goalId: string): Promise<Milestone[]> {
  const res = await apiFetch(`/api/v1/goals/${goalId}/milestones`);
  if (res.status === 404) return [];
  const dtos = (await parseOrThrow(res, "fetch milestones")) as MilestoneDto[];
  return dtos.map(toMilestone).sort((a, b) => a.order - b.order);
}

/** POST /api/v1/milestones/{milestoneId}/complete */
export async function completeMilestone(milestoneId: string): Promise<Milestone> {
  const res = await apiFetch(`/api/v1/milestones/${milestoneId}/complete`, { method: "POST" });
  const dto = (await parseOrThrow(res, "complete milestone")) as MilestoneDto;
  return toMilestone(dto);
}

/** GET /api/v1/goals/{goalId}/commitments */
export async function fetchCommitmentsByGoal(goalId: string): Promise<Commitment[]> {
  const res = await apiFetch(`/api/v1/goals/${goalId}/commitments`);
  if (res.status === 404) return [];
  const dtos = (await parseOrThrow(res, "fetch commitments")) as CommitmentDto[];
  return dtos.map(toCommitment);
}

/** GET /daily-action/today */
export async function fetchDailyAction(): Promise<DailyAction> {
  return resolveAfterLatency(mockDailyAction);
}

/** GET /chat/messages */
export async function fetchChatMessages(): Promise<ChatMessage[]> {
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
