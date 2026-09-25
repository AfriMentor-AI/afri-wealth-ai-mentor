"""C2 (SFT), C3 (DPO) and C4 (probe-guided DPO) for gpt-oss-20b via Unsloth on Kaggle T4s.

Plain Hugging Face cannot hold gpt-oss-20b on a T4 (experts dequantise to ~40GB); Unsloth's loader
can, but TRL's trainers are then a version risk, so this uses a small explicit PyTorch loop.
Same YAML configs as the other models (configs/gptoss_20b/), same seeds, same dataset files.

    python research/experiments/gptoss_unsloth/train.py sft --config research/configs/gptoss_20b/c2_supervised_finetuning.yaml
    python research/experiments/gptoss_unsloth/train.py dpo --config research/configs/gptoss_20b/c3_contrastive_learning.yaml
    python research/experiments/gptoss_unsloth/train.py dpo --config research/configs/gptoss_20b/c4_rlhf_preference_opt.yaml --rlhf

C3/C4 warm-start from ``model.sft_checkpoint`` / ``model.prior_checkpoint`` (Hub repo or local dir).
Add ``--max-examples N --epochs 1`` for a quick timing run before the real one.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

from unsloth import FastLanguageModel  # noqa: I001 - import unsloth before transformers/peft

import torch
import yaml

_HERE = Path(__file__).resolve().parent
_RESEARCH = _HERE.parents[1]
for p in (str(_RESEARCH), str(_HERE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import core  # noqa: E402
from evaluation.checkpoint_eval import render_system_prompt  # noqa: E402

REPO_ROOT = _RESEARCH.parent
TEMPLATE_KW = {"reasoning_effort": "low"}


def _path(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else REPO_ROOT / q


def load_jsonl(path: Path, limit: int | None = None) -> list[dict]:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows[:limit] if limit else rows


def load_model(cfg: dict, adapter_ref: str | None, max_len: int):
    """Fresh LoRA on the base, or continue an existing adapter (Hub id / local dir)."""
    lora, seed = cfg["lora"], cfg["training"].get("seed", 42)
    if adapter_ref:
        model, tok = FastLanguageModel.from_pretrained(model_name=adapter_ref, max_seq_length=max_len,
                                                       load_in_4bit=True, dtype=None)
    else:
        model, tok = FastLanguageModel.from_pretrained(model_name=cfg["model"]["base_model_id"],
                                                       max_seq_length=max_len, load_in_4bit=True, dtype=None)
        model = FastLanguageModel.get_peft_model(
            model, r=lora["r"], lora_alpha=lora["lora_alpha"], lora_dropout=0,  # Unsloth's fast path needs 0
            target_modules=lora["target_modules"], use_gradient_checkpointing="unsloth", random_state=seed)
    n_train = sum(p.numel() for p in model.parameters() if p.requires_grad)
    if n_train == 0:
        raise RuntimeError("no trainable parameters — the adapter loaded frozen; cannot continue training")
    print(f"trainable params: {n_train:,}", flush=True)
    return model, tok


def _seq_logprob(model, ids: list[int], n_prompt: int) -> "torch.Tensor":
    """Sum of log-probs of the response tokens (positions >= n_prompt)."""
    x = torch.tensor([ids], device="cuda")
    logits = model(input_ids=x).logits[:, n_prompt - 1:-1].float()
    tgt = x[:, n_prompt:].to(logits.device)  # lm_head can sit on the 2nd GPU
    return torch.log_softmax(logits, -1).gather(-1, tgt.unsqueeze(-1)).squeeze(-1).sum()


def run_sft(cfg, args):
    tc = cfg["training"]
    max_len = min(tc.get("max_seq_length", 1536), 1536)
    model, tok = load_model(cfg, None, max_len)
    rows = load_jsonl(_path(args.dataset or tc["dataset"]), args.max_examples)
    data = [core.build_sft_example(tok, r["messages"], max_len, TEMPLATE_KW) for r in rows]
    print(f"SFT examples: {len(data)}  (avg len {sum(len(d['input_ids']) for d in data)/len(data):.0f})", flush=True)
    _loop(model, cfg, args, n_items=len(data), step_fn=lambda i: _sft_loss(model, data[i]))
    return model, tok


def _sft_loss(model, ex):
    x = torch.tensor([ex["input_ids"]], device="cuda")
    y = torch.tensor([ex["labels"]], device="cuda")
    return model(input_ids=x, labels=y).loss, {}


def run_dpo(cfg, args):
    tc, dc, mc = cfg["training"], cfg["dpo"], cfg["model"]
    max_len = min(dc.get("max_length", 1536), 1536)
    warm = mc.get("sft_checkpoint") if not args.rlhf else mc.get("prior_checkpoint")
    model, tok = load_model(cfg, warm, max_len)
    pairs = _load_pairs(cfg, args)
    items = []
    for pr in pairs[: args.max_examples] if args.max_examples else pairs:
        sysm = render_system_prompt(pr.get("persona_slug") or "chioma-base")
        pm = [{"role": "system", "content": sysm}, {"role": "user", "content": pr["prompt"]}]
        try:
            pc, rc = core.split_prompt_response(tok, pm, pr["chosen"], max_len, TEMPLATE_KW)
            pj, rj = core.split_prompt_response(tok, pm, pr["rejected"], max_len, TEMPLATE_KW)
        except ValueError as exc:
            print("skip pair:", exc)
            continue
        items.append({"c": (pc + rc, len(pc)), "r": (pj + rj, len(pj))})
    print(f"DPO pairs: {len(items)}; precomputing reference log-probs (frozen starting policy)...", flush=True)
    model.eval()
    with torch.no_grad():
        for it in items:
            it["ref_c"] = float(_seq_logprob(model, *it["c"]))
            it["ref_r"] = float(_seq_logprob(model, *it["r"]))
    FastLanguageModel.for_training(model)
    beta = dc.get("beta", 0.1)

    def step(i):
        it = items[i]
        pc, pr_ = _seq_logprob(model, *it["c"]), _seq_logprob(model, *it["r"])
        margin = beta * ((pc - pr_) - (it["ref_c"] - it["ref_r"]))
        return -torch.nn.functional.logsigmoid(margin), {"margin": float(margin), "acc": float(margin > 0)}

    _loop(model, cfg, args, n_items=len(items), step_fn=step)
    return model, tok


def _load_pairs(cfg, args) -> list[dict]:
    if not args.rlhf:
        return load_jsonl(_path(args.dataset or cfg["dpo"]["dataset"]))
    # C4: same probe-guided conversion as experiments/04_rlhf_preference_opt/run.py
    import pickle

    from evaluation.reward_model import load_preference_pairs, pairs_to_dpo_format

    rm = cfg["reward_model"]
    probe_path = _path(rm["probe_output"])
    probe = pickle.loads(probe_path.read_bytes()) if probe_path.exists() else None
    print(f"reward probe: {'loaded ' + str(probe_path) if probe else 'NOT FOUND — using dataset labels only'}")
    return pairs_to_dpo_format(load_preference_pairs(_path(rm["dataset"])), probe=probe,
                               reward_weights=rm.get("reward_weights"))


def _loop(model, cfg, args, n_items: int, step_fn):
    tc = cfg["training"]
    seed = tc.get("seed", 42)
    torch.manual_seed(seed)
    rng = random.Random(seed)
    epochs = args.epochs or tc["num_train_epochs"]
    accum = tc["per_device_train_batch_size"] * tc["gradient_accumulation_steps"]
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=tc["learning_rate"], weight_decay=0.0)
    total_steps = max(1, epochs * n_items // accum)
    step, seen, t0 = 0, 0, time.time()
    model.train()
    for ep in range(epochs):
        order = list(range(n_items))
        rng.shuffle(order)
        run_loss, run_n, extras = 0.0, 0, {}
        for k, i in enumerate(order, 1):
            loss, ex = step_fn(i)
            (loss / accum).backward()
            run_loss += float(loss.detach()); run_n += 1; seen += 1
            for kk, v in ex.items():
                extras[kk] = extras.get(kk, 0.0) + v
            if k % accum == 0 or k == n_items:
                for g in opt.param_groups:
                    g["lr"] = core.lr_at(step, total_steps, tc["learning_rate"], tc.get("warmup_ratio", 0.05))
                torch.nn.utils.clip_grad_norm_(params, 1.0)
                opt.step(); opt.zero_grad(set_to_none=True); step += 1
                eta = (time.time() - t0) / seen * (epochs * n_items - seen) / 60
                print(f"ep {ep+1}/{epochs} step {step}/{total_steps} loss {run_loss/run_n:.4f} "
                      + " ".join(f"{a} {b/run_n:.3f}" for a, b in extras.items()) + f"  eta {eta:.0f}m", flush=True)
                run_loss, run_n, extras = 0.0, 0, {}
    print(f"training done in {(time.time()-t0)/60:.1f} min", flush=True)


def save_and_push(model, tok, cfg, args):
    out = _path(cfg["model"]["output_dir"] + "/final")
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out))
    tok.save_pretrained(str(out))
    print(f"adapter saved locally: {out}", flush=True)
    repo = cfg["model"].get("hub_repo")
    if args.no_push or args.max_examples or not repo:
        print("NOT pushed (--no-push / --max-examples timing run / no hub_repo)")
        return
    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(repo, exist_ok=True)
    info = api.upload_folder(folder_path=str(out), repo_id=repo, commit_message=f"{cfg['experiment']['name']}")
    print(f"PUSHED to {repo}: {info}", flush=True)  # confirm this line BEFORE ending the session


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["sft", "dpo"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--rlhf", action="store_true", help="C4: warm-start from prior_checkpoint, use probe-guided pairs")
    ap.add_argument("--max-examples", type=int, default=None)
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--dataset", default=None, help="override the config's training jsonl (timing runs)")
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()
    cfg = yaml.safe_load(_path(args.config).read_text())
    model, tok = (run_sft if args.mode == "sft" else run_dpo)(cfg, args)
    save_and_push(model, tok, cfg, args)


if __name__ == "__main__":
    main()
