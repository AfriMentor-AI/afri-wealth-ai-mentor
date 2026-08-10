# Pilot Data-Collection Plan v0 — Proposal 2

- **Card ID:** C2.5
- **Service / Area:** Research & Evaluation Service (`services/research-evaluation-service`)
- **Authors:** Chukwuebuka (Lead ML Engineer), Grace (PM / Research Writer)
- **Status:** Draft v0 — **pending Grace's review**
- **Depends On:** None (card); in practice needs C2.4 guardrails live before any participant contact

---

## 1. Overview & Objectives

Proposal 2 asks an empirical, user-centred question: *what do African micro-entrepreneurs
with limited formal education and constrained device/data access actually want from an AI
mentorship product, and does a personality-constrained persona change engagement or
perceived usefulness relative to a generic assistant?*

This document specifies how we collect the data to answer it: who is eligible, what they
consent to, what we measure, and when.

**Design.** Two arms, parallel, 2–4 weeks of use:

| Arm | Condition | n (target) |
| :--- | :--- | :---: |
| **A** | AfriMentor prototype — CHIOMA persona, African-authored RAG corpus, voice-note first | 15 |
| **B** | Generic LLM control — same base model, same interface, no persona conditioning, no corpus grounding | 15 |

**Read section 2 before section 5.** The sample size the card specifies determines what
this study can claim, and it is not what a two-arm design normally implies.

---

## 2. What This Sample Size Can and Cannot Detect

This section exists because a 2-arm, 20–30 participant design *looks* like a test of
"does the persona beat the control" and cannot function as one. Stating that now is
cheaper than discovering it at analysis.

Two-sided α = .05, power = .80, computed against the noncentral *t* distribution
(`services/research-evaluation-service/scripts/pilot_power_analysis.py`).

### 2.1 Between groups (Arm A vs Arm B)

| Total N | Per arm | Minimum detectable effect (Cohen's *d*) |
| :---: | :---: | :---: |
| 20 | 10 | 1.32 |
| 24 | 12 | 1.20 |
| 30 | 15 | 1.06 |

A *d* of 1.06 is enormous — larger than most well-established effects in behavioural
science. Conversely, power to detect a **moderate** effect (*d* = 0.50), the realistic size
of a persona manipulation, is:

| Total N | Power at *d* = 0.50 |
| :---: | :---: |
| 20 | 18% |
| 24 | 22% |
| 30 | 26% |

**Detecting *d* = 0.50 between arms at 80% power would require 128 participants (64/arm).**
At N = 30 we are roughly three times as likely to miss a real moderate effect as to find
it. A null result here is uninformative, and a significant one is more likely to be noise
than signal.

### 2.2 Within subject (pre vs post, pooled across arms)

| N pairs | Minimum detectable effect (Cohen's *d_z*) |
| :---: | :---: |
| 20 | 0.66 |
| 24 | 0.60 |
| 30 | 0.53 |

This is a usable range. Pre/post change pooled across both arms is the **only quantitative
comparison this pilot is powered for**, and it answers "did using an AI mentor of any kind
move financial self-efficacy" — not "is CHIOMA better than a generic model."

### 2.3 Attrition

| Attrition | On N = 24 | On N = 30 |
| :---: | :---: | :---: |
| 15% | 20 retained → *d* = 1.32 | 26 retained → *d* = 1.15 |
| 25% | 18 retained → *d* = 1.41 | 22 retained → *d* = 1.26 |

Attrition in a 2–4 week unsupervised mobile study with this population will not be zero.
**Recruit to 30, not 20.** The cost difference is small; the difference in what survives is
not.

### 2.4 What this means for the plan

The pilot is specified as a **feasibility and instrument-validation study with descriptive
between-arm comparison**, not a hypothesis test. Concretely:

- **Primary aims are feasibility aims** (§5.1) — recruitment rate, retention, instrument
  comprehension, engagement volume, guardrail incidence. These are what N = 30 measures well.
- **Between-arm differences are reported as effect sizes with confidence intervals, never
  as p-values.** No arm "wins." The CI width is itself a deliverable: it sizes the full study.
- **Qualitative data is a primary source, not colour.** At this N the exit interviews will
  tell us more about the research question than the surveys will.
- **The pre-registered deliverable is a power calculation for the full study**, using this
  pilot's observed variance. That is the single most valuable number this pilot produces.

> **Open question Q1 (Grace):** Is a 2-arm split the right use of 30 participants at all?
> A single-arm feasibility study of Arm A only would give tighter within-subject estimates,
> richer qualitative data per participant, and a cleaner read on whether the product works —
> at the cost of no control comparison, which §2.1 shows we cannot make anyway. My
> recommendation is to keep both arms **only** if the control is needed to validate the
> *instruments* (i.e. to show the survey discriminates between conditions at all); otherwise
> go single-arm. This is a genuine design decision and I would rather you make it than have
> it defaulted.

---

## 3. Eligibility Criteria

### 3.1 Inclusion

| # | Criterion | Rationale / how verified |
| :--- | :--- | :--- |
| I1 | Age 18–35 | Target population is youth entrepreneurs; 18 is the floor for independent consent. Self-reported at screening. |
| I2 | Currently operating a micro-business, or actively starting one within the last 12 months | The mentorship content assumes an active venture. Screening: "tell us what your business does" (free text, reviewed). |
| I3 | Informal or micro-enterprise sector — market trading, smallholder agribusiness, micro-manufacturing, small services | Matches the corpus and persona design (ADR-0003). |
| I4 | Owns and personally uses an Android smartphone | The prototype is a PWA; iOS is out of scope for the pilot (ADR-0002 device profile). |
| I5 | Conversational in English or Nigerian Pidgin | See §3.4 — a real constraint, not a preference. |
| I6 | Able to give informed consent, verified by the comprehension check in §4.4 | Low literacy is **not** an exclusion; failure to understand what participation involves is. |

### 3.2 Exclusion

| # | Criterion | Rationale |
| :--- | :--- | :--- |
| E1 | Employee or contractor of the AfriMentor project, or their immediate family | Conflict of interest; response bias. |
| E2 | Currently receiving formal business mentorship or enrolled in a financial-literacy programme | Confounds pre/post — we could not attribute change to the prototype. |
| E3 | Prior participation in AfriMentor user testing (Sprint 1 intake research) | Familiarity effects. |
| E4 | In acute financial distress such that a 2–4 week study delays access to real help | Ethical, not methodological. See §4.6. |

### 3.3 Sampling and assignment

- **Recruitment:** purposive, via market-trader associations and micro-enterprise
  cooperatives, supplemented by snowball referral. This is a convenience sample and the
  writeup must say so — no claim of representativeness is available at this N.
- **Stratification:** balance arms on (a) gender and (b) self-reported baseline smartphone
  comfort (low / medium / high). Both plausibly dominate any persona effect at this N, so
  leaving them to chance risks a confound larger than the thing being studied.
- **Assignment:** block randomisation within stratum, blocks of 4, allocation sequence
  generated in advance and held by whoever is *not* running that participant's session.
- **Blinding:** participants are not told which arm they are in, and the exit interviewer
  must not know either — the interview is where expectancy effects would do most damage.
  Full blinding of the field team is not achievable (the two builds look different), and
  the writeup should say so plainly.

### 3.4 Language — unresolved

The corpus and persona work assume Nigerian Pidgin, Yoruba, Twi and Swahili are in scope
(ADR-0003, ADR-0002). The prototype's actual language support at pilot time will likely be
**English and Pidgin only**.

Restricting eligibility to English/Pidgin speakers (I5) systematically excludes exactly the
low-formal-education participants Proposal 2 is about. That is a threat to validity, not a
detail.

> **Open question Q2 (Grace + Daniel):** What languages will the prototype actually support
> on pilot day? If English-only, I5 needs rewriting and §9 needs a limitation stating the
> sample skews toward higher formal education than the target population. If Pidgin voice
> input works, the consent script (§4) must be produced in Pidgin too — a translation task
> with lead time.

---

## 4. Consent

### 4.1 Format — why oral, not a signature

The target population includes participants with limited formal literacy. A written form
with a signature line does two bad things: it excludes people who cannot comfortably read
it, and it produces a signature that does not evidence understanding.

**The consent process is therefore an oral script, delivered in person or by voice call,
with an audio-recorded affirmation and a comprehension check.** A printed copy is left with
every participant regardless of whether they read it — someone else may read it to them
later, and they need the contact details. A signed written form remains available for
anyone who prefers one.

### 4.2 Required content

Ordered as delivered. Full script to be drafted by Grace on approval of this outline.

| # | Element | Must state |
| :--- | :--- | :--- |
| C1 | Who is asking | The AfriMentor AI research project; named individuals; that this is research, not a product launch or a loan/grant scheme. |
| C2 | Why | We are testing whether an AI mentor is useful to entrepreneurs like them, and we do not yet know if it is. |
| C3 | What participation involves | Two ~30-min surveys, 2–4 weeks of app use at their own pace, one ~30-min exit interview. Concrete total time cost. |
| C4 | **That it is an AI, not a human mentor** | Non-negotiable, in plain language. See §4.3. |
| C5 | **That the advice may be wrong** | It can make mistakes; it is not a licensed financial adviser; do not make an irreversible financial decision on its say-so alone. |
| C6 | What we collect | Survey answers, conversations including voice notes, app usage timings, interview recording. Enumerated explicitly — no "and related data." |
| C7 | Who sees it | Named research team only; stored encrypted; **not** shared with employers, lenders, government, or cooperative leadership. This fear is specific and real in this population. |
| C8 | How long we keep it | Retention period and deletion date (§7). |
| C9 | Voluntariness | They may stop at any time, skip any question, and withdraw their data afterwards without giving a reason, and nothing they receive is contingent on continuing. |
| C10 | Compensation | Amount, form and schedule — including that it is **not** contingent on completing the study (§4.5). |
| C11 | Risks | Time cost; possible discomfort discussing money; residual re-identification risk in qualitative quotes. |
| C12 | Benefits | Honest: possible personal benefit, no guarantee. Do not oversell. |
| C13 | Contact | A named person, a working phone number, and a route to complain to someone **not** on the research team. |
| C14 | Data rights | Access, correction, deletion, and how to exercise them by phone rather than in writing. |

### 4.3 The AI-disclosure requirement

C4 is the element most likely to be softened for engagement, and it must not be. The whole
premise of Proposal 1 is that this persona is convincingly human-like in reasoning style;
that is precisely why participants must know it is not human — before first contact, in
plain language, and again in the app itself.

The persona may stay in character throughout. It may not deny being an AI if asked
directly. **This is currently unguarded in C2.4** — a persona that convincingly denies its
own nature to a low-income user is the worst failure mode this project has.

> **Action Q7 (Chukwuebuka):** add an `ai_disclosure` category to
> `app/data/guardrail_rules.v1.json`. Note this is an *output*-side concern, unlike every
> existing category, which the C2.4 design does not currently distinguish — see the
> implementation note filed with that work.

### 4.4 Comprehension check

Consent is only informed if it is understood. After the script, before enrolment, ask three
open questions — answered in the participant's own words, not yes/no:

1. "In your own words, what will you be doing over the next few weeks?"
2. "Who or what will you be talking to in the app?" — **must** elicit that it is a computer
   / AI / not a real person. A wrong answer is a stop condition, not a prompt to re-explain
   and proceed.
3. "If you decide next week that you don't want to continue, what happens?" — must elicit
   that they may stop freely and keep the compensation.

Failure on any item: re-explain once, re-ask. Second failure → do not enrol. Record the
outcome; the enrolment-failure rate is itself a feasibility finding (§5.1).

### 4.5 Compensation

- Paid in **two instalments** — at enrolment and at exit — so nobody is financially trapped
  into continuing, and stated as such in C10.
- Paid via mobile money, with the payment identifier stored separately from research data (§7).
- Benchmarked against local median daily earnings for the sector, not a Western norm.

> **Open question Q3 (Grace + Olusegun):** amount and budget line. Enough to respect
> participants' time, not so much that it becomes coercive for a low-income participant — a
> real tension needing a named decision rather than a default.

### 4.6 Distress and safeguarding

Participants are discussing money under real financial pressure.

- **Referral list.** A short list of legitimate local financial-counselling and
  small-business support services, given to every participant at exit regardless of arm.
  Prepared before recruitment opens.
- **Stop rule.** If a participant discloses acute distress — inability to feed their family,
  predatory-debt entrapment, self-harm — the interviewer stops the protocol, provides the
  referral list, and the participant is withdrawn with full compensation. This is not a
  data-collection opportunity.
- Guardrail blocks (`leverage_debt`, `guaranteed_return`) fired during the study are logged
  and reviewed weekly. A cluster in one participant is a welfare signal, not just a metric.

### 4.7 Ethics approval and data protection — **blocking**

> **Open question Q4 (Grace + Olusegun) — this blocks participant contact.**
>
> 1. **Which institutional ethics board reviews this?** The project is not attached to any
>    university IRB that appears in the repo. Human-subjects research with a low-income
>    population needs external review; "we are careful" is not a substitute, and a journal
>    will ask.
> 2. **Which country is the pilot running in?** The repo points at Nigeria (Lagos) but also
>    Ghana and Kenya. This determines the applicable data-protection law — Nigeria's NDPA
>    2023, Ghana's Data Protection Act 843 (2012), or Kenya's DPA 2019 — each with different
>    requirements for lawful basis, cross-border transfer, and whether a Data Protection
>    Impact Assessment is mandatory.
> 3. **Cross-border transfer:** if participant data (including voice notes) is processed by
>    an LLM API hosted outside the pilot country, that is a transfer requiring a lawful basis
>    and disclosure in C7. This must be settled before the consent script is final, because
>    it changes what the script has to say.
>
> **No participant may be contacted until Q4.1 and Q4.2 have answers.** Everything else in
> this document can proceed in parallel.

---

## 5. Measures

### 5.1 Primary — feasibility (what N = 30 measures well)

| # | Measure | Source | Success threshold |
| :--- | :--- | :--- | :--- |
| F1 | Recruitment rate | Screening log | ≥ 30 enrolled within 3 weeks of opening |
| F2 | Consent comprehension pass rate | §4.4 outcomes | ≥ 80% pass on first or second attempt |
| F3 | Retention to exit interview | Attendance | ≥ 75% (below this the quantitative comparison is not worth reporting — §2.3) |
| F4 | Engagement volume | App telemetry: sessions, turns, voice notes | Descriptive; establishes the variance estimate for the full study |
| F5 | Instrument comprehension | Interviewer log of items needing re-explanation | Any item flagged by > 20% of participants is revised before the full study |
| F6 | Guardrail incidence | `messages.guardrail_action` / `guardrail_categories` | Descriptive by category and arm; feeds §4.6 review |
| F7 | Technical failure rate | Error logs, voice-transcription failures | Descriptive; a voice pipeline that fails on real accents is a finding |

F5 and F7 are most likely to change the full study's design, and both are
qualitative-adjacent. Budget interviewer attention accordingly.

### 5.2 Secondary — financial literacy (pre/post)

**Instrument:** the **"Big Three"** (Lusardi & Mitchell) — the international standard, used
in 20+ countries, which makes our numbers comparable to published baselines.

| # | Construct | Correct answer |
| :--- | :--- | :--- |
| L1 | Compound interest | "More than" |
| L2 | Inflation | "Less than" |
| L3 | Risk diversification | "False" |

**Adaptations required — all three documented as deviations:**

1. **Currency and amounts** localised to the pilot country, keeping the arithmetic
   identical (the standard adaptation across all 20+ country deployments).
2. **L3 must be rewritten.** The standard item contrasts a "single company's stock" with a
   "stock mutual fund." Mutual funds are not a meaningful category for an informal-sector
   market trader, and Lusardi & Mitchell themselves note item 3 is the one where wording
   changes *do* affect responses and where guessing is highest. Testing an irrelevant
   concept measures our question quality, not their literacy. Replace with a diversification
   item in their actual context — concentrating stock in one product line versus spreading
   it — and report it as a **modified item, not the Big Three**, scored separately.
3. **Administer orally.** Written administration confounds literacy with financial literacy.

> **Open question Q5 (Grace):** the OECD/INFE Toolkit 2022 has a validated core
> questionnaire designed for cross-country use *including* low-income and emerging
> economies, with existing translations and adaptation guidance. It is longer than the Big
> Three. Worth taking its financial-knowledge subset instead? Better construct coverage and
> adaptation provenance, at roughly 10 minutes more participant time. My lean is the Big
> Three for the pilot, OECD/INFE for the full study; your call.

### 5.3 Secondary — financial self-efficacy (pre/post)

**Instrument:** the **Financial Self-Efficacy Scale (FSES)**, Lown (2011) — 6 items, single
factor, α = .76, 4-point response (1 = exactly true … 4 = not at all true), items
negatively worded and summed to 6–24 with higher = greater self-efficacy.

This is the construct Proposal 2 most plausibly moves, and §2.2 shows the within-subject
comparison is adequately powered for it. **It is the pilot's primary quantitative outcome.**

**Adaptations required:**

- **Item 6 ("I worry about running out of money in retirement") must be replaced.** Formal
  retirement is not a meaningful frame for informal-sector traders with no pension system.
  Substitute a matched-format item on longer-term financial security in their own terms —
  covering a major unexpected expense, or keeping the business running through a bad season.
  Report as **FSES-modified**, with the 5 unmodified items also reported separately so the
  standard scale stays comparable to published work.
- Items 1–5 are usable close to verbatim; "spending plan" (item 1) glossed orally if the
  participant does not recognise the phrase.
- Administer orally; anchor the 4-point scale with a visual aid, since numeric-scale
  comprehension cannot be assumed.
- Reverse-scoring applied at analysis. Every item is negatively worded, which is also a
  satisficing risk on oral administration — watch for straight-lining.

> **Licensing (Grace):** the FSES is published in the *Journal of Financial Counseling and
> Planning*. Confirm permitted research use and required attribution before the instrument
> is printed. Likewise for any OECD/INFE items under Q5.

### 5.4 Secondary — perceived usefulness and engagement

The direct Proposal 2 outcome. Post only.

| # | Construct | Approach |
| :--- | :--- | :--- |
| U1 | Perceived usefulness | Short adapted TAM-style block, 4 items, oral, simple anchors |
| U2 | Intention to continue using | Single item + free-text "why / why not" |
| U3 | Perceived relevance to *their* context | Did it understand their business, their market, their constraints |
| U4 | Trust and appropriate reliance | Did they act on advice, and did they check it against anyone else — the interesting failure mode is over-trust, not under-trust |
| U5 | Mentor-likeness | The persona-specific item. Behavioural anchors, not adjectives. |

U4 and U5 are where the arms would differ if they differ at all. **Report as effect sizes
with CIs (§2.4), never as a significance test.**

### 5.5 Primary qualitative — exit interview

Semi-structured, ~30 min, recorded with separate consent, conducted by someone blind to arm.
Thematic analysis, two independent coders on a 20% subsample, disagreement resolved by
discussion.

Core areas: what they actually used it for; a moment it helped and a moment it did not; how
they described it to other people; whether they trusted it and how they decided; what they
would change; whether they would recommend it and to whom.

**This is a primary source, not supporting colour** (§2.4).

---

## 6. Protocol and Timeline

| Phase | Timing | Activity |
| :--- | :--- | :--- |
| Screening | Day −7 to 0 | Eligibility (§3), stratum assignment |
| Enrolment | Day 0 | Consent (§4), comprehension check, **T0 survey**, device setup, first guided session |
| Use period | Day 1–14 (or 28) | Own-pace use. Weekly check-in call: technical problems and welfare only — no coaching, no prompting to use it more |
| Exit | Day 14/28 +3 | **T1 survey**, exit interview, compensation instalment 2, referral list |
| Analysis | +2 weeks | Coding, effect-size estimation, **full-study power calculation** |

**T0 must complete before first app exposure** — a baseline taken after first contact is not
a baseline.

> **Open question Q6 (Grace):** 2 weeks or 4? Four gives a better shot at real behaviour
> change and a more informative retention figure; two reduces attrition and fits the sprint
> calendar. Given §2.3 I lean 2 weeks at N = 30 over 4 weeks at N = 20 — retention protects
> the analysis more than duration does.

---

## 7. Data Management

| Item | Handling |
| :--- | :--- |
| Identifiers | Name, phone, mobile-money ID held in a **separate** access-controlled store, linked to research data only by participant code |
| Research data | Survey responses, conversation logs, telemetry, transcripts — participant code only |
| Voice notes | **The re-identification risk.** Voice is biometric under all three candidate regimes. Stored encrypted, transcribed, audio deleted at study end unless the participant separately consents to retention |
| Transcripts | Names of people, businesses and specific locations redacted at transcription |
| Retention | Per §4 C8. Linkage file destroyed first, at the earliest point analysis allows |
| Quotes in publication | Only with the specific consent captured at exit, reviewed for indirect identifiability — in a small sector cohort a business description identifies someone as effectively as a name |

Storage location and encryption specifics depend on Q4.2/Q4.3.

---

## 8. Analysis Plan (pre-specified)

Pre-specified before collection, deliberately: at this N, analytic flexibility would
guarantee a finding whether or not one exists.

1. **Feasibility (F1–F7):** descriptive, against §5.1 thresholds. The primary output.
2. **Within-subject pre/post, pooled across arms:** paired comparison on FSES-modified
   (primary) and Big-Three-adapted (secondary), reported as *d_z* with 95% CI. Powered per §2.2.
3. **Between-arm:** difference in change scores, **effect size with 95% CI, no p-value, no
   claim of superiority.** The CI width is the deliverable — it sizes the full study.
4. **Qualitative:** thematic analysis (§5.5), reported alongside rather than subordinate to
   the quantitative results.
5. **Full-study power calculation** from observed variance. The most valuable output.
6. **Deviations log:** every adapted item (§5.2, §5.3), every protocol departure, every
   withdrawal with reason.

No subgroup analyses. At n = 15 per arm they would be noise, and pre-committing here is what
stops them appearing later.

---

## 9. Known Limitations

- **Underpowered for the between-arm question by design** (§2). The pilot cannot establish
  that CHIOMA outperforms a generic model; it establishes whether the study is runnable and
  how large the real one must be.
- **Convenience sample**, not representative of African micro-entrepreneurs generally.
- **Language restriction (§3.4)** likely skews the sample toward higher formal education —
  away from exactly the population Proposal 2 targets.
- **Both instruments are adapted**, so comparability to published norms is partial and the
  modified items are unvalidated in this population. Validating them is part of what the
  pilot is for.
- **Novelty effects** are unmeasurable at 2–4 weeks; engagement will overstate steady state.
- **Social desirability** — participants know the team built the thing they are evaluating.
  Blind interviewing (§3.3) mitigates but does not remove this.
- **No blinding of the field team** to arm (§3.3).

---

## 10. Open Questions

| # | Question | Owner | Blocking? | Status |
| :--- | :--- | :--- | :---: | :---: |
| Q1 | Two arms or single-arm feasibility, given §2.1? | Grace | Design | Open |
| Q2 | Which languages will the prototype actually support at pilot time? | Grace + Daniel | Eligibility + consent translation | Open |
| Q3 | Compensation amount and budget line | Grace + Olusegun | Consent script | Open |
| Q4 | **Ethics board, pilot country, cross-border data transfer** | Grace + Olusegun | **Participant contact** | Open |
| Q5 | Big Three, or OECD/INFE financial-knowledge subset? | Grace | Instrument | Open |
| Q6 | 2-week or 4-week use period? | Grace | Timeline | Open |
| Q7 | Add `ai_disclosure` guardrail category per §4.3 | Chukwuebuka | Pilot launch | Open |

---

## 11. References

- Lusardi, A., & Mitchell, O. S. (2011). *Financial Literacy and Retirement Planning in the
  United States.* NBER Working Paper 17108.
  https://www.nber.org/system/files/working_papers/w17108/w17108.pdf
- GFLEC. *Three Questions to Measure Financial Literacy.*
  https://gflec.org/wp-content/uploads/2015/04/3-Questions-Article2.pdf
- Lown, J. M. (2011). Development and Validation of a Financial Self-Efficacy Scale.
  *Journal of Financial Counseling and Planning, 22*(2), 54–63.
  https://files.eric.ed.gov/fulltext/EJ952966.pdf
- OECD (2022). *OECD/INFE Toolkit for Measuring Financial Literacy and Financial Inclusion
  2022.* OECD Publishing, Paris. https://doi.org/10.1787/cbc4114f-en
- Bandura, A. (2006). Guide for constructing self-efficacy scales. (Theoretical basis for the
  domain-specificity argument underlying the FSES.)

---

## 12. Sign-off

| Reviewer | Role | Status |
| :--- | :--- | :---: |
| Grace | PM / Research Writer — co-author, acceptance-criteria reviewer | ☐ Pending |
| Chukwuebuka | Lead ML Engineer — author | ☑ Drafted |
| Olusegun | Product Owner — needed for Q3, Q4 | ☐ Pending |

**Acceptance criterion (C2.5):** *Survey instrument and consent form drafted and reviewed by
Grace.* Drafted here; **review outstanding**.

---

**Document Version:** v0 (draft)
