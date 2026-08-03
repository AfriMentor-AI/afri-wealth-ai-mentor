# AfriMentor RAG Corpus — Tier-1 Sources

## How to add a new transcript

1. Find a YouTube video (15+ minutes preferred)
2. Click ⋯ below the video → Show transcript → Copy all text
3. Save as `{speaker_slug}_{topic}.txt` in this folder
   Example: `vusi_thembekwayo_entrepreneurship.txt`
4. Add the entry to `scripts/ingest_tier1.py` DOCUMENTS list
5. Run `python3 scripts/ingest_tier1.py`

## Metadata fields (required for every document)
- author: Full speaker name
- country: NG | GH | KE | ZA | ZW | ET | general
- sector: fashion | wholesale_trade | food_trade | financial_literacy | telecoms_technology | manufacturing_trade | general_business
- content_type: video_transcript | interview_transcript | speech_transcript | guide
- source_url: YouTube URL
- channel: Channel name

## Priority personalities to collect (Sprint 1)
1. Vusi Thembekwayo (ZA) — general_business
2. Arese Ugwu / Smart Money Woman (NG) — financial_literacy
3. Tony Elumelu — TEF speech (NG) — finance_investment
4. Folorunsho Alakija — Arise TV (NG) — fashion_oil_finance
5. Fred Swaniker — ALA talks (GH) — education_leadership
6. Bethlehem Tilahun Alemu — TED Talk (ET) — fashion_trade
7. Patrick Awuah — TED Talk (GH) — education_entrepreneurship
8. Google Hustle Academy speakers — Google Africa YouTube (NG/GH/KE/ZA) — SME

## Current corpus status
- dangote_principles.txt — NG — manufacturing_trade
- masiyiwa_resilience.txt — ZW — telecoms_technology
- elumelu_africapitalism.txt — NG — finance_investment
- africa_financial_literacy_guide.txt — general — financial_literacy
- nigeria_trade_guide.txt — NG — wholesale_trade
