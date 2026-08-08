# Guardrails — high-risk advice filter (card C2.4)

AfriMentor's mentor persona gives financial guidance to low-income entrepreneurs. Before
C2.4 nothing stopped it from naming a specific financial instrument to buy, and
investment-adjacent replies carried no disclaimer. This module closes both gaps.

Implemented in `services/chat-orchestration-service/app/guardrails.py`, with policy held as
data in `app/data/guardrail_rules.v1.json`.

> **Spec status.** The card cites "report section 5.4 'Guardrails'". That section does not
> exist yet — `research/main.pdf` is still a skeleton and the word "guardrail" does not appear
> in it. The categories below are derived from the card description and the CHIOMA
> `counter_markers` in `persona-prompt-service/data/chioma_profile.v1.json`. **Reconcile this
> file with §5.4 once written**; because policy is data, that should be a JSON edit.

## Actions

| Action | Meaning |
| --- | --- |
| `allow` | Turn proceeds untouched. |
| `disclaim` | Reply is allowed; a category-appropriate disclaimer is appended. |
| `block` | Turn is refused in-persona. On input this happens *before* RAG retrieval and the LLM call. |

When several categories fire, the most severe action wins.

## Categories

| ID | Covers |
| --- | --- |
| `specific_instrument` | Naming a particular stock, share, fund, ETF or bond to buy. |
| `guaranteed_return` | Guaranteed / risk-free return claims, get-rich-quick framing. |
| `crypto_speculation` | Crypto, forex, binary options, CFDs, day trading. |
| `leverage_debt` | Borrowing to invest, loan sharks, pledging a home as collateral. |
| `tax_legal_evasion` | Evading tax or customs, off-the-books trading, laundering. |
| `medical_or_legal` | Medical or legal questions — outside the persona's scope. |

Each category carries two pattern tiers: `block_patterns` (an imperative request for a
specific instrument, or a guaranteed-return claim) and `disclaim_patterns` (general
investment-adjacent discussion that is legitimate to answer but needs a caveat).

## Integration

Two hooks in `app/routers/chat.py::send_message`:

1. **Pre-hook** — `screen_input` runs after the user turn is persisted and before
   `chat_completion`. A block short-circuits: no RAG query, no LLM call, and the assistant
   turn is `refusal_message(...)`. This is what "blocks retrieval" means in the card — the
   query never reaches the corpus.
2. **Post-hook** — `screen_output` runs on the generated reply, catching the model
   volunteering an instrument in answer to an innocuous question, which the pre-hook cannot
   see. A block replaces the reply; a disclaim appends via `apply_disclaimer`.

Commitment detection runs only on allowed turns, so a refused high-risk statement
("I will put all my savings into bitcoin") never becomes a tracked goal.

### Design decisions

**Deterministic, not model-based.** The acceptance criterion is 100% coverage of a fixed
red-team set, which needs a provable and stable decision procedure. An LLM classifier would
also fail open in CI, where `LLM_API_KEY` is unset and `app/llm.py` takes its stub path. The
module is structured so an LLM second pass could be layered in without changing the call sites.

**Fails closed.** If the rule file is missing or malformed, the turn is *blocked*. This is
deliberately the opposite of `app/rag.py::retrieve`, which swallows errors and returns `[]` so
chat survives RAG being down. A guardrail that fails open is not a guardrail.

**Refusals stay in persona.** Chioma declines and redirects to what she can help with. A flat
error string would read as a bug and would contradict the persona's counter-markers.

## Configuration

| Variable | Default | Effect |
| --- | --- | --- |
| `GUARDRAILS_ENABLED` | `true` | Only the exact string `false` disables it, so a typo or `0` cannot silently open the gate. |

The kill switch exists so a false positive blocking legitimate mentoring can be turned off in
production without a redeploy. Set in `docker-compose.yml` under `chat-orchestration-service`.

## API surface

`MessageResponse` gains two fields:

- `guardrail_action` — `allow` / `disclaim` / `block`, or `null` when guardrails are disabled
  or the turn predates C2.4.
- `guardrail_categories` — the category IDs that fired.

`disclaim` tells the client the disclaimer is **already appended** to `content`; it must not
add a second one. `matched_terms` is retained in-process for audit but deliberately never
returned — it would tell someone probing the filter exactly which phrasing tripped it.

## Deployment note

chat-orchestration-service has no Alembic; `app/database.py` uses `Base.metadata.create_all`,
which creates missing tables but **will not** add columns to an existing `messages` table. On
a deployed Postgres volume, run:

```sql
ALTER TABLE messages ADD COLUMN guardrail_action varchar(20);
ALTER TABLE messages ADD COLUMN guardrail_categories json DEFAULT '[]';
```

Tests are unaffected (fresh SQLite per test). Adopting Alembic for this service is filed as a
follow-up rather than bundled into C2.4.

## Red-team corpus

`research/datasets/redteam_high_risk_advice.v1.jsonl` — 46 attack prompts across all six
categories plus 15 benign controls, one JSON object per line
(`{id, prompt, category, expected}`).

`tests/test_guardrails.py::test_redteam_corpus_is_blocked_or_disclaimed` is the acceptance
test, parametrised so a regression names the offending prompt id. Two stronger assertions run
alongside it: that each prompt receives its *intended* action, and that the firing category
matches the label so the refusal text fits.

`test_benign_controls_are_allowed` is the counterweight — a filter that blocked everything
would satisfy the acceptance criterion and ruin the product.

Adding a category to the rule file without red-team prompts fails
`test_corpus_covers_every_category`.

```bash
cd services/chat-orchestration-service
python -m pytest tests/test_guardrails.py tests/test_chat_guardrails.py -q
```
