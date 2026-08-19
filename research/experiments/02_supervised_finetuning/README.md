# Alignment Condition C2: Supervised Persona Fine-Tuning

This experiment fine-tunes the base model (Qwen/Qwen2.5-7B-Instruct) on a curated dataset of African financial mentorship conversations using QLoRA to test whether the Chioma persona can be reinforced in model generations.

## Scope and status

C2 is one research condition in the four-condition alignment study (C1 baseline
prompting, C2 supervised fine-tuning, C3 DPO, and C4 RLHF). It is not a
production deployment record and does not establish that the model is safe,
financially reliable, or generalises to African users. Production still follows
the runtime model and service boundaries in [ADR-0002](../../../docs/adr/0002-base-llm-selection.md).

The results below are an exploratory run record. The current repository split
contains 21 training, 5 validation, and 5 held-out test records, so the results
should not be treated as a statistically reliable estimate of real-world
performance. C2 also does not complete Proposal 1's evaluation on its own:
cross-condition comparison, human persona-fidelity assessment, and dedicated
safety checks remain necessary.

## Goal
 
The objective was to test whether fine-tuning could improve adoption of the Chioma persona—characterised by direct, practical business mentorship, African economic context (mobile-money rails and SACCOs), anti-dependency framework delivery, and appropriate urgency around the cost of inaction.
 
The run reports that the LoRA adapter was trained using response-only loss masking, merged into full 16-bit standalone precision, and published to Hugging Face Hub. Any downstream deployment remains subject to review.
## Running the Experiment

The fine-tuning pipeline is executed via the `run.py` script:
```bash
python experiments/02_supervised_finetuning/run.py
```
The Kaggle implementation in [`research/notebooks/afri-mentor.ipynb`](../../../research/notebooks/afri-mentor.ipynb) reads the SFT data, applies response-only loss masking via Unsloth (`train_on_responses_only`), evaluates the held-out test split, and logs training runs and artifacts to MLflow. The repository runner also uses TRL's `SFTTrainer`, but does not yet include that masking or the shared checkpoint evaluation wiring; see the [C2 implementation notes](../../../docs/implementation/C2_1_supervised_finetuning.md).

To run the evaluation suite against the held-out test split:
```bash
python evaluation/evaluate_runner.py
```

## Results

### Quantitative Metric Progression

| Metric | C1 Baseline | SFT Run 2 (Prompt) | SFT Peak (15-Pair, T=0.1) | SFT Final (22-Pair, Fixed Parse) | Total Gain (vs. C1) |
|---|---|---|---|---|---|
| Persona Adherence | 0.2000 | 0.4400 | 0.6600 | 0.4900 | +145% |
| Cultural Fluency | 0.3700 | 0.4600 | 0.4700 | 0.4500 | +27.0% |
| Anti-Dependency | 0.3100 | 0.4900 | 0.6500 | 0.4900 | +109% |
| Financial Accuracy | 0.3200 | 0.6800 | 0.6600 | 0.4600 | +106% |
| Urgency (Cost of Inaction) | 0.2300 | 0.2400 | 0.4400 | 0.4900 | +113% |
| ROUGE-L | 0.1400 | 0.1583 | 0.1898 | 0.1298 | +35.6% |
| BERTScore F1 | 0.8300 | 0.8501 | 0.8615 | 0.8454 | +3.8% |
| **Composite Score** | **0.2750** | **0.4720** | **0.5870** | **0.4760** | **+113.5%** |

### Analysis

*   **Persona and Framework Scores**: In the best recorded run, the evaluator scored `persona_adherence` at 0.66 and `anti_dependency` at 0.65, compared with 0.20 and 0.31 for C1. These are observed score differences, not proof of generalisation or causation.
*   **Decoding Sensitivity**: Setting inference sampling to low temperature ($T=0.1$) locked generation paths into the learned low-rank adapter trajectories, preventing base-model assistant drift.
*   **Urgency & Financial Grounding**: The recorded runs reached `urgency` 0.44+ and `financial_accuracy` 0.66 at their respective peaks. Because these scores come from an LLM-as-judge evaluation and the runs use different data/decoding settings, they should be interpreted as exploratory rather than as an attribution of improvement to the training method.

The five-dimensional rubric and ROUGE-L/BERTScore values are useful engineering
diagnostics. They do not replace the study's planned human persona-fidelity,
behavioral-consistency, and safety evaluation.

## Artifacts & Model Checkpoints

*   **LoRA Adapter Checkpoint reported by the run**: `Danleon56/chioma-sft-v1`
*   **Final Merged 16-Bit Standalone Model reported by the run**: `Danleon56/qwen2.5-7b-chioma-sft-merged`
*   **Experiment Tracking**: Full metric progressions, configurations, and evaluation artifacts are logged under the `C2_supervised_persona_finetuning` MLflow experiment.

The Kaggle MLflow store is not committed to this repository because it is
approximately 1.2 GB. The metric summary and configuration are recorded here;
the raw MLflow runs and artifacts remain in the Kaggle execution environment or
must be exported to a remote MLflow/artifact store when reproducibility access
is required. The repository's `mlruns/` ignore rule is intentional.

The published artifacts are research outputs pending deployment review; they
must not be treated as approved financial-advice models without the remaining
evaluation and safety gates.
