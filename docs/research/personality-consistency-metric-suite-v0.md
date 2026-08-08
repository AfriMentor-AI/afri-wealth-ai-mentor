# Personality-Consistency Metric Suite v0 Specification

- **Card ID:** C1.3
- **Service / Area:** Research & Evaluation Service (`services/research-evaluation-service`)
- **Author:** Chukwuebuka (Lead ML Engineer)
- **Status:** Approved / Specification v0
- **Depends On:** D1.4

---

## 1. Overview & Objectives

The **Personality-Consistency Metric Suite v0** provides quantitative evaluation for persona adherence and conversational consistency of the **CHIOMA** AI mentor agent in the AfriMentor platform.

The metric suite evaluates mentor output along two fundamental dimensions:
1. **Trait-Level Fit**: Measuring how closely the mentor's expressed traits (evaluated via adapted Big Five Inventory [BFI] / TRAIT-style probes or dialogue turns) match the target profile vector defined for CHIOMA.
2. **Behavioral Consistency**: Measuring multi-turn stability across a conversation (prompt-to-line alignment, line-to-line stability, and Q&A responsiveness), grounded in the methodology of *Abdulhai et al. (2025)*.

The suite is designed with a **pluggable scoring backend**. In v0, a deterministic, zero-dependency `LexicalScorer` is used to allow metric computation and CI evaluation without heavy ML model requirements. In Sprint 5 (Card C2.3), an embedding-based neural backend (`EmbeddingScorer`) will be plugged in without modifying metric definitions or API schemas.

---

## 2. Target Personality Profile Schema (`CHIOMA Target Profile`)

The target profile defines the target values for personality traits on a $[0, 1]$ numerical scale.

### 2.1 Ordinal-to-Scale Mapping

| Target Level | Scale Value ($v_i^*$) | Description |
| :--- | :---: | :--- |
| `VERY_LOW` | 0.05 | Minimal expression of the trait |
| `LOW` | 0.25 | Weak expression |
| `MODERATE_LOW` | 0.40 | Slightly below average |
| `MODERATE` | 0.50 | Neutral / balanced |
| `MODERATE_HIGH` | 0.70 | Noticeable positive expression |
| `HIGH` | 0.85 | Strong positive expression |
| `VERY_HIGH` | 0.95 | Dominant trait expression |

### 2.2 CHIOMA Profile Definition (`data/chioma_profile.v0.json`)

The CHIOMA profile combines the standard Big Five personality traits with four distinctive domain-specific traits:

#### Big Five Traits
- **Conscientiousness** (`HIGH` = 0.85): Methodical, structured financial guidance, goal-oriented.
- **Agreeableness** (`MODERATE_HIGH` = 0.70): Empathetic, supportive, respectful tone.
- **Openness** (`HIGH` = 0.85): Open to innovative business models, adaptive strategies.
- **Emotional Stability** (`HIGH` = 0.85): Calm under risk, reassuring during financial distress.
- **Extraversion** (`MODERATE` = 0.50): Balanced engagement—neither overly dominant nor passive.

#### Distinctive Traits
- **Urgency / Action Bias** (`HIGH` = 0.85): Focuses on actionable next steps and execution.
- **Resilience Modeling** (`HIGH` = 0.85): Encourages perseverance through business hurdles.
- **Anti-Dependency** (`HIGH` = 0.85): Promotes client self-reliance rather than perpetual dependence.
- **Cultural & Regional Fluency** (`HIGH` = 0.85): Uses African business contexts and relatable nuances.

---

## 3. Metric Definitions & Mathematical Formulas

### 3.1 Metric Family 1: Trait-Level Fit

Trait-level fit measures the agreement between an observed trait vector $\mathbf{u} \in \mathbb{R}^N$ and the target profile vector $\mathbf{v}^* \in \mathbb{R}^N$.

#### 3.1.1 Individual Trait Estimation
For a given text string $T$ and trait $k$ with positive markers $M_k^+$ and counter-markers $M_k^-$:
$$c_{\text{pos}} = \text{Hits}(T, M_k^+), \quad c_{\text{neg}} = \text{Hits}(T, M_k^-)$$

Saturation function with $k=3.0$:
$$S(c) = \frac{c}{c + 3.0}$$

Estimated value:
$$\text{lift} = S(c_{\text{pos}}) \times (1.0 - 0.5)$$
$$\text{drop} = S(c_{\text{neg}}) \times 0.5$$
$$\hat{u}_k = \text{clamp}(0.5 + \text{lift} - \text{drop}, 0.0, 1.0)$$

If no evidence exists ($c_{\text{pos}} + c_{\text{neg}} = 0$), $\hat{u}_k = 0.5$ and `evidence_count` is 0.

#### 3.1.2 Cosine Similarity Fit Score
The primary headline trait fit metric is the Cosine Similarity between the estimated vector $\mathbf{u}$ and target vector $\mathbf{v}^*$:

$$\text{CosineSimilarity}(\mathbf{u}, \mathbf{v}^*) = \frac{\mathbf{u} \cdot \mathbf{v}^*}{\|\mathbf{u}\|_2 \|\mathbf{v}^*\|_2} = \frac{\sum_{i=1}^N u_i v_i^*}{\sqrt{\sum_{i=1}^N u_i^2} \sqrt{\sum_{i=1}^N (v_i^*)^2}}$$

#### 3.1.3 Mean Absolute Error (MAE)
$$\text{MAE}(\mathbf{u}, \mathbf{v}^*) = \frac{1}{N} \sum_{i=1}^N |u_i - v_i^*|$$

---

### 3.2 Metric Family 2: Behavioral Consistency

Adapted from *Abdulhai et al. (2025)*, behavioral consistency measures multi-turn coherence across three sub-scores:

#### 3.2.1 Prompt-to-Line Consistency ($C_{\text{p2l}}$)
Measures how well each mentor response aligns with the system persona prompt $P$.
$$C_{\text{p2l}} = \frac{1}{M} \sum_{m=1}^M \text{Sim}(P, T_m^{\text{mentor}})$$
where $M$ is the number of mentor turns.

#### 3.2.2 Line-to-Line Consistency ($C_{\text{l2l}}$)
Measures tone and voice stability across pairwise mentor turns.
$$C_{\text{l2l}} = \frac{2}{M(M-1)} \sum_{i=1}^{M-1} \sum_{j=i+1}^M \text{Sim}(T_i^{\text{mentor}}, T_j^{\text{mentor}})$$
If $M < 2$, $C_{\text{l2l}} = 1.0$ with $n_{\text{line\_to\_line}} = 0$.

#### 3.2.3 Q&A Consistency ($C_{\text{qa}}$)
Measures responsiveness between user questions/prompts and immediately following mentor answers.
$$C_{\text{qa}} = \frac{1}{K} \sum_{k=1}^K \text{Sim}(T_k^{\text{user}}, T_{k+1}^{\text{mentor}})$$
where $K$ is the count of adjacent User $\rightarrow$ Mentor turn pairs. If $K = 0$, $C_{\text{qa}} = 1.0$ with $n_{\text{qa\_pairs}} = 0$.

#### 3.2.4 Aggregate Behavioral Consistency Score
$$C_{\text{aggregate}} = \frac{C_{\text{p2l}} + C_{\text{l2l}} + C_{\text{qa}}}{3}$$

---

### 3.3 Composite Score Blending

The overall dialogue composite score $S_{\text{composite}}$ balances Trait Fit and Behavioral Consistency:

$$S_{\text{composite}} = 0.5 \times \max(0.0, \text{CosineSimilarity}(\mathbf{u}, \mathbf{v}^*)) + 0.5 \times C_{\text{aggregate}}$$

---

## 4. Pluggable Scoring Backend Architecture

The metric definitions interact with text scoring via the `SimilarityScorer` Protocol:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class SimilarityScorer(Protocol):
    def similarity(self, a: str, b: str) -> float:
        ...

    def similarity_matrix(self, texts: list[str]) -> list[list[float]]:
        ...
```

- **`LexicalScorer` (v0 Default)**: Computes sublinear TF-weighted cosine similarity (`1 + log(tf)`) after stopword removal and tokenization.
- **`EmbeddingScorer` (C2.3 Integration)**: Implements the same protocol using dense vector embeddings (e.g. sentence-transformers or OpenAI embeddings).

---

## 5. CLI Execution & Benchmark Results on Toy Dialogues

The scoring script `scripts/run_metrics.py` evaluates dialogues and produces structured text and JSON reports.

### 5.1 Command Usage

```bash
# Basic console text report over bundled toy dialogues
python scripts/run_metrics.py

# Machine-readable JSON output
python scripts/run_metrics.py --format json

# Export report to file
python scripts/run_metrics.py --out report.json
```

### 5.2 Benchmark Results Summary

| Dialogue ID | Type | Trait Cosine | Trait MAE | Prompt-to-Line | Line-to-Line | Q&A Consist. | Composite |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `toy-001-on-persona` | On-Persona | 0.9888 | 0.1016 | 0.0689 | 0.0824 | 0.1253 | **0.5400** |
| `toy-002-off-persona` | Off-Persona | 0.8813 | 0.4262 | 0.0191 | 0.0341 | 0.0000 | **0.4500** |
| `toy-003-persona-drift` | Persona Drift | 0.9708 | 0.2282 | 0.0398 | 0.0382 | 0.1267 | **0.5200** |
| **Corpus Aggregate** | **Average** | **0.9470** | **0.2520** | **0.0426** | **0.0516** | **0.0840** | **0.5032** |

### 5.3 Probe-Based Trait Fit Benchmark
- **Probe Cosine Similarity:** 0.9817
- **Probe MAE:** 0.1281
- *Note:* Probe-based and dialogue-based scores are intentionally decoupled, following *Han et al. (2025)* findings on self-report vs. behavioral expression divergence.

---

## 6. Acceptance Criteria Traceability Matrix

| Requirement | Implementation Artifact | Status |
| :--- | :--- | :---: |
| Metric spec document committed | `docs/research/personality-consistency-metric-suite-v0.md` | ✅ Complete |
| Trait-level fit probe & dialogue scoring | `app/metrics/trait_fit.py`, `app/metrics/profile.py` | ✅ Complete |
| Behavioral consistency (p2l, l2l, qa per Abdulhai 2025) | `app/metrics/consistency.py` | ✅ Complete |
| Pluggable similarity backend protocol | `app/metrics/scoring.py` | ✅ Complete |
| Scoring script runs on $\ge 3$ toy dialogues outputting numeric report | `scripts/run_metrics.py` | ✅ Complete |
