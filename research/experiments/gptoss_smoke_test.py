"""Go/no-go check for gpt-oss-20b on a Kaggle T4 BEFORE spending GPU time on C2-C4.

Verifies, in order: GPU + library versions; the pre-quantized 4-bit model loads within
VRAM; generation works and the harmony 'final' channel parses; a LoRA adapter takes 5
optimizer steps with a finite loss. Plain PEFT loop (no TRL) so a trl API change cannot
mask a real memory/compat problem. Prints PASS/FAIL per stage; exit code 1 on any FAIL.

    python research/experiments/gptoss_smoke_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_RESEARCH_ROOT = Path(__file__).resolve().parents[1]
if str(_RESEARCH_ROOT) not in sys.path:
    sys.path.insert(0, str(_RESEARCH_ROOT))

MODEL = "unsloth/gpt-oss-20b-unsloth-bnb-4bit"
results: list[tuple[str, bool, str]] = []


def stage(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}", flush=True)


def main() -> int:
    import torch
    import transformers

    stage("gpu present", torch.cuda.is_available(),
          f"{torch.cuda.device_count()}x {torch.cuda.get_device_name(0) if torch.cuda.is_available() else '-'}")
    print(f"torch {torch.__version__}  transformers {transformers.__version__}")
    if not torch.cuda.is_available():
        return 1

    from transformers import AutoModelForCausalLM, AutoTokenizer

    try:
        tok = AutoTokenizer.from_pretrained(MODEL)
        model = AutoModelForCausalLM.from_pretrained(MODEL, device_map="auto")
        used = sum(torch.cuda.memory_allocated(i) for i in range(torch.cuda.device_count())) / 2**30
        stage("load 4-bit model", True, f"{used:.1f} GiB allocated")
    except Exception as exc:  # noqa: BLE001
        stage("load 4-bit model", False, repr(exc)[:300])
        return 1

    from evaluation.checkpoint_eval import extract_final_response

    try:
        msgs = [{"role": "system", "content": "You are Chioma, a direct, warm business mentor."},
                {"role": "user", "content": "My supplier raised prices 15%. What do I do with my prices?"}]
        enc = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt",
                                      return_dict=True, reasoning_effort="low").to(model.device)
        n_prompt = enc["input_ids"].shape[-1]
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=1024, do_sample=False)
        raw = tok.decode(out[0][n_prompt:], skip_special_tokens=False)
        text, truncated = extract_final_response(raw)
        stage("generate + parse final channel", bool(text) and not truncated,
              f"truncated={truncated} answer[:120]={text[:120]!r}")
    except Exception as exc:  # noqa: BLE001
        stage("generate + parse final channel", False, repr(exc)[:300])

    try:
        from peft import LoraConfig, get_peft_model

        model.config.use_cache = False
        peft_model = get_peft_model(model, LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.05, target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            task_type="CAUSAL_LM"))
        peft_model.print_trainable_parameters()
        opt = torch.optim.AdamW([p for p in peft_model.parameters() if p.requires_grad], lr=1e-4)
        batch = tok.apply_chat_template(
            msgs + [{"role": "assistant", "content": "Raise them today; recompute your margin first."}],
            return_tensors="pt", return_dict=True).to(peft_model.device)
        losses = []
        peft_model.train()
        for _ in range(5):
            loss = peft_model(**batch, labels=batch["input_ids"]).loss
            loss.backward()
            opt.step()
            opt.zero_grad()
            losses.append(float(loss))
        peak = max(torch.cuda.max_memory_allocated(i) for i in range(torch.cuda.device_count())) / 2**30
        finite = all(l == l and abs(l) < 1e6 for l in losses)
        stage("LoRA 5 training steps", finite, f"losses={[round(l, 3) for l in losses]} peak/GPU={peak:.1f} GiB")
    except Exception as exc:  # noqa: BLE001
        stage("LoRA 5 training steps", False, repr(exc)[:300])

    print("\n=== SUMMARY ===")
    for n, ok, _ in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {n}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
