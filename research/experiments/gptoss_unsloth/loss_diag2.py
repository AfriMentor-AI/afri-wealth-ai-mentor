"""Does the forward pass break when the sequence exceeds gpt-oss's 128-token sliding window?
Teacher-forced next-token loss on prefixes of one real example, by length, plus a long-prompt
generation check.  Usage: loss_diag2.py [--attn eager|sdpa]  (default: whatever Unsloth picks)"""
import os
import sys

os.environ.setdefault("UNSLOTH_COMPILE_DISABLE", "1")
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
import json
from pathlib import Path

from unsloth import FastLanguageModel  # noqa: E402

import torch  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import core  # noqa: E402

attn = sys.argv[sys.argv.index("--attn") + 1] if "--attn" in sys.argv else None
kw = {"attn_implementation": attn} if attn else {}
print("attn_implementation:", attn or "(unsloth default)", flush=True)
model, tok = FastLanguageModel.from_pretrained("unsloth/gpt-oss-20b", max_seq_length=1536,
                                               load_in_4bit=True, dtype=None, **kw)
FastLanguageModel.for_inference(model)
row = json.loads((HERE.parents[2] / "research/datasets/splits/sft_train.jsonl").read_text().splitlines()[0])
ex = core.build_sft_example(tok, row["messages"], 1536, {"reasoning_effort": "low"})
ids = torch.tensor([ex["input_ids"]], device="cuda")

with torch.no_grad():
    for L in (48, 96, 128, 160, 224, 320, ids.shape[1]):
        x = ids[:, :L]
        lg = model(input_ids=x).logits[0, :-1].float()
        ce = torch.nn.functional.cross_entropy(lg, x[0, 1:].to(lg.device), reduction="none")
        tail = ce[min(40, len(ce) - 1):]  # skip the first tokens (system prompt is not predictable)
        print(f"L={L:4d}  mean loss all={float(ce.mean()):6.2f}  last-half={float(ce[len(ce)//2:].mean()):6.2f}", flush=True)

    enc = tok.apply_chat_template(row["messages"][:-1], add_generation_prompt=True, return_tensors="pt",
                                  return_dict=True, reasoning_effort="low").to("cuda")
    out = model.generate(**enc, max_new_tokens=80, do_sample=False)
    print("prompt tokens:", enc["input_ids"].shape[-1])
    print("generated:", repr(tok.decode(out[0][enc["input_ids"].shape[-1]:], skip_special_tokens=False)[:300]))
