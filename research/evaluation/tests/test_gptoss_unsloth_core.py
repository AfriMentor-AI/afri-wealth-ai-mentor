"""Offline tests for the Unsloth gpt-oss trainer's pure helpers (fake tokenizer, no GPU)."""
import importlib.util
import math
from pathlib import Path

import pytest

_P = Path(__file__).resolve().parents[2] / "experiments" / "gptoss_unsloth" / "core.py"
_s = importlib.util.spec_from_file_location("gptoss_core", _P)
core = importlib.util.module_from_spec(_s)
_s.loader.exec_module(core)


class FakeTok:
    """Renders like harmony: turns as <|start|>role<|message|>text<|end|>; the final
    assistant answer goes through the final channel."""
    def apply_chat_template(self, msgs, tokenize=False, add_generation_prompt=False, **kw):
        out = ""
        for m in msgs:
            if m["role"] == "assistant":
                out += f"<|start|>assistant<|channel|>final<|message|>{m['content']}<|return|>"
            else:
                out += f"<|start|>{m['role']}<|message|>{m['content']}<|end|>"
        if add_generation_prompt:
            out += "<|start|>assistant"
        return out

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": [ord(c) for c in text]}


MSGS = [{"role": "system", "content": "S"}, {"role": "user", "content": "Q"}, {"role": "assistant", "content": "ANSWER"}]


def test_labels_mask_prompt_and_train_on_the_answer_only():
    ex = core.build_sft_example(FakeTok(), MSGS, max_len=500)
    trained = "".join(chr(t) for t in ex["labels"] if t != -100)
    assert "ANSWER" in trained and "<|return|>" in trained
    assert "Q" not in trained and "<|start|>system" not in trained
    assert len(ex["input_ids"]) == len(ex["labels"])


def test_overlong_prompt_is_trimmed_from_the_left_never_the_response():
    long_msgs = [{"role": "user", "content": "x" * 400}, {"role": "assistant", "content": "ANSWER"}]
    ex = core.build_sft_example(FakeTok(), long_msgs, max_len=120)
    assert len(ex["input_ids"]) == 120
    assert "ANSWER" in "".join(chr(t) for t in ex["labels"] if t != -100)


def test_response_longer_than_budget_raises():
    with pytest.raises(ValueError):
        core.build_sft_example(FakeTok(), [{"role": "user", "content": "q"}, {"role": "assistant", "content": "y" * 300}], 100)


def test_lr_schedule_warms_up_then_decays():
    lrs = [core.lr_at(i, 100, 1.0) for i in range(100)]
    assert lrs[0] < lrs[4] and max(lrs) == pytest.approx(1.0, abs=0.05)
    assert lrs[-1] < 0.01 and lrs[50] > lrs[90]


def test_dpo_loss_is_log2_at_zero_margin_and_falls_as_chosen_improves():
    l0, m0 = core.dpo_loss_value(-10, -10, -10, -10, 0.1)
    assert m0 == 0 and l0 == pytest.approx(math.log(2))
    l1, m1 = core.dpo_loss_value(-5, -15, -10, -10, 0.1)
    assert m1 > 0 and l1 < l0
    assert core.dpo_loss_value(-15, -5, -10, -10, 0.1)[0] > l0
