# ADR 0003 — RAG Corpus Architecture: Chunking Strategy, Vector DB & Metadata Schema

- **Status:** Approved
- **Card:** D1.5 (Sprint 1)
- **Date:** 2026-07-31
- **Authors:** Daniel Kusi Boateng (Lead Software Engineer / ML Engineer),
  Chukwuebuka (Lead ML Engineer / RAG Corpus Service Owner)
- **Reviewers:** Olusegun (Infrastructure), Grace (Frontend — query consumer)
- **Depends on:** ADR-0001 (service boundaries — rag-corpus-service owns svc_rag + ChromaDB)
- **Consumed by:** S3.1 (rag-corpus-service ingest), S3.2 (rag-corpus-service query API),
  S3.3 (chat-orchestration-service RAG integration)

---

## 1. Context

`rag-corpus-service` must ingest a curated corpus of African financial knowledge —
business guides, market reports, sector case studies, regulatory summaries, and
community financial wisdom — and serve relevant passages to `chat-orchestration-service`
at query time to ground Chioma's responses in factual, contextually appropriate content.

Three design decisions must be settled before Chukwuebuka begins Sprint 3 implementation
(backlog risk R2 — embedding model / vector schema churn after ingestion):

1. **Chunking strategy** — how documents are split into retrievable units
2. **Vector DB choice** — ChromaDB vs Weaviate
3. **Metadata schema** — what fields are stored alongside each vector

This ADR locks all three. Changes after Sprint 3 ingestion begins require a re-index
job and a new ADR revision.

---

## 2. Decision Summary

| # | Decision Area | Choice |
|---|---|---|
| D1 | Chunking strategy | Semantic chunking by topic boundary, not fixed token size |
| D2 | Vector DB | ChromaDB (dev + Sprint 3–4); Weaviate migration path documented for prod |
| D3 | Embedding model | `BAAI/bge-small-en-v1.5` (frozen — see §5) |
| D4 | Metadata schema | 9-field schema: sector, country, content_type, author_profile, language, source_url, quality_score, persona_relevance, date_published |
| D5 | Retrieval strategy | Hybrid: dense vector similarity + metadata pre-filter |
| D6 | Collection structure | One ChromaDB collection per sector (6 collections) |

---

## 3. D1 — Chunking Strategy

### Decision: Semantic Chunking by Topic Boundary

**Rejected: Fixed token-size chunking** (e.g. 512 tokens with 50-token overlap).

Fixed-size chunking is the default in most RAG tutorials but is wrong for this corpus
for three reasons specific to AfriMentor:

1. **African financial content is topic-dense.** A single paragraph in a market guide
   may cover pricing strategy, supplier relationships, and cash-flow management in
   200 tokens. A fixed 512-token chunk will merge unrelated topics, polluting retrieval
   with irrelevant context that confuses Chioma's response.

2. **Chioma's persona requires topically coherent context.** If the retrieved chunk
   contains half a discussion on inventory management and half a discussion on mobile
   money, the LLM cannot cleanly ground a response on either topic. Semantic coherence
   of the retrieved chunk directly impacts response quality.

3. **Metadata filtering is topic-scoped.** The metadata schema (§5) tags chunks by
   `content_type` (e.g. `pricing_strategy`, `savings_method`, `regulatory`). This
   tagging is only meaningful if each chunk is topically coherent.

### Semantic Chunking Implementation

**Primary method: paragraph-boundary + topic-shift detection**

```
Document
  └── Split on double newlines (paragraph boundaries)
        └── For each paragraph group:
              ├── Compute sentence embeddings for consecutive paragraphs
              ├── Measure cosine similarity between adjacent paragraphs
              ├── If similarity drops below threshold (0.75): topic boundary → new chunk
              └── If chunk exceeds max_tokens (400): hard split at sentence boundary
```

**Parameters (tunable via `configs/rag.yaml`):**

| Parameter | Value | Rationale |
|---|---|---|
| `similarity_threshold` | 0.75 | Empirically tuned; lower = more splits, higher = larger chunks |
| `max_chunk_tokens` | 400 | Fits within 512-token embedding model context; leaves room for metadata prefix |
| `min_chunk_tokens` | 50 | Prevents single-sentence orphan chunks |
| `overlap_sentences` | 1 | One sentence of overlap at chunk boundaries for context continuity |

**Secondary method: structural markers**

For documents with explicit structure (headers, numbered sections), use structural
markers as hard chunk boundaries regardless of similarity score:

- Markdown `##` / `###` headers → always a new chunk
- Numbered section markers (`1.`, `2.1`, etc.) → always a new chunk
- Horizontal rules (`---`) → always a new chunk

**Tooling:** LangChain `SemanticChunker` (already in `requirements.txt` via
`langchain-community`) with a custom `AfriMentorSemanticChunker` wrapper that adds
the structural marker pass and enforces the min/max token bounds.

---

## 4. D2 — Vector DB Choice

### Decision: ChromaDB for Sprint 3–4; Weaviate migration path for production

**ChromaDB is already in the stack** (`chromadb==0.5.23` in `requirements.txt`,
running in `docker-compose.yml` at port 8100). The decision here is to commit to it
for Sprint 3–4 and document the Weaviate migration criteria.

#### ChromaDB — Why it stays for now

| Dimension | ChromaDB | Assessment |
|---|---|---|
| Operational weight | Single Docker container, zero config | ✅ Right for 4-person sprint team |
| Local dev | Runs on a laptop, persists to a volume | ✅ Matches ADR-0001 constraint |
| Python client | Native, no extra runtime | ✅ Consistent with Python/FastAPI stack |
| Metadata filtering | `where` clause on any metadata field | ✅ Sufficient for §5 schema |
| Hybrid search | Dense only (no native BM25) | ⚠️ Mitigated by metadata pre-filter |
| Scale ceiling | ~1M vectors per collection reliably | ✅ Well above Sprint 3–5 corpus size |
| Multi-tenancy | Collection-per-tenant pattern | ✅ Handled by collection-per-sector (§6) |

#### Weaviate — Migration criteria (when to switch)

Migrate to Weaviate when **any two** of the following are true:

- Corpus exceeds **500k vectors** across all collections
- Native **BM25 + vector hybrid search** is required for retrieval quality
- **Multi-language semantic search** (Swahili, Yoruba, Twi) requires a
  multilingual vectorizer module
- **GraphQL query interface** is needed for the admin research console
- Team has capacity to operate a separate Weaviate cluster

Migration is mechanical: the `rag-corpus-service` abstracts the vector store behind
a `VectorStore` protocol interface (see §7). Swapping ChromaDB for Weaviate is a
single implementation swap with no API contract changes.

---

## 5. D3 — Embedding Model (Frozen)

**Decision: `BAAI/bge-small-en-v1.5`**

| Dimension | Detail |
|---|---|
| Dimensions | 384 |
| Model size | 33M parameters (~130 MB) |
| Licence | Apache 2.0 |
| MTEB score | 62.x (top-tier for sub-100M models) |
| Inference | CPU-viable; ~50ms per chunk on a standard server |
| Context window | 512 tokens (matches max_chunk_tokens=400 + overhead) |

**Why not a larger model (e.g. `text-embedding-3-large`, `bge-large`):**

- `bge-small` runs on CPU inside the Docker container with no GPU dependency
- 384 dimensions keeps ChromaDB index size small (~1.5 KB per vector)
- Quality delta vs `bge-large` is <3% on retrieval benchmarks for domain-specific
  corpora — not worth the 4× inference cost and memory footprint

**This model is frozen.** Changing the embedding model after Sprint 3 ingestion
requires a full re-index of all collections. Any proposal to change must raise a
new ADR revision and include a re-index migration plan.

The model ID is stored as metadata on every vector (`embedding_model` field) so
a future re-index job can identify which vectors need updating.

---

## 6. D4 — Metadata Schema

Every chunk stored in ChromaDB carries the following 9-field metadata schema.
All fields are indexed for filtering. Fields marked **required** must be present
at ingestion time; optional fields default to `null`.

### Full Schema

| Field | Type | Required | Values / Format | Purpose |
|---|---|---|---|---|
| `sector` | string | ✅ | `trader` \| `tech` \| `fashion_retail` \| `agriculture` \| `creative` \| `general` | Primary retrieval filter — matches user's `sector_interest` from auth-user-service profile |
| `country` | string | ✅ | ISO 3166-1 alpha-2 (e.g. `NG`, `GH`, `KE`, `ZA`, `UG`) or `AFRICA` for pan-continental | Enables country-specific retrieval (Lagos market dynamics ≠ Nairobi market dynamics) |
| `content_type` | string | ✅ | See content type taxonomy below | Enables topic-scoped retrieval within a sector |
| `author_profile` | string | ✅ | `practitioner` \| `academic` \| `ngo` \| `government` \| `community` \| `synthetic` | Trust weighting — practitioner and community content ranked higher for Chioma's voice |
| `language` | string | ✅ | BCP-47 (e.g. `en`, `sw`, `yo`, `tw`, `fr`) | Enables language-matched retrieval for multilingual users |
| `source_url` | string | optional | Full URL or internal document ID | Source citation for Chioma's responses (NotebookLM-style widget, contract G1.3) |
| `quality_score` | float | optional | 0.0 – 1.0 | Editorial quality score assigned at ingestion; used to boost high-quality chunks in ranking |
| `persona_relevance` | string | optional | `market-queen` \| `tech-founder` \| `trader` \| `rural-hustler` \| `creative` \| `all` | Direct persona affinity tag — allows persona-scoped retrieval in Sprint 3 |
| `date_published` | string | optional | ISO 8601 date (`YYYY-MM-DD`) | Enables recency filtering; financial regulations and market data decay |

### Content Type Taxonomy

```
financial_fundamentals     — savings, budgeting, compound interest basics
pricing_strategy           — cost-plus, value-based, competitive pricing
cash_flow_management       — working capital, daily cash discipline
supplier_relationships     — credit terms, negotiation, diversification
market_dynamics            — demand cycles, seasonality, competition
savings_method             — ajo/esusu/chama, mobile money, formal banking
investment_basics          — stocks, bonds, real estate, business reinvestment
regulatory                 — tax obligations, business registration, licences
trade_finance              — import/export, forex, letters of credit, AfCFTA
agri_economics             — input costs, yield, value chain, cooperatives
tech_business              — unit economics, fundraising, product-market fit
creative_economy           — IP, licensing, irregular income, brand-building
case_study                 — real African business story (practitioner-authored)
community_wisdom           — proverbs, cultural financial practices, oral tradition
```

### Schema as Python TypedDict (for Chukwuebuka's implementation reference)

```python
from typing import Literal, TypedDict

Sector = Literal[
    "trader", "tech", "fashion_retail", "agriculture", "creative", "general"
]
ContentType = Literal[
    "financial_fundamentals", "pricing_strategy", "cash_flow_management",
    "supplier_relationships", "market_dynamics", "savings_method",
    "investment_basics", "regulatory", "trade_finance", "agri_economics",
    "tech_business", "creative_economy", "case_study", "community_wisdom",
]
AuthorProfile = Literal[
    "practitioner", "academic", "ngo", "government", "community", "synthetic"
]
PersonaRelevance = Literal[
    "market-queen", "tech-founder", "trader", "rural-hustler", "creative", "all"
]

class ChunkMetadata(TypedDict, total=False):
    # Required
    sector: Sector
    country: str                  # ISO 3166-1 alpha-2 or "AFRICA"
    content_type: ContentType
    author_profile: AuthorProfile
    language: str                 # BCP-47
    # Optional
    source_url: str
    quality_score: float          # 0.0 – 1.0
    persona_relevance: PersonaRelevance
    date_published: str           # ISO 8601
    # System fields (set automatically at ingestion)
    document_id: str              # parent document UUID
    chunk_index: int              # position within parent document
    embedding_model: str          # frozen: "BAAI/bge-small-en-v1.5"
    chunk_tokens: int             # token count of this chunk
```

---

## 7. D5 — Retrieval Strategy

**Decision: Hybrid — metadata pre-filter + dense vector similarity**

ChromaDB does not support native BM25 hybrid search. The hybrid effect is achieved
by combining metadata pre-filtering with dense retrieval:

```
Query: "How do I manage cash flow as a Lagos market trader?"
User profile: sector=trader, country=NG, language=en

Step 1 — Metadata pre-filter (ChromaDB `where` clause):
  { "sector": { "$in": ["trader", "general"] },
    "country": { "$in": ["NG", "AFRICA"] },
    "language": "en" }

Step 2 — Dense retrieval within filtered set:
  top_k=5 by cosine similarity to query embedding

Step 3 — Re-ranking (optional, Sprint 4):
  Re-rank by quality_score × similarity_score
  Boost chunks where persona_relevance matches active persona
```

**Query parameters (locked for Sprint 3 contract):**

```python
class RAGQueryRequest(BaseModel):
    query: str                          # user message or reformulated query
    sector: str                         # from user profile
    country: str                        # from user profile
    language: str = "en"
    persona_slug: str | None = None     # boosts persona_relevance filter
    top_k: int = 5                      # chunks returned to chat service
    min_quality_score: float = 0.5      # filter out low-quality chunks
```

**Response (locked for Sprint 3 contract — mitigates backlog risk R3):**

```python
class RAGChunk(BaseModel):
    chunk_id: str
    content: str
    similarity_score: float
    metadata: ChunkMetadata

class RAGQueryResponse(BaseModel):
    chunks: list[RAGChunk]
    query_embedding_ms: int             # latency telemetry
    total_candidates: int               # chunks evaluated before top_k
```

---

## 8. D6 — Collection Structure

**Decision: One ChromaDB collection per sector (6 collections)**

```
afrimentor_trader
afrimentor_tech
afrimentor_fashion_retail
afrimentor_agriculture
afrimentor_creative
afrimentor_general          ← pan-sector content; always queried alongside sector collection
```

**Rationale:**
- Keeps collection sizes manageable and query latency low
- Allows sector-specific index tuning in future
- `afrimentor_general` is always included in every query (pan-continental financial
  fundamentals apply across all sectors)
- Avoids a single monolithic collection that grows unbounded

**Rejected: single collection with sector metadata filter only.**
A single collection works at small scale but becomes a bottleneck as corpus grows —
every query scans the full index before filtering. Collection-per-sector pre-partitions
the search space.

---

## 9. VectorStore Protocol Interface

To enable the ChromaDB → Weaviate migration path (§4), Chukwuebuka must implement
the vector store behind this protocol. The FastAPI endpoints and chat-orchestration
integration point never import ChromaDB directly.

```python
from typing import Protocol

class VectorStore(Protocol):
    def upsert(
        self,
        chunk_id: str,
        content: str,
        embedding: list[float],
        metadata: ChunkMetadata,
        collection: str,
    ) -> None: ...

    def query(
        self,
        query_embedding: list[float],
        collection: str,
        where: dict,
        top_k: int,
    ) -> list[RAGChunk]: ...

    def delete(self, chunk_id: str, collection: str) -> None: ...
```

`ChromaVectorStore` implements this protocol in Sprint 3.
`WeaviateVectorStore` implements it when migration criteria are met.

---

## 10. Ingestion Pipeline (Sprint 3 Implementation Guide)

```
Document (PDF / Markdown / plain text)
  │
  ▼
1. Parse & clean          — strip boilerplate, normalise whitespace, detect language
  │
  ▼
2. Structural split       — split on headers / section markers → candidate chunks
  │
  ▼
3. Semantic chunking      — AfriMentorSemanticChunker (similarity_threshold=0.75)
  │                          enforces min/max token bounds
  ▼
4. Metadata tagging       — human-assigned required fields at ingest time
  │                          system fields auto-populated (document_id, chunk_index,
  │                          embedding_model, chunk_tokens)
  ▼
5. Embedding              — BAAI/bge-small-en-v1.5 (batch, CPU)
  │
  ▼
6. Upsert to ChromaDB     — VectorStore.upsert() → collection by sector
  │
  ▼
7. Persist metadata       — document record written to svc_rag Postgres
                             (document_id, title, source_url, chunk_count, ingested_at)
```

---

## 11. Consequences

**Positive:** semantic chunks improve retrieval precision for topic-dense African
financial content; frozen embedding model prevents re-index churn (mitigates R2);
locked `/rag/query` contract unblocks chat-orchestration-service Sprint 3 integration
(mitigates R3); collection-per-sector keeps query latency low; VectorStore protocol
makes ChromaDB → Weaviate migration mechanical.

**Negative / trade-offs:** semantic chunking is more complex to implement than
fixed-size (mitigated by LangChain `SemanticChunker`); metadata tagging at ingestion
requires editorial discipline — missing required fields must be rejected at the API
boundary; `bge-small` is English-primary (multilingual retrieval quality for Swahili/
Yoruba/Twi is acceptable but not optimal — revisit with a multilingual embedding model
if retrieval quality degrades on non-English queries).

**Follow-up ADRs:** 0004 mTLS & service-to-service auth hardening; 0005 Kafka migration
criteria; 0006 multi-region data residency.

---

## 12. Sign-off

| Reviewer | Role | Status |
|---|---|---|
| Daniel Kusi Boateng | Lead Software Engineer / ML Engineer (Co-author) | ✅ Approved |
| Chukwuebuka | Lead ML Engineer / RAG Corpus Service Owner (Co-author) | ☐ Pending |
| Olusegun | Product Owner / Backend Lead (Infrastructure) | ☐ Pending |
| Grace | Frontend Lead (query consumer — contract G1.3) | ☐ Pending |
