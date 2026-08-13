import type {
  Badge,
  ChatMessage,
  Commitment,
  DailyAction,
  Goal,
  InsightItem,
  Milestone,
  Persona,
  Profile,
  StreakStat,
  User,
  UserBadge,
} from "./types";

// Seed data reproduces the exact sample content from the Stitch export's
// screen.png / code.html references (Kofi Mensah, poultry business in
// Kumasi, the named goals, chat lines, insights, badges, etc.) so the app
// is visually/textually verifiable against the real design screens.
//
// G1.3: shapes here now follow contract/types.ts exactly (ids, FKs,
// timestamps included, entities normalized — e.g. Milestone is its own
// collection keyed by goalId, not nested inside Goal) since this is the
// module that has to prove the shared contract is actually consumable,
// not just declared.

const DEMO_USER_ID = "usr_kofi_mensah";

export const mockUser: User = {
  id: DEMO_USER_ID,
  phoneNumber: "+233241234567",
  locale: "en-GH",
  createdAt: "2026-07-01T08:00:00Z",
};

export const mockProfile: Profile = {
  userId: DEMO_USER_ID,
  name: "Kofi Mensah",
  businessName: "Poultry Business - Kumasi",
  location: "Kumasi, Ghana",
  sector: "Agriculture",
  educationLevel: "Secondary school",
  timeAvailablePerWeek: "6-10 hours",
  constraints: ["Limited startup capital"],
  personaId: "rural-hustler",
  createdAt: "2026-07-01T08:05:00Z",
  updatedAt: "2026-07-01T08:05:00Z",
};

export const mockPersonas: Persona[] = [
  {
    id: "market-queen",
    name: "The Market Queen",
    tagline: "Master of commerce, community scaling, and traditional resilience.",
    isRecommended: true,
  },
  {
    id: "tech-founder",
    name: "The Tech Founder",
    tagline: "Strategist for digital disruption, VC fundraising, and agile growth.",
    isRecommended: false,
  },
  {
    id: "trader",
    name: "The Trader",
    tagline: "Expert in logistics, supply chains, and cross-border arbitrage.",
    isRecommended: false,
  },
  {
    id: "rural-hustler",
    name: "The Rural Hustler",
    tagline: "Specialist in agri-business, micro-credits, and local sustainability.",
    isRecommended: false,
  },
  {
    id: "creative",
    name: "The Creative",
    tagline: "Guide for personal branding, digital arts, and the orange economy.",
    isRecommended: false,
  },
];

export const mockGoals: Goal[] = [
  {
    id: "goal-business-launch",
    userId: DEMO_USER_ID,
    title: "Business Launch",
    progressPct: 45,
    deadline: "2026-10-24",
    createdAt: "2026-07-02T09:00:00Z",
    updatedAt: "2026-07-20T09:00:00Z",
  },
  {
    id: "goal-debt-reduction",
    userId: DEMO_USER_ID,
    title: "Debt Reduction",
    progressPct: 80,
    deadline: "2026-12-12",
    createdAt: "2026-07-02T09:00:00Z",
    updatedAt: "2026-07-20T09:00:00Z",
  },
  {
    id: "goal-skill-acquisition",
    userId: DEMO_USER_ID,
    title: "Skill Acquisition",
    progressPct: 10,
    deadline: "2027-01-31",
    createdAt: "2026-07-02T09:00:00Z",
    updatedAt: "2026-07-20T09:00:00Z",
  },
];

// Normalized: keyed by goalId, matching GET /goals/{goalId}/milestones
// rather than nested inside Goal itself.
export const mockMilestones: Milestone[] = [
  { id: "m1", goalId: "goal-business-launch", title: "Vision Foundation", status: "done", order: 0, createdAt: "2026-07-02T09:00:00Z", updatedAt: "2026-07-10T09:00:00Z" },
  { id: "m2", goalId: "goal-business-launch", title: "Legal Readiness", status: "in_progress", order: 1, createdAt: "2026-07-02T09:00:00Z", updatedAt: "2026-07-20T09:00:00Z" },
  { id: "m3", goalId: "goal-business-launch", title: "Operations", status: "upcoming", order: 2, createdAt: "2026-07-02T09:00:00Z", updatedAt: "2026-07-02T09:00:00Z" },
  { id: "m4", goalId: "goal-business-launch", title: "Launch", status: "upcoming", order: 3, createdAt: "2026-07-02T09:00:00Z", updatedAt: "2026-07-02T09:00:00Z" },

  { id: "m5", goalId: "goal-debt-reduction", title: "Consolidate outstanding balances", status: "done", order: 0, createdAt: "2026-07-02T09:00:00Z", updatedAt: "2026-07-15T09:00:00Z" },
  { id: "m6", goalId: "goal-debt-reduction", title: "Final Payment Plan", status: "in_progress", order: 1, createdAt: "2026-07-02T09:00:00Z", updatedAt: "2026-07-20T09:00:00Z" },

  { id: "m7", goalId: "goal-skill-acquisition", title: "Finish Python Basics", status: "in_progress", order: 0, createdAt: "2026-07-02T09:00:00Z", updatedAt: "2026-07-20T09:00:00Z" },
];

export const mockCommitments: Commitment[] = [
  {
    id: "cm1",
    goalId: "goal-business-launch",
    title: "Register business",
    status: "done",
    createdAt: "2026-07-05T09:00:00Z",
    updatedAt: "2026-07-10T09:00:00Z",
  },
  {
    id: "cm2",
    goalId: "goal-business-launch",
    title: "Open savings account",
    status: "in_progress",
    createdAt: "2026-07-12T09:00:00Z",
    updatedAt: "2026-07-20T09:00:00Z",
  },
  {
    id: "cm3",
    goalId: "goal-business-launch",
    title: "Find supplier",
    status: "blocked",
    mentorHelpNote: "I can search local vet-approved suppliers for you.",
    createdAt: "2026-07-18T09:00:00Z",
    updatedAt: "2026-07-22T09:00:00Z",
  },
];

export const mockDailyAction: DailyAction = {
  id: "action-2026-07-28",
  userId: DEMO_USER_ID,
  date: "2026-07-28",
  title: "Save 10% of today's profit",
  description: "Building a reserve fund helps you survive market price fluctuations.",
  estimatedMinutes: 10,
  linkedGoalId: "goal-business-launch",
  done: false,
  createdAt: "2026-07-28T06:00:00Z",
  updatedAt: "2026-07-28T06:00:00Z",
};

export const mockChatMessages: ChatMessage[] = [
  {
    id: "c1",
    userId: DEMO_USER_ID,
    personaId: "rural-hustler",
    sender: "mentor",
    text: "To grow your plantain business, consistency in your savings is just as important as your daily turnover. Have you thought about setting aside 10% of every sale before restocking?",
    createdAt: "2026-07-28T09:15:00Z",
  },
  {
    id: "c2",
    userId: DEMO_USER_ID,
    sender: "user",
    text: "That makes sense, Chioma. I've been reinvesting everything, but I see now how a reserve fund could help when prices fluctuate in the market.",
    createdAt: "2026-07-28T09:18:00Z",
  },
  {
    id: "c3",
    userId: DEMO_USER_ID,
    personaId: "rural-hustler",
    sender: "mentor",
    text: 'Exactly! It is the "Sankofa" principle — reaching back to secure what we have built so we can move forward. Shall we tag this as a commitment for your monthly goal?',
    createdAt: "2026-07-28T09:19:00Z",
  },
];

export const mockInsights: InsightItem[] = [
  {
    id: "i1",
    title: "How to price your trade",
    summary: "Based on TEF curriculum",
    category: "Sector",
    durationMinutes: 5,
    isAudio: true,
    createdAt: "2026-06-01T00:00:00Z",
  },
  {
    id: "i2",
    title: "Saving during lean seasons",
    summary: "Based on TEF curriculum",
    category: "Sector",
    durationMinutes: 3,
    isAudio: false,
    createdAt: "2026-06-01T00:00:00Z",
  },
  {
    id: "i3",
    title: "Bookkeeping with Mobile Money",
    summary: "New — Finance 101",
    category: "Finance 101",
    durationMinutes: 4,
    isAudio: false,
    createdAt: "2026-07-15T00:00:00Z",
  },
  {
    id: "i4",
    title: "Supply Chain Mastery",
    summary: "Popular — Agri-Business",
    category: "Agri-Business",
    durationMinutes: 6,
    isAudio: true,
    createdAt: "2026-05-01T00:00:00Z",
  },
];

export const mockStreak: StreakStat = {
  userId: DEMO_USER_ID,
  currentStreakDays: 14,
  longestStreakDays: 22,
  actionsCompletedTotal: 58,
  updatedAt: "2026-07-28T06:00:00Z",
};

// Catalog (shared/global — not user-specific) ...
export const mockBadges: Badge[] = [
  { id: "b1", label: "Consistency Queen", description: "7 days streak", iconName: "workspace_premium" },
  { id: "b2", label: "Smart Saver", description: "Saved ₵500 this week", iconName: "savings" },
  { id: "b3", label: "Scholar Spirit", description: "Finished 5 lessons in Library", iconName: "menu_book" },
];

// ...joined against this user-specific earned/locked state, mirroring how
// GET /progress/badges actually returns BadgeWithStatus (see lib/api.ts).
export const mockUserBadges: UserBadge[] = [
  { userId: DEMO_USER_ID, badgeId: "b1", earnedAt: "2026-07-08T00:00:00Z" },
  { userId: DEMO_USER_ID, badgeId: "b2", earnedAt: "2026-07-21T00:00:00Z" },
  { userId: DEMO_USER_ID, badgeId: "b3", earnedAt: null },
];
