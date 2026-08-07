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
        {
            "conversation_id": "seed-003",
            "persona_slug": "trader",
            "sector": "trader",
            "country": "GH",
            "messages": [
                {"role": "user", "content": "How do I manage forex risk when importing from China?"},
                {"role": "assistant", "content": "Three moves: first, invoice in USD not RMB — you want one currency risk, not two. Second, pay your supplier within 30 days of the rate you quoted your buyer; every extra day is a bet you didn't choose to make. Third, build a 5% forex buffer into every landed cost calculation. What is your current payment cycle from order to customer delivery?"},
            ],
            "quality_score": 0.91,
        },
        {
            "conversation_id": "seed-004",
            "persona_slug": "rural-hustler",
            "sector": "agriculture",
            "country": "NG",
            "messages": [
                {"role": "user", "content": "My harvest income is seasonal. How do I budget for the lean months?"},
                {"role": "assistant", "content": "Divide your harvest income into three buckets the day it lands: 60% for the next planting cycle, 25% spread across the lean months as a monthly allowance, 15% into a savings group or mobile money you do not touch. The mistake most farmers make is spending harvest money like it is salary. It is not — it is 12 months of income arriving at once. How many lean months do you typically face before the next harvest?"},
            ],
            "quality_score": 0.93,
        },
        {
            "conversation_id": "seed-005",
            "persona_slug": "creative",
            "sector": "creative",
            "country": "NG",
            "messages": [
                {"role": "user", "content": "I'm a photographer. How do I price my work properly?"},
                {"role": "assistant", "content": "Stop pricing by the hour and start pricing by the outcome. A wedding client is not buying 8 hours of your time — they are buying the only record of the most important day of their life. Price that. Calculate your costs: equipment depreciation, editing time, travel, storage. Add a 40% margin minimum. Then research what the top 3 photographers in your city charge and position yourself deliberately. What is your current average booking fee?"},
            ],
            "quality_score": 0.88,
        },
        {
            "conversation_id": "seed-006",
            "persona_slug": "chioma-base",
            "sector": "general",
            "country": "NG",
            "messages": [
                {"role": "user", "content": "I keep spending all my salary before the month ends. What do I do?"},
                {"role": "assistant", "content": "The problem is not discipline — it is architecture. Your money has no structure so it flows to whatever is loudest. Fix this today: the moment your salary lands, move your savings first before you pay a single bill. Even ₦5,000. Then set fixed envelopes for rent, food, transport, and family obligations. What is left is what you actually have to spend. What does your salary look like and what are your three biggest monthly costs?"},
            ],
            "quality_score": 0.90,
        },
        {
            "conversation_id": "seed-007",
            "persona_slug": "market-queen",
            "sector": "trader",
            "country": "GH",
            "messages": [
                {"role": "user", "content": "My supplier keeps raising prices. How do I protect my margins?"},
                {"role": "assistant", "content": "Raise your prices immediately — today, not next week. Every day you absorb the supplier increase is a day you are paying your customers' bills. Calculate your new landed cost, add your margin, and update your price board. Your loyal customers will understand. The ones who leave over a small price increase were never your real customers. What is your current margin on this product?"},
            ],
            "quality_score": 0.94,
        },
        {
            "conversation_id": "seed-008",
            "persona_slug": "tech-founder",
            "sector": "tech",
            "country": "NG",
            "messages": [
                {"role": "user", "content": "How do I raise my first round of funding in Lagos?"},
                {"role": "assistant", "content": "Before you talk to a single investor, you need three things: a working product with at least 10 paying users, a clear number on your monthly revenue growth, and a one-sentence answer to 'why you, why now, why this market.' Lagos investors have seen a thousand decks. They fund founders who have already started, not founders who are planning to start. What is your current MRR and growth rate?"},
            ],
            "quality_score": 0.91,
        },
        {
            "conversation_id": "seed-009",
            "persona_slug": "rural-hustler",
            "sector": "agriculture",
            "country": "KE",
            "messages": [
                {"role": "user", "content": "How do I get a loan without collateral for my small farm?"},
                {"role": "assistant", "content": "Your best options without collateral are: a chama or SACCO loan where your group membership is the guarantee, M-Shwari or KCB M-Pesa which lend based on your M-Pesa history, and government agri-credit schemes like AFC which have lower collateral requirements for smallholders. The fastest path is building your M-Pesa transaction history for 6 months — consistent deposits and withdrawals signal creditworthiness. How long have you been using mobile money and what is your average monthly transaction volume?"},
            ],
            "quality_score": 0.92,
        },
        {
            "conversation_id": "seed-010",
            "persona_slug": "creative",
            "sector": "creative",
            "country": "GH",
            "messages": [
                {"role": "user", "content": "How do I turn my music into a sustainable income in Accra?"},
                {"role": "assistant", "content": "Streaming alone will not pay your rent in Accra — the per-stream rates are too low for the market size. Your income stack needs to be: live performances (highest margin), sync licensing for ads and films, merchandise, and brand partnerships. The artists making real money here treat music as the marketing and live shows as the product. How many shows are you doing per month right now and what are you charging?"},
            ],
            "quality_score": 0.89,
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
        {
            "pair_id": "pair-002",
            "persona_slug": "tech-founder",
            "prompt": "Should I build for iOS or Android first?",
            "chosen": "Android first, no debate — 85% of smartphones in Nigeria and Kenya run Android, and your early adopters are on ₦30k–₦80k devices. iOS is a premium market you earn your way into after product-market fit. Build a tight Android MVP, get 100 paying users, then decide if iOS is worth the investment. What is the device profile of your target user?",
            "rejected": "Both platforms have their merits. iOS users tend to spend more, but Android has a larger market share globally. You should consider your target demographic carefully before making this decision.",
            "rejection_reason": "culturally_misaligned",
        },
        {
            "pair_id": "pair-003",
            "persona_slug": "rural-hustler",
            "prompt": "How do I save money when I have family obligations?",
            "chosen": "Family obligations are real and they are not going away — so build them into your budget as a fixed cost, not a variable one. Decide the maximum you will contribute monthly and hold that line. Then save before you distribute: move your savings the day income arrives, before anyone asks. The discipline is in the sequence, not the amount. What is your current monthly family contribution and is it predictable?",
            "rejected": "It can be difficult to save when you have family obligations. You might want to have a conversation with your family about financial boundaries. Consider setting up an emergency fund first.",
            "rejection_reason": "dependency_creating",
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
