"""Why was the first SFT loss 15.7 (uniform-random over the vocab is ~12.2)? Measures the same
example four ways on the *un-trained* base model and prints per-token losses. ~2 minutes."""
import os

os.environ.setdefault("UNSLOTH_COMPILE_DISABLE", "1")
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
import json
import sys
from pathlib import Path

from unsloth import FastLanguageModel  # noqa: E402

import torch  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import core  # noqa: E402

REPO = HERE.parents[2]
model, tok = FastLanguageModel.from_pretrained("unsloth/gpt-oss-20b", max_seq_length=1536, load_in_4bit=True, dtype=None)
FastLanguageModel.for_inference(model)
row = json.loads((REPO / "research/datasets/splits/sft_train.jsonl").read_text().splitlines()[0])
ex = core.build_sft_example(tok, row["messages"], 1536, {"reasoning_effort": "low"})
ids = torch.tensor([ex["input_ids"]], device="cuda")
lab = torch.tensor([ex["labels"]], device="cuda")
mask = torch.ones_like(ids)
n_prompt = sum(l == -100 for l in ex["labels"])
print(f"tokens={ids.shape[1]} prompt={n_prompt} response={ids.shape[1]-n_prompt}", flush=True)


def manual(logits):
    lg = logits[0, n_prompt - 1:-1].float()
    tgt = ids[0, n_prompt:].to(lg.device)
    return torch.nn.functional.cross_entropy(lg, tgt, reduction="none")


with torch.no_grad():
    out_a = model(input_ids=ids, attention_mask=mask, labels=lab)
    out_b = model(input_ids=ids, labels=lab)
    out_c = model(input_ids=ids, attention_mask=mask)
per_tok = manual(out_c.logits)
print("A model.loss WITH attention_mask :", float(out_a.loss))
print("B model.loss NO attention_mask   :", float(out_b.loss))
print("C manual CE from logits (response tokens): mean", float(per_tok.mean()))
print("   first 8 token losses:", [round(float(x), 2) for x in per_tok[:8]])
print("   mean after first 8   :", float(per_tok[8:].mean()))
print("   logits finite:", bool(torch.isfinite(out_c.logits).all()), " dtype:", out_c.logits.dtype)
