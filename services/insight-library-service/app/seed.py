"""Idempotent catalog seed (card O3.2) — sample items matching the Insight
Library Home/Desktop screens, so search/filter have real data to return before
a real content-authoring workflow exists. Runs once at startup; no-ops if the
catalog already has rows."""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import InsightItem

SEED_ITEMS = [
    {
        "title": "How to price your trade",
        "summary": "A practical framework for setting prices that cover costs and leave room "
        "for profit.",
        "category": "Pricing",
        "duration_minutes": 6,
        "is_audio": False,
    },
    {
        "title": "Saving during lean seasons",
        "summary": "Building a buffer before the slow months hit, and stretching it once they do.",
        "category": "Savings",
        "duration_minutes": 8,
        "is_audio": True,
    },
    {
        "title": "Bookkeeping with Mobile Money",
        "summary": "Turning your mobile money statement into a simple daily ledger.",
        "category": "Bookkeeping",
        "duration_minutes": 5,
        "is_audio": False,
    },
    {
        "title": "Negotiating with suppliers",
        "summary": "Getting better terms without burning the relationship.",
        "category": "Operations",
        "duration_minutes": 7,
        "is_audio": True,
    },
    {
        "title": "Reading your first loan agreement",
        "summary": "The clauses that matter most before you sign.",
        "category": "Finance",
        "duration_minutes": 9,
        "is_audio": False,
    },
]


def seed_if_empty(db: Session) -> None:
    if db.query(InsightItem).first() is not None:
        return
    for item in SEED_ITEMS:
        db.add(InsightItem(**item))
    db.commit()
