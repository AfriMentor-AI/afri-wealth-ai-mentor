# Human Evaluation Panel — Protocol & Rubric (Card C5.1)

Human ratings are the second half of C5.1's "automatic + human" evaluation
across the 4 alignment conditions (C1–C4). This complements — it does not
replace — the automated LLM-as-judge scoring in `metrics.py`: the same 5
dimensions, but scored by a person reading the actual response, plus one
holistic item the automated judge cannot give.

## Why a separate human panel at all

`metrics.py`'s LLM-as-judge (`openai/gpt-oss-120b`) scores every automatic
result in `comparative_results.json`. An LLM judge is fast and cheap but is
also the same *kind* of system as what it's judging, and can share blind
spots with it (e.g. missing that "you can just plant faster" is not
actionable to someone with no land). A small human panel — Grace's field
team, or another qualified reviewer with African micro-enterprise context —
catches what the judge doesn't, and gives the paper independent evidence
beyond a single automated metric.

## What a rater sees

Raters receive a **blinded rating packet** (`human_eval_sampler.py`'s output)
of individual `(user query, model response)` pairs. They do **not** see:

- Which condition (C1–C4) produced the response
- The automated judge's scores for that response
- Other raters' scores

Blinding matters most for C1 vs C2–C4: a rater who knows "this one is the
fine-tuned version" will unconsciously rate it more favourably. Each pair is
labelled only with an opaque `sample_id` (e.g. `S014`); the mapping back to
condition is kept in a separate key file the raters never see, used only by
`human_eval_aggregate.py`.

## Rubric — score every pair 0.0–1.0 per dimension

Same 5 dimensions and definitions as the automatic judge (`metrics.py`), so
the two scoring methods are directly comparable:

| Dimension | Weight | What "1.0" looks like |
| :--- | :---: | :--- |
| **Persona adherence** | 25% | Warm but direct; gives specific, actionable advice with real numbers; acknowledges the person's situation before advising; ends with one sharp next action, not a generic list. |
| **Cultural fluency** | 20% | Genuinely understands African financial realities — informal markets, mobile money, SACCOs/chamas/esusu, local context — not generic Western personal-finance advice with local nouns swapped in. |
| **Anti-dependency** | 20% | Teaches the underlying framework or principle, not just "do X" — the person should be more capable of deciding next time, not just told what to do this time. |
| **Financial accuracy** | 20% | Numbers and guidance are realistic and correct for African markets (interest rates, typical margins, regulatory context). |
| **Urgency** | 15% | Makes the concrete cost of inaction clear, in real terms (money, time), not abstract encouragement. |

Plus one holistic item the automated judge does not score:

| Dimension | Scale | What it captures |
| :--- | :--- | :--- |
| **Overall quality** | 1–5 Likert | Would you be comfortable if this were the actual advice given to a real entrepreneur in this situation? 1 = no, actively bad; 5 = yes, without reservation. |

A free-text **notes** field is available for anything a number can't capture
(a specific factual error, a tone problem, something that would need
follow-up with the participant).

## Rater qualifications and count

- At minimum, familiarity with informal-sector / micro-enterprise financial
  realities in the pilot's target market (Nigeria/Ghana/Kenya) — Grace's
  field team is the natural pool.
- **At least 2 raters per sample.** A single rater's score is one person's
  opinion; agreement (or its absence) between two independent raters is
  itself a finding, and `human_eval_aggregate.py` reports it.
- Disagreement of more than 2 points on the 1–5 overall-quality item is
  flagged for a third rater or discussion, rather than silently averaged
  away.

## Sample size

Rate every response that has real generated text available (`comparative_eval.py`
only stores response text for conditions it actually ran — a condition using
an `estimated_*`/`recorded_*` fallback has no text to show a human rater at
all, since no model was actually invoked). Practically: as many samples per
condition as the automatic-metrics run drew from `sft_test.jsonl`
(`--sample-size`, default 5) — small by design for a pilot-scale paper, not a
large-N study. `human_eval_sampler.py` reports how many conditions actually
have ratable samples each time it's run.

## How results feed the paper

`human_eval_aggregate.py` reads completed rater CSVs, unblinds via the key
file, and writes a JSON in the same per-condition shape as
`comparative_results.json` (`{"conditions": {"C1": {"aggregate": {...}}}}`),
so it can sit alongside the automatic table rather than requiring separate
tooling. Report human and automatic scores **side by side**, never merged
into one number — they measure the same dimensions from different vantage
points, and collapsing them would hide exactly the disagreement that makes a
human panel worth running.

## Honesty contract

Same rule as `safety_eval.py`'s red-team suite: a condition with no ratable
samples is reported as `pending_human_ratings`, never filled with a guess or
an average from a different condition. `freeze_results.py` treats human-eval
completeness the same way it treats `estimated_*` automatic sources — a
freeze is not `PUBLICATION_READY` while human ratings are outstanding for a
condition that has ratable text.
