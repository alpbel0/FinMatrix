# CLAUDE.md — FinMatrix Project Context

> **Last Updated:** March 12, 2026
> **Project:** AI-Powered Stock Analysis Platform for BIST Investors
> **Author:** Yiğitalp ([@alpbel0](https://github.com/alpbel0))

---

## Project Overview

FinMatrix is a financial analysis platform where users can query Turkish stock market (BIST) data using natural language. Users can ask questions like *"Compare THYAO and ASELS net profit over 3 years"* and receive dynamically generated charts and AI-powered analysis — backed by real KAP filings and yfinance data.

**Critical Rule:** FinMatrix NEVER makes buy/sell recommendations. It provides data-driven, unbiased analysis only.

---

## Technology Stack

### Backend
| Component | Technology |
|-----------|------------|
| Framework | FastAPI (Python 3.11+) |
| Database | PostgreSQL 15 |
| Vector DB | ChromaDB |
| ORM | SQLAlchemy (async) |
| Migrations | Alembic |
| LLM | Google Gemini Flash |
| Multi-Agent Orchestration | LangGraph |
| Text Analysis Agent | CrewAI |
| Code Execution Agent | AutoGen |
| Containerization | Docker + Docker Compose |

### Frontend
| Component | Technology |
|-----------|------------|
| Structure | HTML5 |
| Styling | CSS3 (CSS Variables, Responsive) |
| Interactivity | Vanilla JavaScript (ES6+) |
| Charts | Chart.js |
| Data Fetching | Fetch API |

### External Data Sources
| Source | Purpose |
|--------|---------|
| yfinance | Stock prices, financial statements, metrics |
| KAP (kap.org.tr) | Turkish company disclosures and reports |

---

## Architecture Principles

### Strict Agent Role Separation

One of the core design decisions is **strict role separation** between AI frameworks to prevent agent chaos — a common failure mode in multi-agent systems where agents duplicate work, conflict, or make redundant API calls.

| Agent | Role | Responsibility |
|-------|------|----------------|
| **LangGraph** | Orchestrator | Receives user query, decides which agents to activate, merges results, triggers Judge Agent for quality control |
| **CrewAI** | Text Analyst | Reads and interprets KAP PDF reports from ChromaDB — summarizes company risks, strategy, and financial narrative |
| **AutoGen** | Code Executor | Handles all numerical work — writes and runs Python to calculate metrics, generate charts, and process yfinance data |
| **Judge Agent** | Evaluator | Scores every response against source documents before delivery — blocks hallucinated answers and triggers retries |

> **Golden Rule:** LangGraph is the brain. CrewAI reads. AutoGen computes. The Judge verifies. None of them do each other's job.

---

## Project Structure

```
FinMatrix/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pyproject.toml
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI app instance, lifespan, CORS, middleware
│   │   ├── config.py                  # pydantic-settings: env variables, DB URL, API keys
│   │   ├── database.py                # AsyncSession factory, engine, Base declarative
│   │   ├── dependencies.py            # get_db, get_current_user, get_admin_user
│   │   │
│   │   ├── models/                    # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── user.py                # users, telegram_settings
│   │   │   ├── stock.py               # stocks
│   │   │   ├── watchlist.py           # watchlist
│   │   │   ├── stock_price.py         # stock_prices (partitioned)
│   │   │   ├── balance_sheet.py       # balance_sheets
│   │   │   ├── income_statement.py    # income_statements
│   │   │   ├── cash_flow.py           # cash_flows
│   │   │   ├── kap_report.py          # kap_reports + sync_status ENUM
│   │   │   ├── news.py                # news, user_news + news_source ENUM
│   │   │   ├── chat.py                # chat_sessions, chat_messages + ENUMs
│   │   │   ├── document_chunk.py      # document_chunks + embedding_status ENUM
│   │   │   ├── pipeline_log.py        # pipeline_logs + pipeline_status ENUM
│   │   │   └── eval_log.py            # eval_logs + hallucination_reports VIEW
│   │   │
│   │   ├── schemas/                   # Pydantic request/response models
│   │   │   ├── auth.py
│   │   │   ├── stock.py
│   │   │   ├── watchlist.py
│   │   │   ├── news.py
│   │   │   ├── chat.py
│   │   │   ├── financials.py
│   │   │   ├── eval.py
│   │   │   └── telegram.py
│   │   │
│   │   ├── routers/                   # FastAPI route handlers
│   │   │   ├── auth.py                # POST /register, /login — GET /me
│   │   │   ├── stocks.py              # GET /stocks, /stocks/{symbol}, /prices, /metrics, etc.
│   │   │   ├── watchlist.py           # GET/POST/DELETE /watchlist
│   │   │   ├── news.py                # GET /news
│   │   │   ├── chat.py                # CRUD /chat/sessions — POST /messages — SSE streaming
│   │   │   └── admin.py               # GET /admin/eval/stats, /hallucinations
│   │   │
│   │   ├── services/                  # Business logic layer
│   │   │   ├── auth_service.py
│   │   │   ├── stock_service.py
│   │   │   ├── watchlist_service.py
│   │   │   ├── news_service.py
│   │   │   ├── chat_service.py
│   │   │   │
│   │   │   ├── data/                  # External data fetching
│   │   │   │   ├── yfinance_service.py
│   │   │   │   ├── kap_service.py
│   │   │   │   └── bist_service.py
│   │   │   │
│   │   │   ├── pipeline/              # Data processing pipeline
│   │   │   │   ├── chunking_service.py
│   │   │   │   ├── embedding_service.py
│   │   │   │   ├── sync_service.py
│   │   │   │   └── scheduler.py
│   │   │   │
│   │   │   ├── rag/                   # Retrieval-Augmented Generation
│   │   │   │   ├── retriever.py
│   │   │   │   ├── reranker.py
│   │   │   │   └── context_builder.py
│   │   │   │
│   │   │   ├── agents/                # Multi-agent system
│   │   │   │   ├── orchestrator.py    # LangGraph state graph
│   │   │   │   ├── query_classifier.py
│   │   │   │   ├── text_analyst.py    # CrewAI agent
│   │   │   │   ├── code_executor.py   # AutoGen agent
│   │   │   │   ├── merger.py
│   │   │   │   └── judge.py           # Judge Agent
│   │   │   │
│   │   │   ├── eval/                  # EvalOps — hallucination detection
│   │   │   │   ├── metrics.py
│   │   │   │   ├── judge_evaluator.py
│   │   │   │   └── retry_handler.py
│   │   │   │
│   │   │   ├── chart_service.py
│   │   │   ├── notification_service.py
│   │   │   └── telegram_service.py
│   │   │
│   │   ├── utils/
│   │   │   ├── logger.py
│   │   │   ├── security.py
│   │   │   ├── rate_limiter.py
│   │   │   ├── exceptions.py
│   │   │   ├── constants.py
│   │   │   └── helpers.py
│   │   │
│   │   └── prompts/                   # LLM prompt templates
│   │       ├── system_prompt.txt
│   │       ├── judge_prompt.txt
│   │       ├── text_analyst_prompt.txt
│   │       ├── code_executor_prompt.txt
│   │       ├── query_classifier_prompt.txt
│   │       └── summary_prompt.txt
│   │
│   ├── alembic/                       # Database migrations
│   │   ├── alembic.ini
│   │   ├── env.py
│   │   └── versions/
│   │
│   ├── scripts/                       # Utility scripts
│   │   ├── seed_stocks.py
│   │   ├── backfill_prices.py
│   │   ├── backfill_financials.py
│   │   └── create_partitions.py
│   │
│   └── tests/                         # Backend tests
│       ├── conftest.py                # pytest fixtures (async)
│       ├── factories.py               # Factory Boy factories
│       ├── unit/                      # Unit tests
│       │   └── test_main.py           # Main app tests
│       ├── integration/               # Integration tests
│       ├── e2e/                       # End-to-end tests
│       └── mocks/                     # Mock objects
│
├── backend/pytest.ini                 # pytest configuration
├── backend/Dockerfile
│
├── frontend/
│   ├── index.html                     # News Feed page
│   ├── dashboard.html                 # Stock Dashboard page
│   ├── chat.html                      # AI Chat page
│   ├── watchlist.html                 # Watchlist page
│   ├── login.html
│   ├── register.html
│   │
│   ├── css/
│   │   ├── main.css
│   │   ├── components.css
│   │   ├── news.css
│   │   ├── dashboard.css
│   │   ├── chat.css
│   │   ├── watchlist.css
│   │   └── auth.css
│   │
│   ├── js/
│   │   ├── api.js                     # Base API client
│   │   ├── auth.js                    # JWT token management
│   │   ├── news.js
│   │   ├── dashboard.js
│   │   ├── chat.js
│   │   ├── watchlist.js
│   │   │
│   │   ├── components/
│   │   │   ├── chart-factory.js
│   │   │   ├── stock-search.js
│   │   │   ├── notification-toast.js
│   │   │   └── modal.js
│   │   │
│   │   └── utils/
│   │       ├── constants.js
│   │       ├── formatters.js
│   │       └── validators.js
│   │
│   └── assets/
│       ├── img/
│       └── fonts/
│
├── docs/
│   ├── screenshots/
│   └── diagrams/
│
├── infra/
│   ├── nginx/
│   └── github/workflows/
│
├── docker-compose.yml
├── docker-compose.prod.yml
├── docker-compose.test.yml            # Test PostgreSQL (port 5434)
├── .env.example
├── .gitignore
├── .dockerignore
├── Makefile
├── README.md
├── ROADMAP.md
└── CLAUDE.md
```

---

## Database Schema Overview

### Core Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts, authentication |
| `telegram_settings` | Telegram notification preferences |
| `stocks` | BIST stock master data |
| `watchlist` | User-stock tracking relationships |
| `stock_prices` | Historical price data (partitioned by month) |
| `balance_sheets` | Company balance sheet data |
| `income_statements` | Company income statement data |
| `cash_flows` | Company cash flow data |
| `kap_reports` | KAP disclosure reports |
| `news` | News items derived from KAP reports |
| `user_news` | User-specific news read status |
| `chat_sessions` | Chat conversation sessions |
| `chat_messages` | Individual chat messages |
| `document_chunks` | PDF chunks for RAG |
| `pipeline_logs` | Data pipeline execution logs |
| `eval_logs` | AI response evaluation metrics |

### Key ENUMs

```python
sync_status = ('PENDING', 'SUCCESS', 'FAILED')
news_source = ('kap_summary', 'external_news', 'manual')
message_role = ('user', 'assistant', 'system')
message_type = ('text', 'chart', 'table', 'system')
embedding_status = ('PENDING', 'SUCCESS', 'FAILED')
pipeline_status = ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED')
```

---

## API Endpoints Overview

### Authentication (`/api/auth`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Create new user account |
| POST | `/login` | Authenticate and get JWT token |
| GET | `/me` | Get current user info |

### Stocks (`/api/stocks`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List all active stocks |
| GET | `/{symbol}` | Get stock details |
| GET | `/{symbol}/prices` | Get price history |
| GET | `/{symbol}/financials` | Get financial statements |
| GET | `/{symbol}/quarterly` | Get quarterly net profit (8 quarters) |
| GET | `/{symbol}/metrics` | Get key metrics with sector comparison |
| GET | `/{symbol}/kap-reports` | Get related KAP filings |

### Watchlist (`/api/watchlist`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List user's watchlist |
| POST | `/` | Add stock to watchlist |
| DELETE | `/{stock_id}` | Remove from watchlist |
| PATCH | `/{stock_id}/notifications` | Toggle notifications |

### Chat (`/api/chat`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/sessions` | Create new chat session |
| GET | `/sessions` | List user's sessions |
| GET | `/sessions/{id}` | Get session with messages |
| DELETE | `/sessions/{id}` | Delete session |
| POST | `/sessions/{id}/messages` | Send message (sync) |
| POST | `/sessions/{id}/messages/stream` | Send message (SSE stream) |

### News (`/api/news`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | List filtered news |
| GET | `/{id}` | Get news detail |
| POST | `/{id}/read` | Mark as read |

### Admin (`/api/admin`) — Admin Only
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/eval/stats` | Eval statistics |
| GET | `/hallucinations` | Hallucination reports |
| GET | `/pipeline-logs` | Pipeline execution logs |

---

## Docker Services

| Container | Service | Internal Port | External Port |
|-----------|---------|---------------|---------------|
| `finmatrix-api` | FastAPI | 8000 | 8002 |
| `finmatrix-db` | PostgreSQL 15 | 5432 | 5433 |
| `finmatrix-vector` | ChromaDB | 8000 | 8001 |
| `finmatrix-test-db` | PostgreSQL 15 (tests) | 5432 | 5434 |

### Common Commands

```bash
# Start all services
docker-compose up --build -d

# Stop all services
docker-compose down

# Stop and wipe all data
docker-compose down -v

# View logs
docker-compose logs -f api

# Run backend tests
docker-compose exec api pytest

# Access PostgreSQL
docker-compose exec db psql -U finmatrix -d finmatrix
```

---

## Environment Variables

Required environment variables (see `.env.example`):

```bash
# Database
DATABASE_URL=postgresql://finmatrix:finmatrix@db:5432/finmatrix

# ChromaDB
CHROMA_HOST=vector
CHROMA_PORT=8001

# LLM
GOOGLE_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key  # Judge fallback

# Auth
SECRET_KEY=your_jwt_secret_key

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

### Test Environment

```bash
# Test Database (automatic in pytest)
TEST_DATABASE_URL=postgresql+asyncpg://finmatrix_test:finmatrix_test@localhost:5434/finmatrix_test
```

---

## Test Infrastructure

### Test Stack

| Component | Technology |
|-----------|------------|
| Test Framework | pytest |
| Async Support | pytest-asyncio |
| Coverage | pytest-cov |
| Factories | factory-boy |
| Test Containers | testcontainers |
| HTTP Client | httpx (TestClient) |

### Directory Structure

```
backend/tests/
├── __init__.py
├── conftest.py                    # Pytest fixtures
├── factories.py                   # Factory Boy factories
├── unit/                          # Unit tests
│   ├── test_main.py               # Main app tests
│   ├── test_auth_service.py
│   ├── test_stock_service.py
│   └── ...
├── integration/                   # Integration tests
│   ├── test_auth_flow.py
│   ├── test_chat_flow.py
│   └── ...
├── e2e/                           # End-to-end tests
│   └── test_full_user_journey.py
└── mocks/                         # Mock objects
    ├── mock_yfinance.py
    ├── mock_kap.py
    ├── mock_chromadb.py
    └── mock_gemini.py
```

### Running Tests

```bash
# Start test database
docker-compose -f docker-compose.test.yml up -d

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_main.py

# Run with verbose output
pytest -v

# Stop test database
docker-compose -f docker-compose.test.yml down
```

### Test Fixtures

Key fixtures in `conftest.py`:

- `app` — FastAPI application instance
- `client` — Async TestClient for API testing
- `test_db_url` — Test database URL (localhost:5434)
- `test_engine` — Async SQLAlchemy engine (when DB models exist)
- `test_session` — Async session with rollback per test

### Test Database

The test database uses:
- **Container name:** `finmatrix-test-db`
- **Port:** 5434 (external), 5432 (internal)
- **Storage:** tmpfs (in-memory, fast, auto-cleanup)
- **User/DB:** `finmatrix_test` / `finmatrix_test`

---

## Development Roadmap Summary

| Phase | Week | Focus | Status |
|-------|------|-------|--------|
| Phase 1 | Week 1-2 | Infrastructure & Database | ✅ Complete |
| Phase 2 | Week 3-4 | Data Pipeline & KAP Integration | Pending |
| Phase 3 | Week 5-6 | AI Chat & RAG Pipeline | Pending |
| Phase 4 | Week 7 | Frontend-Backend Integration | Pending |
| Phase 5 | Week 8 | EvalOps & Judge Agent | Pending |
| Phase 6 | Week 9 | Telegram Bot & Notifications | Pending |
| Phase 7 | Week 10 | Test, Deploy & Polish | Pending |

**Week 1 Complete (09-10.03.2026):**
- ✅ Task 1.1: Project Setup
- ✅ Task 1.2: Environment Configuration
- ✅ Task 1.3: Docker Setup
- ✅ Task 1.4: FastAPI Boilerplate
- ✅ Task 1.5: Test Infrastructure Setup (8 tests passing)

**Week 2 Complete (12.03.2026):**
- ✅ Task 2.1: Alembic Setup
- ✅ Task 2.2: SQLAlchemy Models — Users & Auth
- ✅ Task 2.3: SQLAlchemy Models — Stocks & Watchlist
- ✅ Task 2.4: SQLAlchemy Models — Financial Data
- ✅ Task 2.5: SQLAlchemy Models — KAP Reports & News
- ✅ Task 2.6: SQLAlchemy Models — Chat & AI Messages
- ✅ Task 2.7: SQLAlchemy Models — Eval & Pipeline Logs

**Total Estimated Effort:** ~125 hours over 10 weeks

---

## Key Implementation Notes

### Agent Flow (LangGraph Orchestrator)

```
START → Query Classifier
      → [text_analysis | numerical_analysis | comparison | general]
      → CrewAI (text) / AutoGen (numerical) / both (comparison)
      → Results Merger
      → Judge Agent (faithfulness/relevance/consistency check)
      → END (return response or retry)
```

### Judge Agent Thresholds

- **Score >= 6:** Response accepted
- **Score < 6:** Retry with expanded context (max 2 retries)
- After 2 failed retries: Return "Insufficient information found" message

### Chart Generation

- Charts are generated as **Chart.js config JSON** (not images)
- Frontend renders inline using Chart.js library
- Supported types: Line, Bar, Mixed
- Color palette is consistent per stock symbol

### KAP Document Processing

1. Scrape KAP filing from kap.org.tr
2. Download PDF
3. Extract text with PyMuPDF/pdfplumber
4. Split into chunks (~500 tokens, ~50 token overlap)
5. Store chunks in `document_chunks` table
6. Embed chunks and store in ChromaDB
7. Update `kap_reports.chroma_sync_status` to SUCCESS

### Turkish Language Considerations

- All AI responses are in Turkish
- PDF text extraction must handle Turkish characters (ş, ğ, ü, ö, ç, ı)
- System prompts explicitly require Turkish responses

---

## Testing Strategy

### Unit Tests
- Main app endpoints (health, root, CORS)
- Auth service (register, login, JWT)
- Stock service (queries, filtering)
- Watchlist service (CRUD operations)
- KAP scraper (HTML parsing, PDF download)
- Chunking service (text splitting)
- RAG retriever (similarity search)
- Query classifier
- Judge agent

### Integration Tests
- Auth flow (register → login → /me)
- Chat flow (session → message → AI response)
- Data pipeline (KAP → chunk → embed → retrieve)

### E2E Tests
- Full user journey (register → watchlist → chat → notification)

### Mocking Strategy
- `mock_yfinance.py`: Fake Yahoo Finance responses
- `mock_kap.py`: Fake KAP HTML and PDF
- `mock_chromadb.py`: In-memory ChromaDB
- `mock_gemini.py`: Fake LLM responses

### Factory Boy
Base factory class using `SQLAlchemyModelFactory`:
```python
from factory.alchemy import SQLAlchemyModelFactory

class BaseFactory(SQLAlchemyModelFactory):
    class Meta:
        sqlalchemy_session = None  # Set in tests
        sqlalchemy_session_persistence = "commit"
```

Async factory usage (since Factory Boy is sync):
```python
# Build and save manually
user = UserFactory.build()
async with session.begin():
    session.add(user)
    await session.commit()
```

---

## Security Considerations

### Authentication
- JWT tokens with 24-hour expiry
- Bcrypt password hashing
- Token refresh mechanism

### API Security
- Rate limiting (slowapi)
- Input validation (Pydantic)
- SQL injection prevention (SQLAlchemy parameterized queries)
- XSS prevention (response sanitization)

### Agent Security
- AutoGen code execution in sandboxed Docker container
- 30-second execution timeout
- Restricted filesystem and network access

---

## Code Style Guidelines

### Python (Backend)
- Use **async/await** for all database operations
- Use **Pydantic v2** for schemas
- Use **SQLAlchemy 2.0 style** (select(), where(), etc.)
- Type hints for all function signatures
- Docstrings for public functions
- Follow **PEP 8** formatting

### JavaScript (Frontend)
- Use **ES6+** syntax (arrow functions, const/let, template literals)
- Async/await for API calls
- Modular component structure
- No jQuery or external frameworks

### General
- **No buy/sell recommendations** in any AI response
- All monetary values in TL (Turkish Lira)
- All dates in Turkish format (DD.MM.YYYY)
- BIST trading hours: 10:00-18:00 TR time

---

## Common Tasks

### Adding a New Stock
```python
# scripts/seed_stocks.py
stocks = [
    {"symbol": "THYAO", "company_name": "Turk Hava Yollari AO", "sector": "Aviation"},
    {"symbol": "ASELS", "company_name": "Aselsan Elektronik", "sector": "Defense"},
    # ...
]
```

### Running Migrations
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

### Testing API Endpoints
- Swagger UI: `http://localhost:8002/docs`
- ReDoc: `http://localhost:8002/redoc`

---

## Troubleshooting

### ChromaDB Connection Issues
```bash
# Check if ChromaDB is running
curl http://localhost:8001/api/v1/heartbeat

# Restart ChromaDB
docker-compose restart vector
```

### Database Connection Issues
```bash
# Check PostgreSQL logs
docker-compose logs db

# Verify connection string
docker-compose exec api python -c "from app.config import settings; print(settings.database_url)"
```

### Container Won't Start
```bash
# Check logs
docker-compose logs api

# Rebuild without cache
docker-compose build --no-cache api
docker-compose up -d api
```

---

## References

- **KAP (Public Disclosure Platform):** https://kap.org.tr
- **yfinance Documentation:** https://github.com/ranaroussi/yfinance
- **FastAPI Documentation:** https://fastapi.tiangolo.com
- **LangGraph Documentation:** https://langchain-ai.github.io/langgraph/
- **CrewAI Documentation:** https://docs.crewai.com
- **AutoGen Documentation:** https://microsoft.github.io/autogen/
- **ChromaDB Documentation:** https://docs.trychroma.com