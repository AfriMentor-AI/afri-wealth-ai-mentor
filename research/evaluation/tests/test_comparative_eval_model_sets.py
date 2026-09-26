"""Model-set plumbing: C1 must be the same base model as C2-C4 for non-Qwen sets."""
from evaluation import comparative_eval as ce


def _fake_condition(calls):
    def fake(condition_id, base, adapter, samples, **kw):
        calls.append((condition_id, base, adapter))
        return [{"composite_score": 0.5, "persona_adherence": 0.5, "persona": "chioma-base",
                 "user_message": "q", "response": "r", "generation_truncated": 0}]
    return fake


def test_llama_c1_runs_the_local_base_model_without_an_adapter(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(ce, "_run_checkpoint_condition", _fake_condition(calls))
    out = ce.run(2, tmp_path / "o.json", run_c2=False, run_c3=False, run_c4=False,
                 model_set="llama31_8b", splits_dir=tmp_path)
    assert calls == [("C1", "meta-llama/Llama-3.1-8B-Instruct", None)]
    assert out["conditions"]["C1"]["aggregate"]["source"] == "live_hf_base"
    assert out["meta"]["model_set"] == "llama31_8b"


def test_adapters_are_loaded_on_the_matching_base(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(ce, "_run_checkpoint_condition", _fake_condition(calls))
    ce.run(2, tmp_path / "o.json", run_c1=False, model_set="llama31_8b", splits_dir=tmp_path)
    assert [c[0] for c in calls] == ["C2", "C3", "C4"]
    assert {c[1] for c in calls} == {"meta-llama/Llama-3.1-8B-Instruct"}
    assert calls[1][2] == "AfriMentor/chioma-llama31-8b-dpo-v2"
