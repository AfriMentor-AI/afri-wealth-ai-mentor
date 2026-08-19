# Supervised Persona Fine-Tuning - Card C2.1

## Overview

Condition **C2** is the second alignment condition in the AfriMentor research
pipeline. It applies parameter-efficient supervised fine-tuning to
`Qwen/Qwen2.5-7B-Instruct` using curated Chioma mentorship conversations. C2 is
a research experiment, not a production deployment mechanism. The production
runtime model and service boundaries remain governed by
[ADR-0002](../adr/0002-base-llm-selection.md).

The intended comparison is:

```text
C1 baseline prompting -> C2 supervised fine-tuning -> C3 DPO -> C4 RLHF
```

## Current implementation

There are two C2 execution paths. The reproducible Kaggle path is documented in
`research/notebooks/afri-mentor.ipynb`; the repository runner is
`research/experiments/02_supervised_finetuning/run.py`.

The Kaggle/Unsloth path:

1. Loads Qwen through `FastLanguageModel` with 4-bit quantization and applies
	the Qwen chat template.
2. Loads the Kaggle SFT train and validation JSONL files and formats their
	message conversations.
3. Attaches the configured LoRA adapter and trains with TRL `SFTTrainer`.
4. Applies `train_on_responses_only`, so prompt tokens do not contribute to the
	supervised loss.
5. Saves the adapter, evaluates the held-out test split, logs the C2 metrics to
	MLflow, and publishes the adapter when credentials are available.

The repository runner is deliberately GPU only. It:

1. Loads the YAML configuration from `research/configs/c2_supervised_finetuning.yaml`.
2. Exits safely with a warning when PyTorch or CUDA is unavailable.
3. Loads the Qwen base model with 4-bit NF4 quantization.
4. Prepares the model for k-bit training and attaches a LoRA adapter to the configured attention projections.
5. Loads `sft_train.jsonl` and `sft_val.jsonl` with the Hugging Face Datasets loader.
6. Trains with TRL `SFTTrainer` using the configured schedule and BF16 settings.
7. Saves the adapter to `checkpoints/final`.
8. Logs trainer evaluation metrics and the adapter artifact to MLflow.

The two paths are not identical: the Kaggle notebook contains the response-only
masking and end-to-end evaluation used for the reported C2 results, while the
repository runner does not import the C3 checkpoint evaluation harness and does
not log the shared `avg_*` persona metric keys needed for direct C1/C2
comparison.

## Data and MLflow contracts

The dataset contract is defined in `research/configs/dataset.yaml`:

- SFT records contain `(system, user, assistant)` messages plus persona, sector, country, and quality metadata.
- The configured split is 80% train, 10% validation, and 10% test with seed 42.
- The current repository split contains 21 training, 5 validation, and 5 test records.
- `quality_score` must meet the configured minimum of 0.7.

The held-out test split is not consumed by the current C2 runner. It is the
correct split for post-training comparison and should remain untouched during
training and validation.

Each run creates `C2_supervised_persona_finetuning` and logs the condition,
model, LoRA and training parameters, trainer metrics, and the adapter artifact
under `sft_adapter` when model logging is enabled. Trainer metrics describe the
SFT objective; they are not equivalent to the shared persona metric suite.

The Kaggle MLflow store is approximately 1.2 GB and is intentionally not
committed. This repository keeps the metric summary and configuration, while
the raw run database and artifacts remain in Kaggle or should be exported to a
remote MLflow/artifact store. The root `.gitignore` explicitly excludes
`mlruns/`.

## GPU runbook

```bash
cd research
pip install -r requirements.txt -r requirements-gpu.txt
export LLM_API_KEY=...                  # needed for shared LLM-as-judge scoring
export MLFLOW_TRACKING_URI=...          # optional remote MLflow backend
python experiments/02_supervised_finetuning/run.py
```

The configured output is:
`research/experiments/02_supervised_finetuning/checkpoints/final`.
The Hub repository is configured as `afrimentor/chioma-sft-v1`. Publication and
deployment require evaluation and safety review.

## Current gaps and path differences

The Kaggle implementation does apply response-only loss masking and is the
source of the documented training run. The repository runner uses TRL
`SFTTrainer` directly and does not call `train_on_responses_only`; it therefore
must not be treated as equivalent to the Kaggle notebook until that behavior is
ported and tested there.

There is currently no C2-specific offline test directory. The real 7B training
run and checkpoint generation require CUDA and `research/requirements-gpu.txt`.
The Kaggle evaluation produces the C2 rubric results, but comparable C1/C2
`avg_*` MLflow keys still require the shared checkpoint harness, followed by
human persona-fidelity and safety evaluation.

## Acceptance criteria

- [x] C2 configuration defines the base model, QLoRA parameters, dataset paths, training schedule, and MLflow experiment.
- [x] GPU-gated SFT runner loads the model, dataset, LoRA adapter, and trainer.
- [x] Adapter checkpoint is saved under the configured output directory.
- [x] Trainer metrics and model artifacts are logged to MLflow.
- [x] Response-only loss masking is implemented in the Kaggle execution path.
- [x] The Kaggle checkpoint is evaluated on the shared held-out test split with the C2 metric suite.
- [ ] Response-only loss masking is ported to the repository runner and covered by tests.
- [ ] The saved checkpoint is evaluated with the C1/C3 shared checkpoint harness and comparable `avg_*` MLflow keys.
- [ ] Human persona-fidelity and dedicated safety evaluation are completed.
- [ ] A real 7B checkpoint is reproduced on a GPU node from the tracked runner.

## References

- `research/experiments/02_supervised_finetuning/run.py`
- `research/configs/c2_supervised_finetuning.yaml`
- `research/configs/dataset.yaml`
- `research/evaluation/checkpoint_eval.py`
- [C3.1 implementation](C3_1_contrastive_learning.md)
- [C2 experiment README](../../research/experiments/02_supervised_finetuning/README.md)