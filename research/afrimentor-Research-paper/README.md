# AfriMentor AI — Research Paper (G1.6 / G2.2)

arXiv-ready LaTeX project. Standard `article` class, natbib + bibtex for
citations — deliberately not tied to a specific venue's style file yet,
since venue isn't decided (see `docs/paper-scope-decision.md`).

## Build

```bash
make          # produces main.pdf
make clean    # removes build artifacts
```

Requires a standard TeX Live install (`pdflatex`, `bibtex`). Verified
building genuinely clean — 6 pages, **zero warnings of any kind** on the
final pass (no undefined citations, no undefined references, no
overfull/underfull hboxes).

## Status

| Section | Status |
|---|---|
| Abstract | Placeholder — write last, after Method section is complete |
| Introduction | **Drafted, 702 words** (AC: ≥500) |
| Related Work | **Drafted, 1,432 words** — all references from both proposals cited (AC met in full) |
| Method | **Drafted** (card C5.5) — C1–C4 training procedures, real hyperparameters from `research/configs/*.yaml`, dataset split |
| Evaluation & Results | **Drafted, updated (card C5.5)** — comparative table now the real `eval-freeze-v2` numbers, with AfriMentor checkpoint IDs recorded for C2-C4; added a Human Evaluation subsection; mid-pilot section explicitly marked placeholder pending real pilot data (see below) |
| Discussion & Limitations | **Drafted & Co-authored — now partially stale (card C5.5 finding)**: extensively builds on the same not-yet-real pilot numbers the Results section now discloses as placeholder (qualitative themes T1–T5, deployment-realities claims, DG4/DG5, the AI-disclosure comprehension claim). Not rewritten here — flagged for the team, since it's previously signed-off co-authored content |
| Conclusion | **Drafted** — summary of findings, contributions, and outlook |
| Reproducibility Appendix | **Added (card C5.5)** — frozen snapshot reference, checkpoints, configs, dataset split, judge config, known gaps (no training seed logged), reproduction commands |

## Important history — read this before touching the citations

An earlier version of this repo cited several papers found via independent
web search that matched an author surname + year mentioned in early
planning tickets, but turned out to be **the wrong paper** — a different,
real, unrelated work by a different author who happened to share a last
name. That happened because the tickets referenced citations by shorthand
("Lee et al. 2024," "Liu et al. 2025," etc.) without the full proposal
documents to check against, and multiple different real papers can match
the same rough author+year+topic search.

**That problem is now fully resolved.** The team's actual two proposal
documents (`Proposal_1__Personality_Aligned_RLHF...` and
`Proposal_2__LLM_Mentor_for_Low-Income_Youth...`) were provided directly,
each with a complete APA reference list. Every citation in
`refs.bib` and `sections/related_work.tex` was rewritten from those lists
— the actual authoritative source — not from search-engine guessing.
Five papers that turned out wrong in the old version, corrected in this
one:

| Shorthand | Old (wrong) paper | Corrected paper, from the real proposal |
|---|---|---|
| Lee et al. 2024 | "RLAIF vs. RLHF" (Google) | **TRAIT**: a psychometric personality testset for LLMs |
| Li et al. 2024 | "ReMax" / "Quantifying AI Psychology" (flagged ambiguous) | **BIG5-CHAT**: shaping LLM personalities via training on human-grounded data |
| Jiang et al. 2023 | "Machine Personality Inventory" (Guangyuan Jiang, NeurIPS) | **PersonaLLM** (Hang Jiang et al.): whether LLMs can express an assigned persona's traits |
| Liu et al. 2025 | "Synthetic Socratic Debates" | **LPITutor**: an LLM-based personalized intelligent tutoring system |
| Park et al. 2024 | "Generative Agent Simulations of 1,000 People" | Conversation-based tutoring system with explicit student modeling (CHI EA 2024) |

Two citations previously flagged as **unverifiable** are now fully resolved:
Han et al. 2025 → "The Personality Illusion" (self-report vs. behavior
dissociation in LLMs); Sharma et al. 2025 → a systematic review of LLMs
in personalized learning. Both are now real, cited entries — not
placeholders.

**All 19 references across both proposals are now in `refs.bib` and all
19 are actually cited** (`\citet{}`) somewhere in `sections/related_work.tex`
— programmatically verified, not just claimed: every bib key has exactly
one matching citation, no orphans either direction.

## Structure

```
main.tex                       — top-level document
sections/introduction.tex       — drafted, 702 words
sections/related_work.tex       — drafted, 1,432 words, all 19 references cited
refs.bib                        — bibliography (19 entries, rewritten from the
                                   real proposal reference lists — see history above)
docs/paper-scope-decision.md    — 1-paper vs. 2-paper analysis, now confirmed
                                   against the full proposal documents
                                   (recommendation only — still needs actual
                                   team agreement, not something I can produce)
```

## What still isn't done, honestly

- **Team agreement on paper scope** (1 combined vs. 2 companion papers) —
  `docs/paper-scope-decision.md` has a reasoned recommendation (two
  companion papers), but "agreed by all 4 team members" requires an actual
  conversation between Grace, Olusegun, Daniel, and Chukwuebuka that I
  can't hold on your behalf.
- A handful of arXiv IDs in `refs.bib` are independently confirmed
  (marked `% CONFIRMED` with the ID); the rest are cited exactly as the
  proposals' own reference lists give them (which mostly just say
  "arXiv preprint" without an ID). Worth a pass to track down the
  remaining IDs before final submission, but not blocking for a draft.
