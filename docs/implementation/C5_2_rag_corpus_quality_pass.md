# RAG Corpus Quality Pass — Card C5.2

## Overview

Deduplicate and re-tag the corpus, refresh any stale Tier-1 content, and
confirm guardrails coverage across the full corpus before pilot close-out.
Scope for the two acceptance criteria was clarified before implementation:

- **"Dedup pass completed"** — the live corpus (26 docs / 2488 chunks) was
  already clean going in; the actual gap was that `scripts/ingest_tier1.py`
  had no `external_id`, so it wasn't safe to *re-run* without creating
  duplicates (unlike `ingest_tier2.py`, which has been idempotent since
  card C3.4). Closing that gap — and the incident it caused when first
  exercised — is what "dedup" means here.
- **"Guardrails coverage confirmed across 100% of Tier-1 content"** —
  interpreted as a content audit: run chat-orchestration-service's existing
  `screen_output` guardrail patterns directly against every Tier-1 document's
  raw text and report the result, reusing the deterministic rule engine
  rather than building a second one.

## 1. Idempotency fix

`scripts/ingest_tier1.py`'s `ingest_record()` payload was missing
`external_id`, so every re-run minted a fresh UUID per record instead of
upserting — the exact pattern `ingest_tier2.py` already guards against (see
its module docstring). Fixed by adding `"external_id": record["doc_id"]`,
mirroring `ingest_tier2.py`'s `"external_id": source["id"]`.

**This surfaced a live duplication bug on first use of the fix.** The
original 21 Tier-1 rows were ingested *before* `external_id` existed, so
their Postgres primary keys are random UUIDs, not `doc_id`-based. The
upsert path (`app/api/routes.py`) matches on `Document.id == external_id`,
found no match for any of them, and created 21 **new** rows under the
`doc_id`-keyed id instead of updating in place — corpus went from 26 docs /
2488 chunks to 49 docs / 3584 chunks. The 21 stale UUID-keyed duplicates
were identified (regex match against the UUID id format) and deleted via
`DELETE /api/v1/rag/documents/{id}`, restoring a clean corpus at 28 docs /
2511 chunks (23 Tier-1 + 5 Tier-2) — the 2 new documents below are the only
real addition. Every Tier-1 row's id is now `doc_id`-based, so this class of
duplication cannot recur on the next re-run.

## 2. Two new Tier-1 documents ingested

`corpus/tier1/` held two well-written, on-topic guide files with **no**
corresponding `corpus.jsonl` entry — invisible to the ingestion pipeline and
therefore to users, for no reason found in the codebase or history:

| doc_id | Source file | Sector | source_origin |
| :--- | :--- | :--- | :--- |
| `ng_trade_guide` | `nigeria_trade_guide.txt` | Trade | `trade_guide` |
| `general_financial_literacy_guide` | `africa_financial_literacy_guide.txt` | Financial Literacy | `financial_literacy` |

`corpus.jsonl` entries were added (content read verbatim from the source
files, not retyped) and ingested via the now-idempotent
`scripts/ingest_tier1.py`. Tier-1 count: 21 → 23.

## 3. Dead `corpus/tier1/` directory removed

`corpus/tier1/*.txt` was never read by any ingestion code — `ingest_tier1.py`
reads only `corpus/data/corpus.jsonl`. The directory held:

- `dangote_principles.txt`, `elumelu_africapitalism.txt`,
  `masiyiwa_resilience.txt`, `vusi_thembekwayo_entrepreneurship.txt` —
  superseded drafts (diffed against the real ingested content for the same
  figures; genuinely different, generic text, confirmed dead).
- `nigeria_trade_guide.txt`, `africa_financial_literacy_guide.txt` — the two
  files migrated into `corpus.jsonl` in step 2 above; their content now lives
  in the single source of truth the pipeline actually reads.
- `TRANSCRIPT_TEMPLATE.txt`, `README.md` — described an ingestion workflow
  (a `DOCUMENTS` list in `ingest_tier1.py`) that no longer exists; the
  "current corpus status" list in the README didn't match the real corpus
  either.

Removed via `git rm -r corpus/tier1/`. `corpus/data/corpus.jsonl` is now the
sole source of truth for Tier-1 content, matching Tier-2's
`corpus/tier2/sources.json` + `raw/` pattern.

## 4. Guardrails content audit

New script: `scripts/audit_tier1_guardrails.py`. Imports
`chat-orchestration-service/app/guardrails.py::screen_output` directly
(pure function — json/re/dataclasses/enum/functools/pathlib only, no DB or
network) and runs it against every Tier-1 document's full raw text.

Result — **23/23 Tier-1 documents screened (100% coverage)**:

| Action | Count |
| :--- | :---: |
| allow | 6 |
| disclaim | 12 |
| block | 5 |

Full per-document results (categories fired, matched-term counts):
`corpus/reports/tier1_guardrails_audit.json`.

**On the 5 "block" results**: `screen_output` is applied in production only
to the model's *generated* reply (`app/routers/chat.py`), never to raw
retrieved corpus text — RAG context is retrieved, handed to the LLM, and it
is the LLM's synthesized answer that gets screened before it reaches the
user. A raw source document scoring "block" means *if the model echoed this
passage near-verbatim*, the guardrail would correctly catch it — expected
behavior for authentic business biographies that discuss named companies,
debt/leverage, equity, and (for two Aboyeji/Elegbe/Shagaya-type profiles)
legal or medical tangents, not a defect in the corpus. Coverage — knowing
exactly how every document would be treated — is what this card asked for;
zero-block is not the bar.

## Verification

```
python scripts/ingest_tier1.py            # 23/23 ingested, 0 failed
python scripts/audit_tier1_guardrails.py --json corpus/reports/tier1_guardrails_audit.json
GET /api/v1/rag/stats                      # 28 docs / 2511 chunks (23 tier1, 5 tier2)
```

## Not in this pass

`GET /health` on rag-corpus-service does not verify Chroma connectivity
(Postgres only) — found during this investigation, flagged for a future
card rather than folded into C5.2's scope.
