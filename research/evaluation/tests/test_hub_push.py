"""Adapter push must never raise and must be skippable."""
from unittest.mock import MagicMock, patch

from evaluation.hub_push import push_adapter


def test_skips_when_no_repo_or_disabled(monkeypatch):
    assert push_adapter("/x", None, "m") is None
    monkeypatch.setenv("HUB_PUSH", "0")
    assert push_adapter("/x", "org/repo", "m") is None


def test_uploads_and_returns_commit_url(monkeypatch, capsys):
    monkeypatch.delenv("HUB_PUSH", raising=False)
    api = MagicMock()
    api.upload_folder.return_value = MagicMock(commit_url="https://hf.co/org/repo/commit/abc")
    with patch("huggingface_hub.HfApi", return_value=api):
        url = push_adapter("/adapter", "org/repo", "msg")
    assert url == "https://hf.co/org/repo/commit/abc"
    api.create_repo.assert_called_once_with("org/repo", exist_ok=True)
    assert "PUSHED org/repo" in capsys.readouterr().out


def test_failure_is_reported_loudly_but_does_not_raise(monkeypatch, capsys):
    monkeypatch.delenv("HUB_PUSH", raising=False)
    api = MagicMock()
    api.upload_folder.side_effect = RuntimeError("401")
    with patch("huggingface_hub.HfApi", return_value=api):
        assert push_adapter("/adapter", "org/repo", "msg") is None
    assert "HUB PUSH FAILED" in capsys.readouterr().out
