"""Unit tests for _strip_think_tags — ensures Qwen reasoning blocks are never
surfaced to clients via either the non-streaming or streaming LLM path."""

from app.llm import _strip_think_tags


class TestStripThinkTags:
    def test_strips_think_block(self):
        raw = "<think>\nHere is my reasoning.\n</think>\nHello, user!"
        assert _strip_think_tags(raw) == "Hello, user!"

    def test_no_think_block_unchanged(self):
        text = "Hello, user!"
        assert _strip_think_tags(text) == text

    def test_case_insensitive(self):
        raw = "<THINK>secret</THINK>public reply"
        assert _strip_think_tags(raw) == "public reply"

    def test_multiline_think_block(self):
        raw = (
            "<think>\n"
            "Step 1: think hard.\n"
            "Step 2: think harder.\n"
            "</think>\n"
            "Here is your answer."
        )
        assert _strip_think_tags(raw) == "Here is your answer."

    def test_leading_newline_stripped(self):
        """After removing <think>…</think>, a leading newline is trimmed."""
        raw = "<think>thinking</think>\nActual reply"
        result = _strip_think_tags(raw)
        assert result == "Actual reply"
        assert not result.startswith("\n")

    def test_empty_think_block(self):
        raw = "<think></think>Reply"
        assert _strip_think_tags(raw) == "Reply"

    def test_only_think_block(self):
        """If the model only emits a think block and nothing else, return empty."""
        raw = "<think>reasoning only</think>"
        assert _strip_think_tags(raw) == ""

    def test_unclosed_think_block_truncated(self):
        """If max_tokens cuts off generation inside <think>, entire think block is stripped."""
        raw = "\n<think>\nHere is a thinking process:\n1. Step 1\nTruncated mid thought"
        assert _strip_think_tags(raw) == ""

    def test_stray_closing_tag(self):
        """Stray </think> without opening tag is removed."""
        raw = "</think>Actual answer here"
        assert _strip_think_tags(raw) == "Actual answer here"

