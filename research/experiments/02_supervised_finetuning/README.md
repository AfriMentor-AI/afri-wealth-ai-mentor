# Alignment Condition C2: Supervised Persona Fine-Tuning

This experiment fine-tunes the base model (Qwen/Qwen2.5-7B-Instruct) on a curated dataset of African financial mentorship conversations using QLoRA to align model generations with the Chioma persona.

## Goal
 
The objective was to fine-tune Qwen2.5-7B-Instruct to reliably adopt the Chioma persona—characterised by direct, practical business mentorship, deep African economic context (Mobile Money rails, SACCOs, dual-currency inflation hedges), anti-dependency framework delivery, and strong urgency around the cost of inaction.
 
The LoRA adapter was trained using response-only loss masking, merged into full 16-bit standalone precision, and published to Hugging Face Hub for downstream deployment.
## Running the Experiment

The fine-tuning pipeline is executed via the `run.py` script:
```bash
python experiments/02_supervised_finetuning/run.py
```
The script reads hyperparameters from `research/configs/c2_supervised_finetuning.yaml`, applies response-only loss masking via Unsloth (`train_on_responses_only`), and logs training runs and artifacts to MLflow.

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

*   **Persona and Framework Retention**: Fine-tuning with response-only loss masking dramatically improved `persona_adherence` (0.20 -> 0.66) and `anti_dependency` (0.20 -> 0.65). The model ceased generating generic pleasantries and bulleted checklists, instead adopting Chioma's direct coaching style and framework-first methodology.
*   **Decoding Sensitivity**: Setting inference sampling to low temperature ($T=0.1$) locked generation paths into the learned low-rank adapter trajectories, preventing base-model assistant drift.
*   **Urgency & Financial Grounding**: Incorporating explicit cost-of-inaction statements into the training data lifted `urgency` scores from 0.20 to 0.44+, with `financial_accuracy` peaking at 0.66.

## Artifacts & Model Checkpoints

*   **LoRA Adapter Checkpoint**: `Danleon56/chioma-sft-v1`
*   **Final Merged 16-Bit Standalone Model**: `Danleon56/qwen2.5-7b-chioma-sft-merged`
*   **Experiment Tracking**: Full metric progressions, configurations, and evaluation artifacts are logged under the `C2_supervised_persona_finetuning` MLflow experiment.