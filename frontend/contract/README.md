# AfriMentor AI — Frontend/Backend API Contract (G1.3)

Two files, meant to be read together:

- **`types.ts`** — TypeScript source of truth. Consumed directly by the frontend today (`lib/types.ts` re-exports everything from here; `lib/api.ts` and `lib/mockData.ts` build against these exact shapes, not a simplified stand-in).
- **`openapi.yaml`** — OpenAPI 3.0 mirror of the same entities, for Olusegun/backend to scaffold against. **Validated with `openapi-spec-validator` — it's syntactically and structurally a real, loadable OpenAPI 3.0 document, not just YAML that looks plausible.**

If these two files ever disagree on a shape, that's a bug — figure out which one is stale and fix it, don't just pick one.

## Entities covered (all 11 required)

User, Profile, Persona, Goal, Milestone, Commitment, ChatMessage, InsightItem, FeedbackSurvey, DailyAction, StreakStat, Badge — plus two supporting join types (`InsightFavorite`, `UserBadge`) that fell out of modeling Badge/InsightItem as shared catalog data rather than per-user data. Explained inline in `types.ts` where they appear.

## Real modeling decisions worth flagging before Sprint 2 starts

These aren't arbitrary — each one trades something off, and Olusegun may reasonably want a different answer:

1. **User vs. Profile are separate entities.** `User` is the auth identity (phone/email, minimal). `Profile` is the Intake-flow business data. Splitting them means auth can change (phone → email → SSO) without touching business data's shape.
2. **Milestone and Commitment are normalized, not nested in Goal.** `GET /goals/{id}` does NOT return milestones inline — they're `GET /goals/{id}/milestones`. This matches how the data actually gets updated (milestones change status independently of their parent goal) and avoids ever having to PATCH a goal just to update one milestone.
3. **Badge is a shared catalog; earning it is per-user.** Same reasoning for `InsightItem` + `InsightFavorite`. `GET /progress/badges` returns the two joined together (`BadgeWithStatus`) — that join happens in `lib/api.ts` client-side against mock data today, and should happen server-side once real.
4. **`Persona.isRecommended` is request-scoped, not a stored property.** It's computed against whichever user is asking, not a fixed fact about the Persona.

## What's explicitly NOT in this stub yet

Flagged in `openapi.yaml`'s header comment too, repeating here since it matters for the Sprint 1 review:
- **No auth model.** Every path assumes a resolved user from session/token; none of that mechanism is specified here.
- **No pagination.** List endpoints return bare arrays. Fine for the pilot's data volume; will need cursor/offset pagination before it doesn't.
- **No error response shapes.** Just bare HTTP status codes as placeholders.

## Review status

**Not yet reviewed with Olusegun.** This satisfies the "write and publish the contract" half of this ticket's acceptance criteria; the "reviewed with Olusegun before Sprint 1 ends" half is a scheduling/conversation step I can't do on my own — that needs an actual sync between you two. Recommend walking through the four modeling decisions above specifically, since those are the ones most likely to need backend input before they're load-bearing.

**Not yet committed to a shared docs repo**, for the same reason — I don't have access to wherever that repo lives. These two files are ready to go in as-is; committing them is the remaining manual step.
