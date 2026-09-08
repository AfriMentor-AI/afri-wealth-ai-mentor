"""Idempotent catalog seed (card O3.2) — sample items covering text, audio, and
video across multiple languages and difficulty levels. Runs once at startup."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import InsightItem

SEED_ITEMS = [
    # ── Text ──────────────────────────────────────────────────────────────────
    {
        "title": "How to price your trade",
        "summary": "A practical framework for setting prices that cover costs and leave room for profit.",
        "category": "Pricing",
        "media_type": "text",
        "duration_seconds": 360,
        "language": "en",
        "difficulty": "beginner",
    },
    {
        "title": "Bookkeeping with Mobile Money",
        "summary": "Turning your mobile money statement into a simple daily ledger.",
        "category": "Bookkeeping",
        "media_type": "text",
        "duration_seconds": 300,
        "language": "en",
        "difficulty": "beginner",
    },
    {
        "title": "Reading your first loan agreement",
        "summary": "The clauses that matter most before you sign.",
        "category": "Finance",
        "media_type": "text",
        "duration_seconds": 540,
        "language": "en",
        "difficulty": "intermediate",
    },
    {
        "title": "Jinsi ya kuweka akiba wakati wa kiangazi",
        "summary": "Kujenga akiba kabla ya miezi ngumu na kuinyoosha inapofika.",
        "category": "Savings",
        "media_type": "text",
        "duration_seconds": 420,
        "language": "sw",
        "difficulty": "beginner",
    },
    # ── Audio ─────────────────────────────────────────────────────────────────
    {
        "title": "Saving during lean seasons",
        "summary": "Building a buffer before the slow months hit, and stretching it once they do.",
        "category": "Savings",
        "media_type": "audio",
        "duration_seconds": 480,
        "language": "en",
        "difficulty": "beginner",
        "transcript_url": "/media/transcripts/saving-lean-seasons-en.txt",
    },
    {
        "title": "Negotiating with suppliers",
        "summary": "Getting better terms without burning the relationship.",
        "category": "Operations",
        "media_type": "audio",
        "duration_seconds": 420,
        "language": "en",
        "difficulty": "intermediate",
        "transcript_url": "/media/transcripts/negotiating-suppliers-en.txt",
    },
    {
        "title": "Ètò owó fún àwọn oníṣòwò kéékèèké",
        "summary": "Bí a ṣe lè tọ́jú owó iṣowo kí o má bàa papọ̀ mọ́ owó ilé.",
        "category": "Bookkeeping",
        "media_type": "audio",
        "duration_seconds": 390,
        "language": "yo",
        "difficulty": "beginner",
        "transcript_url": "/media/transcripts/bookkeeping-yo.txt",
    },
    {
        "title": "How to build an emergency fund on irregular income",
        "summary": "Practical steps for traders and gig workers with unpredictable cash flow.",
        "category": "Savings",
        "media_type": "audio",
        "duration_seconds": 900,
        "language": "en",
        "difficulty": "intermediate",
        "transcript_url": "/media/transcripts/emergency-fund-irregular-income-en.txt",
    },
    # ── Video ─────────────────────────────────────────────────────────────────
    {
        "title": "Setting up a simple cash-flow tracker",
        "summary": "A 10-minute walkthrough using a free spreadsheet template.",
        "category": "Bookkeeping",
        "media_type": "video",
        "duration_seconds": 600,
        "language": "en",
        "difficulty": "beginner",
        "thumbnail_url": "/media/thumbnails/cashflow-tracker.jpg",
        "transcript_url": "/media/transcripts/cashflow-tracker-en.txt",
    },
    {
        "title": "Understanding interest rates",
        "summary": "Simple vs compound interest explained with real market examples.",
        "category": "Finance",
        "media_type": "video",
        "duration_seconds": 780,
        "language": "en",
        "difficulty": "intermediate",
        "thumbnail_url": "/media/thumbnails/interest-rates.jpg",
        "transcript_url": "/media/transcripts/interest-rates-en.txt",
    },
    {
        "title": "Comment fixer le prix de vos produits",
        "summary": "Méthode pas-à-pas pour calculer un prix de vente rentable.",
        "category": "Pricing",
        "media_type": "video",
        "duration_seconds": 660,
        "language": "fr",
        "difficulty": "beginner",
        "thumbnail_url": "/media/thumbnails/pricing-fr.jpg",
        "transcript_url": "/media/transcripts/pricing-fr.txt",
    },
    {
        "title": "Advanced inventory management for growing traders",
        "summary": "FIFO, reorder points, and supplier lead times without expensive software.",
        "category": "Operations",
        "media_type": "video",
        "duration_seconds": 1200,
        "language": "en",
        "difficulty": "advanced",
        "thumbnail_url": "/media/thumbnails/inventory-advanced.jpg",
        "transcript_url": "/media/transcripts/inventory-advanced-en.txt",
    },
]


def seed_if_empty(db: Session) -> None:
    if db.query(InsightItem).first() is not None:
        return
    for item in SEED_ITEMS:
        db.add(InsightItem(**item))
    db.commit()
