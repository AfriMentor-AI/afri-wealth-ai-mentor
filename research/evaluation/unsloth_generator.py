"""Generation for gpt-oss adapters via Unsloth (plain HF cannot load gpt-oss-20b on a T4).
Drop-in for HFCheckpointGenerator: __call__(system_prompt, user_message) -> final-channel text;
``last_truncated`` is set when the reasoning channel used the whole token budget."""
from __future__ import annotations

from evaluation.checkpoint_eval import extract_final_response


class UnslothCheckpointGenerator:
    def __init__(self, base_model_id: str, adapter_path: str | None = None, *,
                 max_new_tokens: int = 1536, temperature: float = 0.0, **_ignored) -> None:
        self.model_ref = adapter_path or base_model_id
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.last_truncated = False
        self.n_truncated = 0
        self._model = self._tok = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        from unsloth import FastLanguageModel

        self._model, self._tok = FastLanguageModel.from_pretrained(
            model_name=self.model_ref, max_seq_length=2048, load_in_4bit=True, dtype=None)
        FastLanguageModel.for_inference(self._model)

    def __call__(self, system_prompt: str, user_message: str) -> str:
        import torch

        self._ensure_loaded()
        msgs = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]
        enc = self._tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt",
                                            return_dict=True, reasoning_effort="low").to("cuda")
        n = enc["input_ids"].shape[-1]
        with torch.no_grad():
            out = self._model.generate(**enc, max_new_tokens=self.max_new_tokens,
                                       do_sample=self.temperature > 0,
                                       **({"temperature": self.temperature} if self.temperature > 0 else {}))
        text, self.last_truncated = extract_final_response(self._tok.decode(out[0][n:], skip_special_tokens=False))
        self.n_truncated += int(self.last_truncated)
        return text
