"""Raw data ingestion script (DVC Stage 1).

Sources (Sprint 3+):
  - AfriMentor session logs from chat-orchestration-service (svc_chat DB)
  - Human-annotated preference pairs (Sprint 4-5)
  - Synthetic seed conversations for scaffold testing

Outputs:
  - research/datasets/raw/conversations.jsonl
  - research/datasets/raw/preference_pairs.jsonl

TODO Sprint 3: connect to svc_chat Postgres and export session logs.
TODO Sprint 4: add human annotation pipeline for preference pairs.
"""
from __future__ import annotations

import json
from pathlib import Path

RAW_DIR = Path("research/datasets/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


def ingest_synthetic_seed() -> None:
    """Write synthetic seed conversations for scaffold testing."""
    seed_conversations = [
        {
            "conversation_id": "seed-001",
            "persona_slug": "market-queen",
            "sector": "trader",
            "country": "NG",
            "messages": [
                {"role": "user", "content": "How do I start saving as a market trader in Lagos?"},
                {"role": "assistant", "content": "First, separate your trading capital from your personal money today — not tomorrow. Open a separate mobile money wallet just for business. Every evening, move 10% of your daily takings into it before you touch anything else. What is your average daily revenue right now?"},
            ],
            "quality_score": 0.9,
        },
        {
            "conversation_id": "seed-002",
            "persona_slug": "tech-founder",
            "sector": "tech",
            "country": "KE",
            "messages": [
                {"role": "user", "content": "I want to launch a fintech app in Nairobi. Where do I start?"},
                {"role": "assistant", "content": "Before you write a line of code, answer this: who is your first paying customer and what exact problem are you solving for them? Not a segment — one specific person. The Nairobi fintech space is crowded with solutions looking for problems. What pain have you personally watched someone suffer that you know how to fix?"},
            ],
            "quality_score": 0.92,
        },
    ]

    seed_pairs = [
        {
            "pair_id": "pair-001",
            "persona_slug": "market-queen",
            "prompt": "How do I price my goods when my supplier raises prices?",
            "chosen": "Raise your prices immediately — today, not next week. Every day you absorb the supplier increase is a day you are paying your customers' bills. Calculate your new landed cost, add your margin, and update your price board. Your loyal customers will understand. The ones who leave over a small price increase were never your real customers. What is your current margin on this product?",
            "rejected": "That's a tough situation. You might want to consider gradually increasing your prices over time so customers don't notice too much. It's important to stay competitive in the market.",
            "rejection_reason": "generic_response",
        },
    ]

    with open(RAW_DIR / "conversations.jsonl", "w") as f:
        for conv in seed_conversations:
            f.write(json.dumps(conv) + "\n")

    with open(RAW_DIR / "preference_pairs.jsonl", "w") as f:
        for pair in seed_pairs:
            f.write(json.dumps(pair) + "\n")

    print(f"Ingested {len(seed_conversations)} conversations, {len(seed_pairs)} preference pairs.")


if __name__ == "__main__":
    ingest_synthetic_seed()
