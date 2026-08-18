# Alignment Condition C2: Supervised Persona Fine-Tuning

This experiment fine-tunes the base model on a curated dataset of conversations to align it with the Chioma persona.

## Goal

The goal is to improve the model's performance on the five key metrics: `persona_adherence`, `cultural_fluency`, `anti_dependency`, `financial_accuracy`, and `urgency`.

## Running the experiment

The experiment is run using the `run.py` script in this directory.

```bash
python experiments/02_supervised_finetuning/run.py
```

The script uses the configuration from `research/configs/c2_supervised_finetuning.yaml` and logs the results to MLflow.

## Results

The following is a summary of the evaluation results from a recent run.

| Key                             | Status     |
| ------------------------------- | ---------- |
| lm_head.layer_norm.weight       | UNEXPECTED |
| lm_head.bias                    | UNEXPECTED |
| lm_head.layer_norm.bias         | UNEXPECTED |
| lm_head.dense.weight            | UNEXPECTED |
| lm_head.dense.bias              | UNEXPECTED |
| roberta.embeddings.position_ids | UNEXPECTED |
| pooler.dense.weight             | MISSING    |
| pooler.dense.bias               | MISSING    |

**Notes:**
- UNEXPECTED: can be ignored when loading from different task/architecture; not ok if you expect identical arch.
- MISSING: those params were newly initialized because missing from the checkpoint. Consider training on your downstream task.

### Evaluation Summary

| Metric                 | Score  |
| ---------------------- | ------ |
| persona_adherence      | 0.2000 |
| cultural_fluency       | 0.3000 |
| anti_dependency        | 0.2000 |
| financial_accuracy     | 0.4000 |
| urgency                | 0.2000 |
| rouge_l                | 0.0576 |
| bert_score_f1          | 0.8055 |
| **composite_score**    | **0.2600** |

## Analysis

For a more detailed analysis of the results, including comparison with the baseline, please refer to the notebooks in the `research/notebooks/` directory. The results of this run should be logged in MLflow, where you can inspect the metrics, parameters, and any generated artifacts.
