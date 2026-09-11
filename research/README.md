# AfriMentor AI — Research & Evaluation Workspace

**Card D1.4 | Epic: Foundation | Sprint 1**
Experiment tracking and eval harness for the 4 alignment conditions from Proposal 1.

---

## ⚠️ This is NOT the research-evaluation-service microservice

This `research/` directory and `services/research-evaluation-service/` are two
distinct things that serve completely different purposes:

| | `research/` (this folder) | `services/research-evaluation-service/` |
|---|---|---|
| **What it is** | ML training workspace | Production FastAPI microservice |
| **Where it runs** | Ephemeral cloud GPU nodes / local | 24/7 inside docker-compose |
| **Purpose** | Train LoRA/DPO/RLHF adapters | Audit live sessions, detect drift |
| **Dependencies** | PyTorch, PEFT, TRL, BitsAndBytes | FastAPI, SQLAlchemy only |
| **Called at runtime?** | Never | Every production session |
| **Sprint** | D1.4 scaffold now; C2–C4 in Sprint 4–5 | Sprint 5 (cards S5.2, S5.3) |

**The only connection between them:**
- `research/evaluation/metrics.py` scoring logic will be **ported** (not imported)
  into the microservice as a lightweight inference-time scorer in Sprint 5 — without
  the heavy ML training dependencies.
- Trained adapter weights from `research/` are deployed into `chat-orchestration-service`
  via the `LLM_MODEL` env var, not through the research-evaluation-service.

---

## The 4 Alignment Conditions

| ID | Condition | Method | Sprint | GPU Required |
|---|---|---|---|---|
| C1 | Baseline Prompting | Zero-shot / few-shot with Chioma persona prompt | 3 | No |
| C2 | Supervised Persona Fine-Tuning | QLoRA SFT on Chioma conversation demos | 4 | Yes |
| C3 | Persona-Aware Contrastive Learning | DPO on (chosen, rejected) persona pairs | 4 | Yes |
| C4 | RLHF / Preference Optimization | Reward model + PPO policy optimisation | 5 | Yes |

Each condition warm-starts from the previous: C1 → C2 → C3 → C4.

---

## Quick Start

```bash
cd research
pip install -r requirements.txt

# 1. Register all 4 MLflow experiments
python tracking/setup_mlflow.py

# 2. Open MLflow UI
mlflow ui --backend-store-uri sqlite:///tracking/mlflow.db
# → http://localhost:5000

# 3. Generate seed dataset
python datasets/scripts/ingest_raw.py
python datasets/scripts/process.py
python datasets/scripts/split.py

# 4. Run C1 baseline (no GPU needed)
python experiments/01_baseline_prompting/run.py
```

Set your LLM API key first:
```bash
export LLM_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
export LLM_BASE_URL=https://api.groq.com/openai/v1
```

---

## MLflow (via docker-compose)

```bash
docker compose up mlflow
# → http://localhost:5000
```

The MLflow server uses a SQLite backend in dev and Postgres in prod.
All experiment runs, metrics, and model artifacts are persisted in the `mlflowdata` Docker volume.

---

## Dataset Versioning (DVC)

```bash
# Initialise DVC (first time)
dvc init

# Run the full data pipeline
dvc repro research/datasets/dvc.yaml

# Configure a remote (S3/MinIO for prod)
dvc remote add -d myremote s3://afrimentor-research/datasets
dvc push
```

Dataset versions are tracked by Git commit. Every experiment config references
`research/configs/dataset.yaml` for the split seed — changing the seed creates
a new reproducible split version.

---

## GPU Experiments (C2, C3, C4)

Run on ephemeral cloud GPU nodes (RunPod / AWS EC2 g5.xlarge):

```bash
pip install -r requirements.txt -r requirements-gpu.txt
export MLFLOW_TRACKING_URI=http://<your-mlflow-host>:5000

# C2 — SFT
python experiments/02_supervised_finetuning/run.py

# C3 — DPO
python experiments/03_contrastive_learning/run.py

# C4 — RLHF (reward model first, then PPO)
python experiments/04_rlhf_preference_opt/run.py --stage reward_model
python experiments/04_rlhf_preference_opt/run.py --stage ppo
```

Trained adapters are published to HuggingFace Hub (`AfriMentor/chioma-*`) and
quantized to 4-bit/GGUF/AWQ for deployment per ADR-0002 Tier 2.

---

## Evaluation Metrics

All conditions are evaluated on the same 5-dimension rubric:

| Metric | Weight | Description |
|---|---|---|
| `persona_adherence` | 25% | Sounds like Chioma — direct, warm, specific |
| `cultural_fluency` | 20% | African financial realities, local context |
| `anti_dependency` | 20% | Teaches frameworks, not just answers |
| `financial_accuracy` | 20% | Factually correct financial advice |
| `urgency` | 15% | Surfaces cost of inaction in concrete terms |

Plus reference-based metrics (`rouge_l`, `bert_score_f1`) when reference responses are available.

Composite score = weighted sum of the 5 dimensions.

---

## Directory Structure

```
research/
  experiments/
    01_baseline_prompting/run.py      # C1 — no GPU
    02_supervised_finetuning/run.py   # C2 — GPU
    03_contrastive_learning/run.py    # C3 — GPU
    04_rlhf_preference_opt/run.py     # C4 — GPU
  datasets/
    raw/                              # DVC-tracked raw data
    processed/                        # DVC-tracked processed splits
    splits/                           # train/val/test splits
    scripts/                          # ingest, process, split
    dvc.yaml                          # DVC pipeline definition
  evaluation/
    metrics.py                        # shared eval harness (LLM-as-judge + ROUGE + BERTScore)
  tracking/
    setup_mlflow.py                   # registers all 4 experiments in MLflow
    mlflow.Dockerfile                 # MLflow server for docker-compose
  configs/
    dataset.yaml                      # split ratios, schema version
    c1_baseline_prompting.yaml
    c2_supervised_finetuning.yaml
    c3_contrastive_learning.yaml
    c4_rlhf_preference_opt.yaml
  notebooks/                          # EDA and result analysis
  requirements.txt                    # CPU deps
  requirements-gpu.txt                # GPU deps (install on cloud nodes only)
```
