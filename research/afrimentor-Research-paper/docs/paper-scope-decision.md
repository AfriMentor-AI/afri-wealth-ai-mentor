# Paper Scope Strategy: One Combined Paper vs. Two Companion Papers

**Status: RECOMMENDATION ONLY — not yet agreed by the team.** This ticket's acceptance criteria calls for a decision "documented and agreed by all 4 team members." I can produce the analysis and a recommendation; I can't produce the agreement itself — that needs an actual conversation between Grace, Olusegun, Daniel, and Chukwuebuka. Treat this doc as the input to that conversation, not its output. Once you've actually discussed it, update the "Decision" section at the bottom with what was agreed and who signed off.

## The two proposals, as currently scoped

- **Proposal 1 — Personality-Aligned RLHF.** A methods contribution: can RLHF, conditioned on structured trait profiles from real achievers, produce a language model that stays faithful to a specific reasoning style across a full conversation? Evaluated via the persona-fidelity methodology (blind rating + archetype identification) already drafted for US-H4.
- **Proposal 2 — LLM Mentor for Low-Income Youth.** A user-centered/HCI contribution: what do African micro-entrepreneurs actually want from AI mentorship, and does persona-constraining change engagement or perceived usefulness versus a generic assistant? Evaluated via the pilot, interviews, and usage-log analysis (Epic F).

## Option A: One combined "AfriMentor" applied paper

**Case for:**
- One writing/review/submission effort instead of two, with a 4-person team already carrying full-time engineering work — real bandwidth savings.
- The system is one system. A combined paper can tell one coherent story: "we built X, here's how the model was aligned, here's what real users thought of it" — which is arguably a *more* compelling applied-AI narrative than either half alone.
- Avoids the awkwardness of two papers that cite each other's not-yet-published claims.

**Case against:**
- Methods (RLHF alignment) and user-study (HCI/qualitative) reviewers tend to be different audiences with different standards for what counts as sufficient evidence. A combined paper risks being evaluated as "the RLHF section lacks rigor" by one reviewer and "the user study lacks depth" by another, simultaneously — the classic failure mode of papers trying to do two things.
- Page-limit pressure at most applied-AI venues will force cutting one half down to a subsection, which undersells whichever half loses that fight.

## Option B: Two companion papers

**Case for:**
- Each paper can be written for and reviewed by the audience actually equipped to judge it — an ML/alignment venue for Proposal 1, an HCI/education/AI-for-development venue for Proposal 2.
- Each gets full page budget to make its case properly, including negative/null results if the persona-fidelity numbers or the user study don't come out cleanly — harder to do honestly in a combined paper under space pressure.
- Two publication credits instead of one, which matters for a team using this partly as portfolio/research-writer output (per Grace's role transition).

**Case against:**
- Real additional writing overhead: two intros, two related-work sections, two sets of reviewer responses, on a team that's simultaneously running Sprints 2-5 of actual product engineering.
- Proposal 2 (the user study) depends on Proposal 1 (the persona-conditioned model) actually working — if Proposal 1's fidelity results come out weak, Proposal 2 either has to acknowledge that as a limitation or wait, which creates a sequencing dependency two papers make more visible than one flexible combined draft would.

## My recommendation

**Two companion papers**, sequenced rather than simultaneous: Proposal 1 (methods) drafted first since Proposal 2's user study needs a working, evaluated persona system to study in the first place. This isn't a strong preference over Option A — it's a real trade-off — but the audience mismatch under Option A is the deciding factor for me: a combined paper is more likely to read as competent-but-shallow to both audiences than as a strong contribution to either.

**Confirmed after reading both full proposal documents** (this recommendation was originally written from summaries; the actual documents make the audience-mismatch case stronger, not weaker). Proposal 1's methodology is a genuinely rigorous ML benchmarking design — four alignment conditions (prompting, supervised fine-tuning, contrastive learning, RLHF) compared on a two-layer metric suite (psychometric trait-fit, behavioral consistency, optional latent-space probing), plus a dedicated safety check. Proposal 2 is a mixed-methods HCI pilot — a 20–30 participant two-arm study (tailored mentor vs. generic assistant) with pre/post quantitative measures and semi-structured qualitative interviews. These aren't just different topics; they're different research traditions with different standards for what counts as sufficient evidence, reviewed by people trained to evaluate one or the other, rarely both well.

**If the team picks Option A instead**, the LaTeX structure in this repo still works — `sections/method.tex` and `sections/evaluation.tex` (not yet drafted) would just need to accommodate both proposals' content rather than split into two repos.

## What this doesn't resolve

- Target venue(s) for either option — not addressed here, needs its own conversation once scope is settled.
- Author order and contribution statement — also not addressed here.

## Decision

*(Fill in after the team actually discusses this — date, decision, and who was present/agreed.)*

- Decision:
- Date:
- Present/agreed:
