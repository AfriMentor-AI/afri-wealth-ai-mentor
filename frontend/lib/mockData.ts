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

// Seed data reproduces the exact sample content from the Stitch export's
// screen.png / code.html references (Kofi Mensah, poultry business in
// Kumasi, the named goals, chat lines, insights, badges, etc.) so the app
// is visually/textually verifiable against the real design screens.

export const mockProfile: Profile = {
  name: "Kofi Mensah",
  businessName: "Poultry Business - Kumasi",
  location: "Kumasi, Ghana",
  sector: "Agriculture",
  educationLevel: "Secondary school",
  timeAvailablePerWeek: "6-10 hours",
  constraints: ["Limited startup capital"],
  personaId: "rural-hustler",
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
    title: "Business Launch",
    progressPct: 45,
    milestones: [
      { id: "m1", title: "Vision Foundation", status: "done" },
      { id: "m2", title: "Legal Readiness", status: "in_progress" },
      { id: "m3", title: "Operations", status: "upcoming" },
      { id: "m4", title: "Launch", status: "upcoming" },
    ],
  },
  {
    id: "goal-debt-reduction",
    title: "Debt Reduction",
    progressPct: 80,
    milestones: [
      { id: "m5", title: "Consolidate outstanding balances", status: "done" },
      { id: "m6", title: "Final Payment Plan", status: "in_progress" },
    ],
  },
  {
    id: "goal-skill-acquisition",
    title: "Skill Acquisition",
    progressPct: 10,
    milestones: [{ id: "m7", title: "Finish Python Basics", status: "in_progress" }],
  },
];

export const mockDailyAction: DailyAction = {
  id: "action-today",
  title: "Save 10% of today's profit",
  description: "Building a reserve fund helps you survive market price fluctuations.",
  estimatedMinutes: 10,
  linkedGoalId: "goal-business-launch",
  done: false,
};

export const mockChatMessages: ChatMessage[] = [
  {
    id: "c1",
    sender: "mentor",
    text: "To grow your plantain business, consistency in your savings is just as important as your daily turnover. Have you thought about setting aside 10% of every sale before restocking?",
    timestamp: "09:15 AM",
    sourceCitation: "Based on TEF curriculum",
  },
  {
    id: "c2",
    sender: "user",
    text: "That makes sense, Chioma. I've been reinvesting everything, but I see now how a reserve fund could help when prices fluctuate in the market.",
    timestamp: "09:18 AM",
  },
  {
    id: "c3",
    sender: "mentor",
    text: 'Exactly! It is the "Sankofa" principle — reaching back to secure what we have built so we can move forward. Shall we tag this as a commitment for your monthly goal?',
    timestamp: "09:19 AM",
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
    isFavorite: false,
  },
  {
    id: "i2",
    title: "Saving during lean seasons",
    summary: "Based on TEF curriculum",
    category: "Sector",
    durationMinutes: 3,
    isAudio: false,
    isFavorite: false,
  },
  {
    id: "i3",
    title: "Bookkeeping with Mobile Money",
    summary: "New — Finance 101",
    category: "Finance 101",
    durationMinutes: 4,
    isAudio: false,
    isFavorite: false,
  },
  {
    id: "i4",
    title: "Supply Chain Mastery",
    summary: "Popular — Agri-Business",
    category: "Agri-Business",
    durationMinutes: 6,
    isAudio: true,
    isFavorite: false,
  },
];

export const mockStreak: StreakStat = {
  currentStreakDays: 14,
  longestStreakDays: 22,
  actionsCompletedTotal: 58,
};

export const mockCommitments: Commitment[] = [
  { id: "cm1", title: "Register business", status: "done", goalId: "goal-business-launch" },
  { id: "cm2", title: "Open savings account", status: "in_progress", goalId: "goal-business-launch" },
  {
    id: "cm3",
    title: "Find supplier",
    status: "blocked",
    goalId: "goal-business-launch",
    mentorHelpNote: "I can search local vet-approved suppliers for you.",
  },
];

export const mockBadges: Badge[] = [
  { id: "b1", label: "Consistency Queen", earned: true },
  { id: "b2", label: "Smart Saver", earned: true },
  { id: "b3", label: "Scholar Spirit", earned: false },
];
