"""gpt-oss 'harmony' decoding: score the final answer, never the reasoning trace."""
from evaluation.checkpoint_eval import extract_final_response


def test_extracts_final_channel_and_drops_analysis():
    raw = ("<|channel|>analysis<|message|>User asks about pricing; think step by step...<|end|>"
           "<|start|>assistant<|channel|>final<|message|>Raise prices today. What is your margin?<|return|>")
    assert extract_final_response(raw) == ("Raise prices today. What is your margin?", False)


def test_reports_truncation_when_final_channel_never_starts():
    raw = "<|channel|>analysis<|message|>Let me think about this at great length and never finish"
    assert extract_final_response(raw) == ("", True)


def test_plain_text_passes_through_for_non_harmony_models():
    assert extract_final_response("  Just an answer.  ") == ("Just an answer.", False)


def test_only_the_last_final_block_is_used():
    raw = ("<|channel|>final<|message|>draft<|end|><|start|>assistant"
           "<|channel|>final<|message|>real answer<|return|>")
    assert extract_final_response(raw)[0] == "real answer"
