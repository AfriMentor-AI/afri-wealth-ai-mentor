# Frontend Handoff — AfriMentor AI PWA

**For:** Daniel, Chukwuebuka, Olusegun
**From:** Grace
**Purpose:** everything you need to build against this frontend in Sprints 2-5 without me in the room.

This is the written version of the handoff. Acceptance criteria for G1.5 accepts "recorded/written" — this doc is the written half. If a live walkthrough would still help (screen-sharing, answering questions in real time), a suggested outline for that recording is at the bottom of this doc — reuse these section headers as your talking points if you record it.

---

## 1. The big picture

This is a Next.js 14 (App Router) + TypeScript + Tailwind PWA. Everything currently runs against **mock data** — there is no real backend yet. The entire point of how this is structured is that Sprint 2's backend work should be able to plug in underneath this frontend **without touching any UI component**. That's not aspirational — it's enforced by one specific architectural choice, explained in Section 3.

Two documents you should read alongside this one:
- `README.md` (repo root) — build/run instructions, and a log of real design-fidelity decisions made against the Stitch export.
- `contract/README.md` — the API contract (types + OpenAPI). **This is the most important thing for Daniel and Chukwuebuka specifically** — it's what your backend work builds against.

## 2. Folder structure, and what actually matters in each

```
app/                    Routes (Next.js App Router — folder = URL path)
components/             Shared UI: nav, modals, icon wrapper, theme toggle
components/ui/          Reusable primitives: Button, Chip, ProgressRing, MilestoneRoad, Skeleton
lib/                     The important stuff — see Section 3
contract/                Shared frontend/backend API contract (types.ts + openapi.yaml)
```

Inside `app/`, folders in `(parentheses)` are Next.js **route groups** — `(app)` doesn't appear in the URL, it just groups the four tab-shell screens (Chat/Goals/Library/Progress) under one shared layout (nav, feedback modal, data hydration).

## 3. The mock data layer — read this before you touch anything

**`lib/api.ts` is the only file any screen imports data from.** Not `lib/mockData.ts` directly — always `lib/api.ts`. Every function in `api.ts` currently does this:

```ts
export async function fetchGoals(): Promise<Goal[]> {
  return resolveAfterLatency(mockGoals);
}
```

When your backend endpoint exists, you change **only the body of that function** — swap it for a real `fetch()` call. Nothing in `app/(app)/goals/page.tsx` or anywhere else needs to change, because it only ever imported `fetchGoals` from `api.ts`, never `mockGoals` from `mockData.ts` directly.

**Practical implication for you:** when you build a real endpoint, look up its corresponding function in `lib/api.ts` (each one has a comment pointing at the intended real route, e.g. `/** GET /goals/{goalId}/milestones */`), and that's your integration point. You shouldn't need to read the component code at all to wire up a given screen's data.

## 4. Where things are, entity by entity

Every type is defined once in `contract/types.ts` — this is the same file the OpenAPI spec is mirrored from, so if you're implementing an endpoint, read the interface there first, then check `openapi.yaml` for the intended request/response shape.

| Entity | Where it's fetched | Where it's rendered |
|---|---|---|
| Profile | `fetchProfile()` | Chat header, Daily Action greeting |
| Persona | `fetchPersonas()` | `/persona` |
| Goal | `fetchGoals()`, `fetchGoalById()` | `/goals`, `/goals/milestones/[goalId]` |
| Milestone | `fetchMilestonesByGoal()` | Goal Milestone Path — **normalized, not nested in Goal** |
| Commitment | `fetchCommitmentsByGoal()` | Goal Milestone Path, "Tagged Commitments" |
| ChatMessage | `fetchChatMessages()` | `/chat` |
| InsightItem | `fetchInsights()` | `/library` |
| FeedbackSurvey | `submitFeedback()` | Feedback modal (global, opened from Progress) |
| DailyAction | `fetchDailyAction()` | `/goals/action` |
| StreakStat | `fetchStreak()` | `/progress` |
| Badge | `fetchBadges()` | `/progress` — **catalog + per-user earned state joined client-side today**, should be server-side once real |

The "normalized, not nested" and "joined client-side" notes above matter — see `contract/README.md`'s "Real modeling decisions" section for why Milestone/Commitment aren't embedded in Goal, and why Badge is split into catalog + earned-state.

## 5. State that isn't just fetched data

`lib/store.tsx` is a React Context + `useReducer` holding cross-screen state that isn't server data: which persona is selected, the in-progress chat draft, favorited insights, theme, feedback modal open/closed. This lives **above** the tab routes in the component tree specifically so that switching Chat → Goals → Chat doesn't lose your half-typed message or scroll position. If you add a new screen that needs to remember something across tab switches, this is where it goes — not local `useState` in the page component.

## 6. Design system

`tailwind.config.ts` and `app/globals.css` implement the "Heritage-Forward Financial Mentor" design system from the Stitch export's `DESIGN.md`, generated directly from those tokens (not hand-guessed — see the README's G1.2 section for a real discrepancy I found and fixed between `DESIGN.md`'s tokens and what the export's rendered screens actually used). Component primitives (`components/ui/`) are built to the DESIGN.md Components spec. If you're building new UI, use these primitives and the CSS variables (`var(--primary)`, etc.) rather than hardcoding colors — dark mode ("Nocturnal Heritage") depends on those variables actually being used consistently.

## 7. Known gaps / things to watch for

- **Dark mode has no real design source.** The Stitch export never actually defined dark-mode colors. What's there is a reasonable derivation, not a verified match to anything. Don't treat it as more final than it is.
- **Two Stitch export screens were deliberately not built**: `rag_corpus_admin` and `research_console_dashboard`. Those belong to your tickets (Epic A backend admin, Epic F/G research tooling), not the frontend PWA scope.
- **`contract/types.ts` is a stub**, explicitly not final — expect it to change once real backend constraints (DB choice, auth model, pagination) are known. Don't build deeply against exact field names as if they're frozen.
- **Auth doesn't exist.** Every mock function assumes a single hardcoded demo user (`usr_kofi_mensah` in `mockData.ts`). There's no login flow, no session handling — that's new ground for Sprint 2, not something to reverse-engineer from the frontend.

## 8. Running it

```bash
npm install
npm run dev      # http://localhost:3000
npm run build    # production build — verify this stays clean as you change things
```

---

## If you record a walkthrough video instead of/in addition to reading this

Suggested order, roughly 15-20 minutes:
1. Run `npm run dev`, click through the full flow once (Splash → Welcome → Intake → Persona → the four tabs) so it's clear what's actually built.
2. Open `lib/api.ts` and `lib/mockData.ts` side by side — explain the swap-point pattern from Section 3 live, since seeing it in the editor lands better than reading about it.
3. Open `lib/store.tsx` — show the Context/reducer and explain why it sits where it does in the component tree.
4. Open `contract/types.ts` and `contract/openapi.yaml` side by side, and point at one example (e.g. Milestone) showing how they mirror each other.
5. End on Section 7 (gaps) — say out loud what's genuinely unfinished so nobody discovers it the hard way mid-sprint.
