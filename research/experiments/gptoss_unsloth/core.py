"""Tokenisation/loss helpers for the Unsloth gpt-oss trainer. torch-free except where noted,
so the fiddly parts (prompt/response masking, LR schedule, DPO maths) are unit-testable offline."""
from __future__ import annotations

import math


def split_prompt_response(tok, prompt_messages: list[dict], response: str, max_len: int,
                          template_kwargs: dict | None = None) -> tuple[list[int], list[int]]:
    """Token ids for (prompt, response) such that loss can be taken on the response only.

    The prompt side is the chat template rendered with the generation prompt; the response
    side is whatever the template adds when the same assistant turn is appended (for gpt-oss
    that is ``<|channel|>final<|message|>...<|return|>``). Truncates the *prompt* from the
    left if the pair exceeds ``max_len`` so the response is never cut.
    """
    kw = template_kwargs or {}
    prompt_text = tok.apply_chat_template(prompt_messages, tokenize=False, add_generation_prompt=True, **kw)
    full_text = tok.apply_chat_template(prompt_messages + [{"role": "assistant", "content": response}],
                                        tokenize=False, add_generation_prompt=False, **kw)
    if full_text.startswith(prompt_text):
        response_text = full_text[len(prompt_text):]
    else:  # template re-renders earlier turns differently: split at the last assistant header
        marker = "<|start|>assistant"
        idx = full_text.rfind(marker)
        if idx < 0:
            raise ValueError("cannot locate the assistant turn in the rendered chat template")
        prompt_text, response_text = full_text[: idx + len(marker)], full_text[idx + len(marker):]
    p = tok(prompt_text, add_special_tokens=False)["input_ids"]
    r = tok(response_text, add_special_tokens=False)["input_ids"]
    if len(r) >= max_len:
        raise ValueError(f"response alone ({len(r)} tokens) exceeds max_len={max_len}")
    if len(p) + len(r) > max_len:
        p = p[len(p) + len(r) - max_len:]
    return p, r


def build_sft_example(tok, messages: list[dict], max_len: int, template_kwargs=None) -> dict:
    """``messages`` = [system?, user, assistant]; loss only on the final assistant turn."""
    p, r = split_prompt_response(tok, messages[:-1], messages[-1]["content"], max_len, template_kwargs)
    return {"input_ids": p + r, "labels": [-100] * len(p) + r}


def lr_at(step: int, total: int, base_lr: float, warmup_ratio: float = 0.05) -> float:
    """Linear warmup then cosine decay to 0."""
    warm = max(1, int(total * warmup_ratio))
    if step < warm:
        return base_lr * (step + 1) / warm
    prog = (step - warm) / max(1, total - warm)
    return 0.5 * base_lr * (1 + math.cos(math.pi * min(1.0, prog)))


def dpo_loss_value(pi_chosen: float, pi_rejected: float, ref_chosen: float, ref_rejected: float,
                   beta: float) -> tuple[float, float]:
    """Sigmoid DPO loss and the implicit-reward margin for one pair (plain floats)."""
    margin = beta * ((pi_chosen - pi_rejected) - (ref_chosen - ref_rejected))
    loss = math.log1p(math.exp(-margin)) if margin > -30 else -margin  # -log(sigmoid(margin))
    return loss, margin
