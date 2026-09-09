"""Idempotent catalog seed (card O3.2) — sample items covering text, audio, and
video across multiple languages and difficulty levels. Runs once at startup."""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from .models import InsightItem

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data"
INSIGHTS_JSON_PATH = DATA_DIR / "insights.json"

DEFAULT_SEED_ITEMS = [
    # ── Text ──────────────────────────────────────────────────────────────────
    {
        "slug": "how-to-price-your-trade",
        "title": "How to price your trade",
        "summary": (
            "A practical framework for setting prices that cover costs and leave room "
            "for profit."
        ),
        "category": "Pricing",
        "media_type": "text",
        "duration_seconds": 180,
        "language": "en",
        "difficulty": "beginner",
        "audio_narration": (
            "Welcome to this micro-lesson on pricing your trade. Many traders calculate "
            "profit simply as the selling price minus the market purchase price. But what about "
            "transport, market toll, MoMo withdrawal fees, and spoilage? To stay in business, "
            "you must account for your true unit cost."
        ),
        "content": (
            "Setting the right price is the difference between surviving day-to-day and "
            "building generational wealth. This lesson walks you through calculating your "
            "true cost of goods sold and setting prices customers respect."
        ),
    },
    {
        "slug": "bookkeeping-with-mobile-money",
        "title": "Bookkeeping with Mobile Money",
        "summary": "Turning your mobile money statement into a simple daily ledger.",
        "category": "Bookkeeping",
        "media_type": "text",
        "duration_seconds": 120,
        "language": "en",
        "difficulty": "beginner",
        "audio_narration": (
            "Mobile money statements are a treasure trove of financial records. In this "
            "lesson, learn how to export and review daily SMS notifications to track "
            "customer payments, supplier disbursements, and fees."
        ),
        "content": (
            "Most micro-merchants use mobile money daily but rarely reconcile their "
            "transaction statements. By dedicating 5 minutes every evening to log MoMo "
            "references into a simple ledger, you prepare for bank financing."
        ),
    },
    {
        "slug": "reading-your-first-loan-agreement",
        "title": "Reading your first loan agreement",
        "summary": "The clauses that matter most before you sign.",
        "category": "Finance",
        "media_type": "text",
        "duration_seconds": 180,
        "language": "en",
        "difficulty": "intermediate",
        "audio_narration": (
            "Before taking any loan, understand the total cost of credit. Do not look "
            "only at the monthly percentage. Look for processing fees, insurance "
            "charges, late penalty compounding, and reducing balance terms."
        ),
        "content": (
            "A loan agreement often contains legal covenants and fee schedules that "
            "dramatically increase your APR. This guide breaks down the essential clauses "
            "every borrower must scrutinize."
        ),
    },
    {
        "slug": "jinsi-ya-kuweka-akiba-wakati-wa-kiangazi",
        "title": "Jinsi ya kuweka akiba wakati wa kiangazi",
        "summary": "Kujenga akiba kabla ya miezi ngumu na kuinyoosha inapofika.",
        "category": "Savings",
        "media_type": "text",
        "duration_seconds": 120,
        "language": "sw",
        "difficulty": "beginner",
        "audio_narration": (
            "Habari za kazi! Katika somo hili, tunajifunza jinsi ya kuweka akiba na "
            "kulinda biashara yako wakati wa msimu wa kiangazi au biashara inapopungua."
        ),
        "content": (
            "Kujenga akiba wakati wa mauzo ya juu kunakusaidia kutopata shida wakati wa "
            "miezi migumu. Hatua hizi zitakusaidia kusimamia mapato yako kwa utaratibu "
            "thabiti."
        ),
    },
    # ── Audio ─────────────────────────────────────────────────────────────────
    {
        "slug": "saving-during-lean-seasons",
        "title": "Saving during lean seasons",
        "summary": "Building a buffer before the slow months hit, and stretching it once they do.",
        "category": "Savings",
        "media_type": "audio",
        "duration_seconds": 180,
        "language": "en",
        "difficulty": "beginner",
        "transcript_url": "/media/transcripts/saving-lean-seasons-en.txt",
        "audio_narration": (
            "Hello! Let's talk about saving during lean seasons. In almost every African "
            "trade, revenue fluctuates with seasons, harvests, and holidays. The key to "
            "financial peace is smoothing your consumption so slow months never force "
            "you into predatory emergency loans."
        ),
        "content": (
            "Every enterprise has seasonal peaks and troughs. By mapping your annual sales "
            "cycle and automating your lean-season lockbox during boom months, you protect "
            "your household from stress."
        ),
    },
    {
        "slug": "negotiating-with-suppliers",
        "title": "Negotiating with suppliers",
        "summary": "Getting better terms without burning the relationship.",
        "category": "Operations",
        "media_type": "audio",
        "duration_seconds": 180,
        "language": "en",
        "difficulty": "intermediate",
        "transcript_url": "/media/transcripts/negotiating-suppliers-en.txt",
        "audio_narration": (
            "Suppliers are your key partners. Negotiation is about finding mutual "
            "wins—like flexible payment cycles, consignment terms, or bulk delivery "
            "discounts."
        ),
        "content": (
            "Mastering supplier negotiation gives you the working capital cushion "
            "needed to fulfill bigger customer orders. Learn how to leverage prompt "
            "payment history to unlock 14 to 30-day supplier trade credit."
        ),
    },
    {
        "slug": "eto-owo-fun-awon-onisowo-keekee-yo",
        "title": "Ètò owó fún àwọn oníṣòwò kéékèèké",
        "summary": "Bí a ṣe lè tọ́jú owó iṣowo kí o má bàa papọ̀ mọ́ owó ilé.",
        "category": "Bookkeeping",
        "media_type": "audio",
        "duration_seconds": 120,
        "language": "yo",
        "difficulty": "beginner",
        "transcript_url": "/media/transcripts/bookkeeping-yo.txt",
        "audio_narration": (
            "Ẹ ku iṣẹ o gbogbo oníṣòwò. Ẹkọ yii kọ wa bí a ṣe lè ya owó iṣowo "
            "sọ́tọ̀ kúrò nínú owó inawo ile, kí olúkúlùkù lè mọ èrè gidi tí o ń wọlé."
        ),
        "content": (
            "Bí a ṣe lè ya owó iṣowo sọ́tọ̀ kúrò nínú owó inawo ile. Èyí yóò jẹ́ kí "
            "iṣowo rẹ tẹ̀síwájú láìsí ìṣòro owó."
        ),
    },
    {
        "slug": "how-to-build-an-emergency-fund-on-irregular-income",
        "title": "How to build an emergency fund on irregular income",
        "summary": "Practical steps for traders and gig workers with unpredictable cash flow.",
        "category": "Savings",
        "media_type": "audio",
        "duration_seconds": 240,
        "language": "en",
        "difficulty": "intermediate",
        "transcript_url": "/media/transcripts/emergency-fund-irregular-income-en.txt",
        "audio_narration": (
            "When your income changes from week to week, adopt a percentage-based sweep "
            "method: save a percentage of every profitable transaction rather than a "
            "static dollar amount."
        ),
        "content": (
            "Traders and freelancers face variable cash flows. An emergency fund of "
            "3 to 6 months of basic living costs provides the runway to survive sudden "
            "market downturns."
        ),
    },
    # ── Video ─────────────────────────────────────────────────────────────────
    {
        "slug": "setting-up-a-simple-cash-flow-tracker",
        "title": "Setting up a simple cash-flow tracker",
        "summary": "A 10-minute walkthrough using a free spreadsheet template.",
        "category": "Bookkeeping",
        "media_type": "video",
        "duration_seconds": 180,
        "language": "en",
        "difficulty": "beginner",
        "thumbnail_url": "/media/thumbnails/cashflow-tracker.jpg",
        "transcript_url": "/media/transcripts/cashflow-tracker-en.txt",
        "audio_narration": (
            "Watch how to organize your cash inflows and outflows by date. "
            "Cash flow is the oxygen of your business."
        ),
        "content": (
            "A visual guide to tracking daily opening balance, total cash in, "
            "total cash out, and closing balance."
        ),
    },
    {
        "slug": "understanding-interest-rates",
        "title": "Understanding interest rates",
        "summary": "Simple vs compound interest explained with real market examples.",
        "category": "Finance",
        "media_type": "video",
        "duration_seconds": 180,
        "language": "en",
        "difficulty": "intermediate",
        "thumbnail_url": "/media/thumbnails/interest-rates.jpg",
        "transcript_url": "/media/transcripts/interest-rates-en.txt",
        "audio_narration": (
            "Learn how interest compounds over time. Whether saving in a treasury bill "
            "or borrowing for inventory, knowing how interest works puts you in command "
            "of your money."
        ),
        "content": (
            "Compare a 5% monthly flat rate with an annualized 28% reducing balance loan."
        ),
    },
    {
        "slug": "comment-fixer-le-prix-de-vos-produits",
        "title": "Comment fixer le prix de vos produits",
        "summary": "Méthode pas-à-pas pour calculer un prix de vente rentable.",
        "category": "Pricing",
        "media_type": "video",
        "duration_seconds": 180,
        "language": "fr",
        "difficulty": "beginner",
        "thumbnail_url": "/media/thumbnails/pricing-fr.jpg",
        "transcript_url": "/media/transcripts/pricing-fr.txt",
        "audio_narration": (
            "Bienvenue à cette leçon sur la fixation des prix. Découvrez comment "
            "calculer vos coûts réels et dégager une marge bénéficiaire durable pour "
            "votre entreprise."
        ),
        "content": (
            "Guide pratique pour les commerçants et artisans francophones d'Afrique "
            "de l'Ouest pour tarifer leurs produits."
        ),
    },
    {
        "slug": "advanced-inventory-management-for-growing-traders",
        "title": "Advanced inventory management for growing traders",
        "summary": "FIFO, reorder points, and supplier lead times without expensive software.",
        "category": "Operations",
        "media_type": "video",
        "duration_seconds": 240,
        "language": "en",
        "difficulty": "advanced",
        "thumbnail_url": "/media/thumbnails/inventory-advanced.jpg",
        "transcript_url": "/media/transcripts/inventory-advanced-en.txt",
        "audio_narration": (
            "Excess stock ties up capital; stockouts turn customers away. Learn simple "
            "inventory formulas like reorder point and minimum stock safety buffers."
        ),
        "content": (
            "Advanced operational concepts made simple: First-In-First-Out (FIFO), "
            "managing perishable shrinkage, and calculating optimal reorder points."
        ),
    },
]


def load_seed_items() -> list[dict]:
    """Load items from data/insights.json if present; otherwise write default and return."""
    if INSIGHTS_JSON_PATH.exists():
        try:
            with open(INSIGHTS_JSON_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(
                "Failed to parse %s (%s); using default seed items", INSIGHTS_JSON_PATH, e
            )

    # Persist defaults to JSON for easy editing outside python code
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(INSIGHTS_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SEED_ITEMS, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning("Could not persist seed items to %s: %s", INSIGHTS_JSON_PATH, e)

    return DEFAULT_SEED_ITEMS


def seed_catalog(db: Session) -> None:
    """Idempotent upsert: matches on slug or title to update or create items with stable UUIDs."""
    items = load_seed_items()
    updated = 0
    created = 0

    for item_data in items:
        slug = item_data.get("slug")
        title = item_data.get("title")

        existing = None
        if slug:
            existing = db.query(InsightItem).filter(InsightItem.slug == slug).first()
        if not existing and title:
            existing = db.query(InsightItem).filter(InsightItem.title == title).first()

        if existing:
            for k, v in item_data.items():
                setattr(existing, k, v)
            updated += 1
        else:
            # Deterministic UUID5 based on slug or title so IDs are stable across environments
            item_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"insight:{slug or title}"))
            db.add(InsightItem(id=item_id, **item_data))
            created += 1

    db.commit()
    logger.info("Catalog seeded: %d updated, %d created", updated, created)


def seed_if_empty(db: Session) -> None:
    """Alias for backwards compatibility with main.py lifespan."""
    seed_catalog(db)
