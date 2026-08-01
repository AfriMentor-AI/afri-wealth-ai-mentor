# AfriMentor AI — Frontend PWA (G1.1)

Built for: **[G1.1] Build full frontend PWA from Stitch design export (all screens)**
Assignee: Grace · 8 pts

## Run it

```bash
npm install
npm run dev
```

Open http://localhost:3000 — flow is Splash → Welcome (2-slide intro) → Intake (4 steps) → Persona Selection → main app (Chat / Goals / Library / Progress via the bottom tab nav).

Production build check: `npm run build` (verified clean — 0 type errors).

## Status: reconciled against the real Stitch export

The first version of this app was built before `stitch_afrimentor_ai_design_system.zip` was available, using a placeholder visual system. **That's since been replaced.** Every token, icon, and screen below has been rebuilt against the actual export (`DESIGN.md` + each screen's `code.html` / `screen.png`), not guessed.

**What's now pixel/token-accurate:**
- `tailwind.config.ts` / `app/globals.css` — real Material3-style tokens from `DESIGN.md` (`primary: #7e5700`, `surface: #fcf9f3`, etc.), not an invented palette.
- Icons — swapped from lucide-react to **Material Symbols Outlined** (`components/Icon.tsx`), matching the export's actual icon font and glyph names (`chat_bubble`, `workspace_premium`, `auto_stories`...).
- `SankofaMotif` — the literal SVG path from the export's splash screen, not a redrawn approximation.
- `Button`, `Chip`, `ProgressRing`, `MilestoneRoad`, `Skeleton` — rebuilt to the exact specs in DESIGN.md's Components section (pill buttons with the pressed-shadow effect, 8px progress rings in Sage Green over Warm Sand, etc.).
- All 10 route screens rebuilt against their real markup/copy: **Splash, Welcome, Intake, Persona Selection, Chat, Goals Overview, Daily Action Card, Goal Milestone Path, Insight Library, Progress Board**, plus the **Feedback Survey** modal.
- Mock data (`lib/mockData.ts`) now uses the export's actual sample content — real goal names, the real Chioma/plantain-business chat lines, real streak numbers (14-day streak, 22-day best), real badge names.

**Known, deliberate departures from the export (documented, not accidental):**
1. **Dark mode has no real source.** The export's `dark:` classes just reuse the light token values — there's no actual "Nocturnal Heritage" palette in `DESIGN.md`. `app/globals.css` has our own derived dark palette clearly marked with a comment; replace it wholesale once design ships real dark tokens.
2. **No hotlinked stock photos.** The export's persona/mentor images point to `googleusercontent.com` URLs tied to the Stitch session — those aren't reliable or ours to depend on long-term. Personas and the Chioma avatar use initials-in-a-circle placeholders on the same token colors instead. Swap in real assets whenever the team has them (S3/CDN, not hotlinked).
3. **Goal Milestone Path is a single vertical list, not the export's left/right zig-zag.** The zig-zag only works cleanly for exactly 3 fixed milestones; a goal with 2 or 6 milestones would break it. Same node/line visual language (solid vs. dashed, filled vs. hollow), just a layout that scales.
4. **Splash vs. Welcome.** The export bundles these into one file (`splash_welcome_screen`) with a 3-dot pagination hint. Split into two screens here — Splash as the brand moment, Welcome as a 2-slide carousel — both to match the ticket's "Splash / Welcome" naming and the "11 unique screens" acceptance criteria.
5. **Two export screens intentionally not built here:** `rag_corpus_admin` and `research_console_dashboard`. Both are real screens in the export, but they belong to other tickets (RAG Corpus Service admin / Research Console — Epic A and Epic F/G work), not G1.1's scope. Flagging so nobody assumes they were missed.

## G1.2 — Design system / theme provider (this pass)

Implemented against the real `DESIGN.md` tokens, with three things worth knowing:

**1. Border-radius scale corrected.** G1.1 sourced radius values from the export's rendered `code.html` (0.25/0.5/0.75rem), since that's what generated the screens being matched visually. `DESIGN.md`'s own frontmatter token block defines a different scale (0.5/0.75/1/1.5rem) — this ticket's AC specifically requires generating from `DESIGN.md`, so that's now the source of truth. Net effect: cards are very slightly less rounded than the G1.1 screen.png references. This is a real inconsistency in the source deliverables (code.html vs. DESIGN.md don't agree with each other), not an error introduced here — see `tailwind.config.ts` comments.

**2. Theme provider is now real, not just a token switch.** Previously the theme only applied after React hydrated, causing a flash of the wrong theme on reload for anyone who'd chosen dark mode. `app/layout.tsx` now has a blocking inline script that reads `localStorage` and sets `data-theme` before first paint. The toggle itself is a proper reusable `<ThemeToggle />` component, now reachable from both the mobile header AND the desktop nav bar (it was mobile-only before — desktop had no way to switch themes at all).

**3. "Matching the `*_dark` screen variants pixel-for-pixel" — cannot be done.** Checked thoroughly: there are no `*_dark` screen folders in the export, and `DESIGN.md` defines zero dark color values anywhere (frontmatter or prose). The dark "Nocturnal Heritage" theme here is a from-scratch derivation using standard Material3 dark-theme conventions (inverted primary/on-primary emphasis, lighter accents on dark surfaces) — a defensible, coherent dark theme, but not a verified match to anything, because nothing to match against was ever delivered. This AC should either get real dark mockups from design, or get reworded to something achievable.

**Components primitives**, reconciled against `DESIGN.md`'s Components section specifically:
- `Button` — pill-shaped, 44px min height; `cta` variant is Confident Gold (primary-container) + on-primary-container text, matching "primary button uses Confident Gold with deep charcoal text."
- `ProgressRing` — 8px stroke, Sage Green (secondary) progress over Warm Sand-toned (outline-variant) track, no gradients.
- `MilestoneRoad` — 2px dashed vertical line; active nodes filled Gold (primary-container, not the darker `primary` token — "Gold" per the Colors section prose is specifically primary-container); upcoming nodes hollow with a 2px stroke.
- `Skeleton` — flat `#e0e0e0` wash, exact hex from spec, radius passed in per-usage to match whatever it's standing in for.
- `Chip` — one open gap, flagged in the component's own comment: DESIGN.md prose says chips use "Learning"/"Community" semantic colors, but those aren't defined as actual hex tokens anywhere. Currently matches the real intake screen reference (primary/primary-container) instead of inventing hex values for the undefined names.

## G1.3 — API contract (TypeScript + OpenAPI)

New `contract/` folder at the repo root — see `contract/README.md` for the full writeup. Short version:

- `contract/types.ts` is now the actual source of truth for every entity shape. `lib/types.ts` just re-exports from it, and `lib/api.ts` / `lib/mockData.ts` were rewritten to genuinely build against these stricter shapes (ids, timestamps, foreign keys included) — not a parallel simplified type set that happens to look similar.
- `contract/openapi.yaml` mirrors it, and is a **validated, loadable OpenAPI 3.0 document** (checked with `openapi-spec-validator`, not just "is this YAML").
- Real modeling calls made along the way — User split from Profile, Milestone/Commitment normalized out of Goal instead of nested, Badge split into catalog + per-user earned state — are documented with reasoning in `contract/README.md`, since Olusegun may want to push back on any of them.
- **Two acceptance criteria I can't mark done:** actually reviewing this with Olusegun, and committing it to a shared docs repo — both need access/coordination I don't have. The files are ready for both; someone needs to do the human part.

## Structure

```
app/                    → routes (App Router)
  page.tsx              → Splash
  welcome/               → Welcome (2-slide intro carousel)
  intake/                → 4-step Intake (sector → education/time → constraints → confirm)
  persona/                → Persona Selection
  (app)/                 → route group: everything behind the bottom tab nav
    layout.tsx            → mounts BottomTabNav + FeedbackSurveyModal once, hydrates
                             cross-tab data — this is what makes tab state persist
    chat/                  → Chioma Mentor Chat
    goals/                 → Goals Overview
    goals/action/          → Daily Action Card
    goals/milestones/[goalId]/ → Goal Milestone Path
    library/               → Insight Library
    progress/              → Progress Board
components/
  Icon.tsx                → Material Symbols Outlined wrapper — matches the export's icon font
  BottomTabNav.tsx        → Chat / Goals / Library / Progress
  FeedbackSurveyModal.tsx → global modal, opened via shared state from anywhere
  SankofaMotif.tsx        → exact SVG path from the export's splash screen
  ui/                     → Button, Chip, ProgressRing, MilestoneRoad, Skeleton
                            (rebuilt to DESIGN.md's Components spec)
lib/
  types.ts                → domain types (User/Goal/Milestone/Commitment/ChatMessage/etc. —
                            a lightweight version of what G1.3 will formalize)
  mockData.ts              → ALL seed data lives here only — real sample content from the
                             export (Kofi Mensah, Poultry Business - Kumasi, the 5 personas,
                             real goal/chat/insight copy)
  api.ts                   → the ONLY file components import data from. Every function
                             currently resolves mockData with a simulated 250ms latency (so
                             loading states are real, not skipped). Swap a function's body for
                             a real fetch() call later — no component needs to change. This is
                             what satisfies the "isolated mock layer" criterion.
  store.tsx                → shared app state (React Context + useReducer): persona, profile,
                             chat messages/draft, favorites, feedback modal, theme. Lives above
                             the tab routes, so switching Chat → Goals → Chat never loses your
                             draft message or scroll position.
```

## Acceptance criteria checklist

- [x] All 11 unique screens render from React components, not raw exported HTML
- [x] Mobile (390px) / desktop (1280px+) responsive layouts — verified by resizing; not yet
      pixel-diffed against the desktop screen.png variants (`*_desktop` folders in the export)
      — worth a dedicated visual-regression pass (this is literally what G2.5 is for)
- [x] Bottom tab nav (Chat / Goals / Library / Progress) works and preserves state across tabs
      (shared Context lives above the routes, not per-page state)
- [x] Mock data layer isolated in one module (`lib/mockData.ts`, accessed only via `lib/api.ts`)
      so it can be swapped for live API calls without touching UI components

## Notes for whoever picks up G1.2 / G1.3 / G1.4 next

- **G1.2 (theme tokens):** the CSS variable + Tailwind structure is ready and now uses the
  *real* DESIGN.md values for light mode — see `app/globals.css`. Dark mode still needs real
  tokens from design (see departure #1 above). A working theme toggle already exists in the
  app shell header.
- **G1.3 (API contract):** `lib/types.ts` is a deliberately lightweight starting point, not the
  final shared contract — expect it to be superseded.
- **G1.4 (PWA/offline/a11y):** `public/manifest.json` is a placeholder; no service worker yet.
  Tap targets are already ≥44px and focus-visible states are already in place globally, to save
  you some of that pass.
