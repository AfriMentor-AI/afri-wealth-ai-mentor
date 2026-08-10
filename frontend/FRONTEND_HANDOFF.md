# Frontend Handoff — AfriMentor AI PWA

**For:** Daniel, Chukwuebuka, Olusegun
**From:** Grace (transitioning to PM / Research Writer for Sprints 2–5)
**Covers:** component structure, the mock data layer, and how to swap it for the real backend

---

## 1. Start here: run it yourself before reading further

```bash
cd afrimentor-pwa
npm install
npm run dev
```

Open `http://localhost:3000`. Click through Splash → Welcome → Intake → Persona Selection → the four main tabs. Toggle dark mode. That's the whole app — five minutes of clicking will make the rest of this doc click faster than reading it cold.

## 2. The one thing to understand before anything else: the mock layer

**Every screen's data currently comes from `lib/mockData.ts`, compiled straight into the JS bundle — there is no real network call anywhere in this app yet.** That's deliberate, not a shortcut: it let frontend development run fully in parallel with backend work, per the original sprint plan.

The isolation point is `lib/api.ts`. **No component ever imports `mockData.ts` directly** — every screen calls a function like `fetchGoals()` or `fetchChatMessages()` from `lib/api.ts`, which today just resolves the mock data (with a simulated 250ms latency, so loading states are real and testable, not skipped). When the real backend is up:

```ts
// lib/api.ts today:
export async function fetchGoals(): Promise<Goal[]> {
  return resolveAfterLatency(mockGoals);
}

// becomes, later, with zero component changes required:
export async function fetchGoals(): Promise<Goal[]> {
  const res = await fetch("/api/goals");
  return res.json();
}
```

That's the whole migration for most endpoints — swap the function body, not the UI. `contract/openapi.yaml` documents which real endpoint each function is meant to become (each has a `/** GET /goals */`-style comment pointing at it).

## 3. The type contract (Olusegun, this is the one to read closely)

`contract/types.ts` is the actual source of truth for every entity shape — `lib/types.ts` just re-exports it so `@/lib/types` imports across the app don't need to change. `contract/openapi.yaml` mirrors it 1:1 and is a **validated, loadable OpenAPI 3.0 document** (checked with `openapi-spec-validator`, not just eyeballed).

Four modeling decisions in there are worth a conversation before they're load-bearing in the real backend — full reasoning in `contract/README.md`:

1. **User is split from Profile.** Auth identity vs. Intake business data — lets auth evolve independently.
2. **Milestone and Commitment are normalized out of Goal**, not nested — `GET /goals/{id}` doesn't return milestones inline; they're their own `GET /goals/{id}/milestones` collection, because they get updated independently of their parent goal.
3. **Badge is a shared catalog; earning it is a per-user join** (`UserBadge`), same pattern as `InsightItem` + `InsightFavorite`.
4. **`Persona.isRecommended` is request-scoped**, computed against whoever's asking — not a stored fact about the Persona.

None of these are final — they're a strong starting point specifically so Sprint 2 backend work has something concrete to push back on instead of starting from nothing.

## 4. Component structure, top to bottom

```
app/                    → routes (Next.js App Router — folder = URL path)
  page.tsx              → Splash (the actual entry point, "/")
  welcome/, intake/, persona/  → onboarding, in that order
  (app)/                 → route group: everything behind the bottom tab nav
    layout.tsx            → mounts nav + feedback modal ONCE, hydrates shared
                             data — this is what makes switching Chat→Goals→Chat
                             preserve a half-typed message instead of losing it
    chat/, goals/, library/, progress/  → the four main tabs

components/
  ui/                    → Button, Chip, ProgressRing, MilestoneRoad, Skeleton —
                            reusable primitives, built to DESIGN.md's spec, not
                            ad hoc per-screen styling
  Icon.tsx               → Material Symbols wrapper (matches the Stitch export's
                            actual icon font — not lucide or another icon set)
  BottomTabNav, ThemeToggle, FeedbackSurveyModal, OfflineBanner, SankofaMotif

lib/
  types.ts               → re-exports contract/types.ts (see §3)
  mockData.ts             → ALL seed data, nowhere else
  api.ts                  → THE swap point (see §2) — this is the only file
                            that changes when the real backend lands
  store.tsx                → shared app state (React Context + useReducer):
                             persona, profile, chat draft/history, theme,
                             favorites. Lives above the tab routes specifically
                             so it survives navigation between them.

contract/
  types.ts, openapi.yaml, README.md  → the actual API contract (§3)

public/
  sw.js, manifest.json, offline.html  → PWA shell (see §5)
```

**If you're adding a new screen:** look at `app/(app)/library/page.tsx` as the simplest complete example — fetch via `lib/api.ts`, render a `<Skeleton />` while loading, use the `ui/` primitives, done.

**If you're adding a new data type:** add it to `contract/types.ts` first, mirror it into `openapi.yaml`, then add mock data + an `api.ts` function. In that order — the contract is supposed to be the thing you write against, not an afterthought you reverse-engineer from mock data later.

## 5. PWA / offline behavior, briefly

Real service worker (`public/sw.js`, hand-written, no next-pwa dependency) does app-shell caching. **Important nuance:** because data is currently in-bundle mock data (§2), the app shell being cached means Chat/Goals/Library currently work *fully* offline, not just show a fallback — that stops being automatically true the moment real API calls exist, at which point the service worker will also need response caching to keep the same guarantee. `<OfflineBanner />` is already in place so cached content is never silently indistinguishable from live content once that transition happens.

## 6. Known gaps / things I didn't get to

Being direct about this rather than letting it surface as a surprise later:

- **Two citations in the research paper repo are unverified** (see `afrimentor-paper/README.md`) — need input from whoever compiled the original reading list.
- **Dark mode has no real design source** — the export never shipped dark screens or dark tokens, so `Nocturnal Heritage` is a from-scratch derivation, not a verified match.
- **Lighthouse PWA score and real-device install testing were never run** — no headless Chrome available in the environment this was built in. Someone needs to run `npx lighthouse` for real before checking that off.
- **`goal_milestone_path`'s zig-zag layout was simplified to a straight vertical list** — the original only works for exactly 3 fixed milestones.

## 7. Questions?

Grace is transitioning to PM/Research Writer, not off the project — tag her on anything that needs frontend-history context she'd actually know and this doc doesn't cover.
