"""Second go/no-go for gpt-oss-20b: Unsloth's loader (the only route documented to fit ~14GB).

Plain transformers dequantizes the MoE experts to bf16 on a T4 (~40GB) and spills to CPU, so
gptoss_smoke_test.py fails at load. This checks whether Unsloth's patched loader fits, generates a
parseable harmony answer, and survives 5 LoRA optimizer steps. `import unsloth` must come first.

    pip install -q unsloth   # it manages its own transformers/trl pins
    python research/experiments/gptoss_unsloth_smoke_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from unsloth import FastLanguageModel  # noqa: I001 - must precede transformers imports

import torch

_RESEARCH_ROOT = Path(__file__).resolve().parents[1]
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

MODEL = "unsloth/gpt-oss-20b"  # Unsloth converts to its own memory-efficient 4-bit layout
results: list[tuple[str, bool, str]] = []


def stage(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}", flush=True)


def main() -> int:
    import transformers

    print(f"torch {torch.__version__} transformers {transformers.__version__} gpus={torch.cuda.device_count()}")
    try:
        model, tok = FastLanguageModel.from_pretrained(
            model_name=MODEL, max_seq_length=1024, load_in_4bit=True, dtype=None)
        used = max(torch.cuda.memory_allocated(i) for i in range(torch.cuda.device_count())) / 2**30
        stage("unsloth load", True, f"max/GPU {used:.1f} GiB")
    except Exception as exc:  # noqa: BLE001
        stage("unsloth load", False, repr(exc)[:400])
        return 1

    from evaluation.checkpoint_eval import extract_final_response

    msgs = [{"role": "system", "content": "You are Chioma, a direct, warm business mentor."},
            {"role": "user", "content": "My supplier raised prices 15%. What do I do with my prices?"}]
    try:
        FastLanguageModel.for_inference(model)
        enc = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt",
                                      return_dict=True, reasoning_effort="low").to("cuda")
        n_prompt = enc["input_ids"].shape[-1]
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=1024, do_sample=False)
        text, truncated = extract_final_response(tok.decode(out[0][n_prompt:], skip_special_tokens=False))
        stage("generate + parse final channel", bool(text) and not truncated,
              f"truncated={truncated} answer[:120]={text[:120]!r}")
    except Exception as exc:  # noqa: BLE001
        stage("generate + parse final channel", False, repr(exc)[:400])

    try:
        model = FastLanguageModel.get_peft_model(
            model, r=16, lora_alpha=32, lora_dropout=0,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            use_gradient_checkpointing="unsloth", random_state=42)
        FastLanguageModel.for_training(model)
        opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)
        batch = tok.apply_chat_template(
            msgs + [{"role": "assistant", "content": "Raise them today; recompute your margin first."}],
            return_tensors="pt", return_dict=True).to("cuda")
        losses = []
        for _ in range(5):
            loss = model(**batch, labels=batch["input_ids"]).loss
            loss.backward()
            opt.step()
            opt.zero_grad()
            losses.append(float(loss))
        peak = max(torch.cuda.max_memory_allocated(i) for i in range(torch.cuda.device_count())) / 2**30
        stage("LoRA 5 training steps", all(l == l and abs(l) < 1e6 for l in losses),
              f"losses={[round(l, 3) for l in losses]} peak/GPU={peak:.1f} GiB")
    except Exception as exc:  # noqa: BLE001
        stage("LoRA 5 training steps", False, repr(exc)[:400])

    print("\n=== SUMMARY ===")
    for n, ok, _ in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {n}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
