"""Catch a collapsed adapter *before* it is published or scored.

The first Llama C4 (DPO stacked on an already-saturated C3) degenerated into "friend friend friend ..." and was
pushed to the Hub as if it were a result. After training, a few answers are generated on held-out *validation*
prompts (never the test set) and checked for the signatures of collapse: a word repeated many times in a row,
a generation that never stops, empty output. If too many fail, the push is skipped.
"""
from __future__ import annotations

import re

_REPEAT = re.compile(r"\b(\w+)(\s+\1\b){5,}", re.IGNORECASE)   # same word 6+ times in a row


def is_degenerate(text: str, token_cap_words: int = 450) -> tuple[bool, str]:
    t = (text or "").strip()
    if not t:
        return True, "empty"
    if _REPEAT.search(t):
        return True, "repeated word run"
    words = t.split()
    if len(words) >= token_cap_words:
        return True, "ran to the length cap"
    if len(words) > 40 and len(set(w.lower() for w in words)) / len(words) < 0.25:
        return True, "very low lexical diversity"
    return False, ""


def health_report(texts: list[str], max_bad_fraction: float = 0.2) -> dict:
    flags = [is_degenerate(t) for t in texts]
    bad = [reason for is_bad, reason in flags if is_bad]
    frac = len(bad) / len(texts) if texts else 1.0
    return {"n": len(texts), "n_degenerate": len(bad), "bad_fraction": frac,
            "reasons": sorted(set(bad)), "healthy": bool(texts) and frac <= max_bad_fraction}


def sample_validation_responses(model, tokenizer, prompts_with_persona: list[tuple[str, str]],
                                max_new_tokens: int = 400) -> list[str]:
    """Greedy answers from a freshly trained (PEFT) model. GPU-only helper; the logic above is unit-tested."""
    import torch

    from evaluation.checkpoint_eval import render_system_prompt

    was_training = model.training
    model.eval()
    out = []
    for persona, user in prompts_with_persona:
        msgs = [{"role": "system", "content": render_system_prompt(persona)}, {"role": "user", "content": user}]
        enc = tokenizer.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt",
                                            return_dict=True).to(model.device)
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False,
                                 pad_token_id=tokenizer.pad_token_id)
        out.append(tokenizer.decode(gen[0][enc["input_ids"].shape[-1]:], skip_special_tokens=True))
    if was_training:
        model.train()
    return out
