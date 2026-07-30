// Lightweight domain types for the mock layer. G1.3 formalizes these into
// the full shared TypeScript + OpenAPI contract with the backend — these
// are scoped to exactly what the UI needs to render for G1.1.

export type ThemeName = "heritage" | "nocturnal";

export interface Profile {
  name: string;
  businessName: string;
  location: string;
  sector: string;
  educationLevel: string;
  timeAvailablePerWeek: string;
  constraints: string[];
  personaId: string;
}

export interface Persona {
  id: string;
  name: string;
  tagline: string;
  /** Whether to show the "Recommended for you" badge — computed server-side
   * from the user's profile/sector in production; hardcoded here to match
   * the reference design's sample state. */
  isRecommended: boolean;
}

export type MilestoneStatus = "done" | "in_progress" | "blocked" | "upcoming";

export interface Milestone {
  id: string;
  title: string;
  status: MilestoneStatus;
}

export interface Goal {
  id: string;
  title: string;
  progressPct: number;
  milestones: Milestone[];
}

export type CommitmentStatus = "done" | "in_progress" | "blocked";

export interface Commitment {
  id: string;
  title: string;
  status: CommitmentStatus;
  goalId: string;
  mentorHelpNote?: string;
}

export interface DailyAction {
  id: string;
  title: string;
  description: string;
  estimatedMinutes: number;
  linkedGoalId: string;
  done: boolean;
}

export type ChatSender = "user" | "mentor";

export interface ChatMessage {
  id: string;
  sender: ChatSender;
  text: string;
  timestamp: string;
  sourceCitation?: string;
}

export interface InsightItem {
  id: string;
  title: string;
  summary: string;
  category: string;
  durationMinutes: number;
  isAudio: boolean;
  isFavorite: boolean;
}

export interface StreakStat {
  currentStreakDays: number;
  longestStreakDays: number;
  actionsCompletedTotal: number;
}

export interface Badge {
  id: string;
  label: string;
  earned: boolean;
}
