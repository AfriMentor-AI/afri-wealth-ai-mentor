"""Push a trained adapter to the Hugging Face Hub *immediately after it is saved*.

Lost-checkpoint history: a Kaggle session ended before a manual push happened and the trained C4 adapter
was gone. Training scripts now call this right after ``save_model`` — before any evaluation step that could
crash — and print the commit so the push can be confirmed from the log. Disable with ``HUB_PUSH=0``.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def push_adapter(adapter_dir: str, repo_id: str | None, message: str) -> str | None:
    """Upload ``adapter_dir`` to ``repo_id``. Returns the commit url, or None when skipped or failed.
    Never raises: a failed push must not discard a finished training run (the adapter is still on disk)."""
    if not repo_id or os.getenv("HUB_PUSH", "1") == "0":
        logger.warning("Hub push skipped (repo=%r, HUB_PUSH=%s)", repo_id, os.getenv("HUB_PUSH", "1"))
        return None
    try:
        from huggingface_hub import HfApi

        api = HfApi()
        api.create_repo(repo_id, exist_ok=True)
        info = api.upload_folder(folder_path=adapter_dir, repo_id=repo_id, commit_message=message)
        url = getattr(info, "commit_url", str(info))
        print(f"PUSHED {repo_id}: {url}", flush=True)
        return url
    except Exception as exc:  # noqa: BLE001
        print(f"!!! HUB PUSH FAILED for {repo_id}: {exc!r}\n!!! adapter is still on disk at {adapter_dir} — "
              f"push it manually before ending the session", flush=True)
        return None
