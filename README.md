# FinMatrix

**AI-powered stock analysis platform for BIST investors**

FinMatrix is a local-first financial analysis platform for the Turkish stock market. It combines structured BIST market data, KAP disclosures, and LLM-based analysis so users can explore stocks, compare companies, follow watchlists, and ask natural-language questions backed by source documents.

> FinMatrix does not provide buy/sell recommendations. It is designed for data-backed analysis only.

---

## Product Scope

FinMatrix is built around four parallel product slices:

- **Dashboard**: stock profile, price chart, financial metrics, quarterly performance, related KAP filings
- **Watchlist**: tracked stocks, live summary cards, notification preferences
- **News Feed**: KAP-driven news stream filtered by watchlist relevance
- **AI Chat**: source-backed analysis, comparison tables, inline charts, suggested follow-up questions

The project is being developed as **frontend + backend in parallel**, not as a backend-first then frontend-later workflow.

---

## Current Architecture Direction

### Backend

- FastAPI
- SQLAlchemy + Alembic
- PostgreSQL
- ChromaDB
- APScheduler or equivalent local scheduler

### Frontend

- HTML
- CSS
- JavaScript
- Chart.js

### AI Layer

- OpenRouter for all LLM API calls
- RAG over KAP documents
- Separate strategy for:
- chat/text analysis
- judge/evaluation
- reranking/helper tasks

Model names are intentionally not fixed yet. Routing and model choice will be finalized later.

---

## Data Sources

FinMatrix does not rely on a single provider. The current data-source strategy is:

| Need | Primary source | Role |
|---|---|---|
| Price history, market data, financial statements | `borsapy` | Main market data provider |
| KAP company info, disclosure queries, filing metadata | `pykap` | Main KAP provider |
| Secondary KAP access path | `kap_sdk` | Fallback / cross-check provider |

### What these sources solve

- BIST stock data
- historical price data for charts
- financial statements
- watchlist market data
- KAP disclosure lists
- company-to-KAP matching
- KAP-driven news ingestion
- document metadata collection for RAG

### What they do not solve by themselves

- provider abstraction
- canonical normalization layer
- PDF download and storage
- chunking and embedding
- retrieval quality
- scheduling and incremental sync
- retry, caching, deduplication, observability
- orchestration, judge, and guardrails

### Important note about `kap_sdk`

The folder [`search/kap_sdk`](C:/Users/yigit/Desktop/FinMatrix/search/kap_sdk) is currently empty in the repo. `kap_sdk` is treated as an installed Python dependency, not as repo-owned source code.

---

## AI / LLM Strategy

All LLM calls will go through **OpenRouter**.

The architecture separates LLM responsibilities by role:

- **Chat / text analysis**: stronger reasoning and long-context interpretation of KAP documents
- **Judge**: separate evaluation pass for faithfulness, relevance, and consistency
- **Reranker / helper tasks**: cheaper, faster model class for narrower filtering or ranking work
- **Numerical flow**: prefer deterministic code over LLM whenever possible

### Cost Control and Fallback

- token and cost tracking per agent type
- limited prompt size and context trimming
- retrieval-first context narrowing before generation
- independent fallback strategy for chat and judge flows
- cheaper default class for reranker/helper calls
- retry and bounded fallback on timeout/rate-limit/provider errors
- degrade mode options:
- disable reranking
- shorten judge context
- shorten answer format
- skip non-critical extras like suggested questions

---

## Planned Repository Shape

```text
FinMatrix/
|-- backend/
|   |-- app/
|   |   |-- models/
|   |   |-- schemas/
|   |   |-- routers/
|   |   |-- services/
|   |   |   |-- data/
|   |   |   |-- pipeline/
|   |   |   |-- rag/
|   |   |   |-- agents/
|   |   |   `-- eval/
|   |   `-- prompts/
|   |-- alembic/
|   |-- scripts/
|   `-- tests/
|-- frontend/
|-- search/
|   |-- borsapy/
|   |-- pykap/
|   `-- kap_sdk/
|-- README.md
`-- ROADMAP.md
```

For the detailed implementation plan, see [ROADMAP.md](C:/Users/yigit/Desktop/FinMatrix/ROADMAP.md).

---

## Development Model

This project is **local-first**.

Current assumptions:

- Docker is not part of the active development flow
- local Python virtual environment
- local PostgreSQL or an existing local database
- local or separately running ChromaDB
- manual or scheduled sync jobs

---

## Local Setup

### Prerequisites

- Python 3.11+
- PostgreSQL
- ChromaDB
- Node is not required for the current static frontend workflow
- OpenRouter API key

### Suggested environment variables

```env
DATABASE_URL=postgresql://...
CHROMA_HOST=localhost
CHROMA_PORT=8001
OPENROUTER_API_KEY=...
TELEGRAM_BOT_TOKEN=...
```

### Basic local workflow

```bash
git clone https://github.com/alpbel0/FinMatrix.git
cd FinMatrix
```

Frontend can continue as static pages during early development. Backend, database, vector store, and sync services are planned to run locally without Docker.

---

## Planned Feature Details

### Dashboard

- price chart with selectable timeframes
- key metric cards
- quarterly net profit visualization
- financial summary tables
- related KAP filing list

### Watchlist

- tracked stock cards
- live market summaries
- mini chart/sparkline support
- notification toggles

### News Feed

- KAP-based stream
- category filters
- watchlist-aware relevance
- direct handoff into AI analysis

### AI Chat

- natural-language BIST analysis
- KAP-backed answers with source transparency
- comparison tables
- inline chart generation
- judge-controlled answer validation

### Telegram

- KAP filing alerts
- watchlist-linked notifications
- future digest and event-based alerts

---

## Status

The roadmap currently assumes:

- no Docker workflow
- `borsapy + pykap + kap_sdk` data-source strategy
- OpenRouter-based LLM layer
- frontend and backend progressing in parallel vertical slices

---

## Reference

- Detailed plan: [ROADMAP.md](C:/Users/yigit/Desktop/FinMatrix/ROADMAP.md)
- Market data source: [search/borsapy](C:/Users/yigit/Desktop/FinMatrix/search/borsapy)
- KAP source: [search/pykap](C:/Users/yigit/Desktop/FinMatrix/search/pykap)
- Optional KAP fallback folder: [search/kap_sdk](C:/Users/yigit/Desktop/FinMatrix/search/kap_sdk)
