# FinMatrix — Development Roadmap 📊

> **Proje:** AI-Powered Stock Analysis Platform for BIST Investors
> **Başlangıç:** Mart 2026
> **Tahmini Süre:** 10 Hafta (Sprint bazlı)
> **Yazar:** Yiğitalp ([@alpbel0](https://github.com/alpbel0))

---

## Genel Bakış

| Phase | Hafta | Odak | Durum |
|-------|-------|------|-------|
| Phase 1 | Week 1–2 | Altyapı & Database | 🔄 Devam Ediyor (Week 1 ✅, Week 2 başladı) |
| Phase 2 | Week 3–4 | Data Pipeline & KAP Entegrasyonu | ⬜ |
| Phase 3 | Week 5–6 | AI Chat & RAG Pipeline | ⬜ |
| Phase 4 | Week 7 | Frontend–Backend Entegrasyonu | ⬜ |
| Phase 5 | Week 8 | EvalOps & Judge Agent | ⬜ |
| Phase 6 | Week 9 | Telegram Bot & Notification Sistemi | ⬜ |
| Phase 7 | Week 10 | Test, Deploy & Polish | ⬜ |

---

# Phase 1 — Altyapı & Database

---

## 📅 Week 1: Project Setup & Docker Infrastructure

**Tarih:** 09-10.03.2026
**Hedef:** Repo, Docker stack, PostgreSQL, ChromaDB ayağa kaldırma
**Durum:** ✅ Tamamlandı (Task 1.1-1.5 tamamlandı)

### Task 1.1: Project Setup

**Tahmini Süre:** 2 saat
**Durum:** ✅ Tamamlandı (09.03.2026)

- [x] GitHub repository oluştur (`FinMatrix`)
- [x] Ana klasör yapısını oluştur:
  ```
  FinMatrix/
  │
  ├── backend/
  │   ├── Dockerfile
  │   ├── requirements.txt
  │   ├── pyproject.toml
  │   │
  │   ├── app/
  │   │   ├── __init__.py
  │   │   ├── main.py                          # FastAPI app instance, lifespan, CORS, middleware
  │   │   ├── config.py                        # pydantic-settings: env variables, DB URL, API keys
  │   │   ├── database.py                      # AsyncSession factory, engine, Base declarative
  │   │   ├── dependencies.py                  # get_db, get_current_user, get_admin_user
  │   │   │
  │   │   ├── models/                          # SQLAlchemy ORM models
  │   │   │   ├── __init__.py                  # from .user import User; ... (tüm model importları)
  │   │   │   ├── user.py                      # users, telegram_settings
  │   │   │   ├── stock.py                     # stocks
  │   │   │   ├── watchlist.py                 # watchlist
  │   │   │   ├── stock_price.py               # stock_prices (partitioned)
  │   │   │   ├── balance_sheet.py             # balance_sheets
  │   │   │   ├── income_statement.py          # income_statements
  │   │   │   ├── cash_flow.py                 # cash_flows
  │   │   │   ├── kap_report.py                # kap_reports + sync_status ENUM
  │   │   │   ├── news.py                      # news, user_news + news_source ENUM
  │   │   │   ├── chat.py                      # chat_sessions, chat_messages + ENUM'lar
  │   │   │   ├── document_chunk.py            # document_chunks + embedding_status ENUM
  │   │   │   ├── pipeline_log.py              # pipeline_logs + pipeline_status ENUM
  │   │   │   └── eval_log.py                  # eval_logs + hallucination_reports VIEW
  │   │   │
  │   │   ├── schemas/                         # Pydantic request/response modelleri
  │   │   │   ├── __init__.py
  │   │   │   ├── auth.py                      # RegisterRequest, LoginRequest, TokenResponse, UserResponse
  │   │   │   ├── stock.py                     # StockResponse, StockDetail, StockMetrics, StockPricePoint
  │   │   │   ├── watchlist.py                 # WatchlistItem, WatchlistAdd, WatchlistStats
  │   │   │   ├── news.py                      # NewsItem, NewsFilter, NewsDetail
  │   │   │   ├── chat.py                      # ChatSessionResponse, MessageRequest, MessageResponse, ChartConfig, SourceRef
  │   │   │   ├── financials.py                # IncomeStatementResponse, BalanceSheetResponse, CashFlowResponse, QuarterlyProfit
  │   │   │   ├── eval.py                      # EvalStats, HallucinationReport, PipelineLogResponse
  │   │   │   └── telegram.py                  # TelegramLink, NotificationPreferences
  │   │   │
  │   │   ├── routers/                         # FastAPI route handlers
  │   │   │   ├── __init__.py
  │   │   │   ├── auth.py                      # POST /register, /login — GET /me
  │   │   │   ├── stocks.py                    # GET /stocks, /stocks/{symbol}, /stocks/{symbol}/prices, /metrics, /quarterly, /financials, /kap-reports
  │   │   │   ├── watchlist.py                 # GET/POST/DELETE /watchlist — PATCH /watchlist/{id}/notifications
  │   │   │   ├── news.py                      # GET /news, /news/{id} — POST /news/{id}/read
  │   │   │   ├── chat.py                      # CRUD /chat/sessions — POST /messages — SSE /messages/stream
  │   │   │   └── admin.py                     # GET /admin/eval/stats, /hallucinations, /pipeline-logs (admin-only)
  │   │   │
  │   │   ├── services/                        # İş mantığı katmanı
  │   │   │   ├── __init__.py
  │   │   │   ├── auth_service.py              # password hash/verify, JWT create/decode
  │   │   │   ├── stock_service.py             # DB query helpers: get_stock, list_stocks, search
  │   │   │   ├── watchlist_service.py         # add/remove/list watchlist, stats hesapla
  │   │   │   ├── news_service.py              # news listele, filtrele, okundu işaretle, KAP→news dönüştür
  │   │   │   ├── chat_service.py              # session CRUD, mesaj kaydet, conversation context builder
  │   │   │   │
  │   │   │   ├── data/                        # Harici veri çekme servisleri
  │   │   │   │   ├── __init__.py
  │   │   │   │   ├── yfinance_service.py      # Fiyat geçmişi, metrikler, financial statements çek
  │   │   │   │   ├── kap_service.py           # kap.org.tr scraper: bildirimleri çek, PDF indir
  │   │   │   │   └── bist_service.py          # BIST100 index, sektör performansı, top gainers/losers
  │   │   │   │
  │   │   │   ├── pipeline/                    # Data processing pipeline
  │   │   │   │   ├── __init__.py
  │   │   │   │   ├── chunking_service.py      # PDF → text → chunk (500 token, 50 overlap)
  │   │   │   │   ├── embedding_service.py     # Chunk → ChromaDB embedding (batch)
  │   │   │   │   ├── sync_service.py          # PENDING chunk/report'ları işle, status güncelle
  │   │   │   │   └── scheduler.py             # APScheduler: fiyat/KAP/embedding/digest job'ları
  │   │   │   │
  │   │   │   ├── rag/                         # Retrieval-Augmented Generation
  │   │   │   │   ├── __init__.py
  │   │   │   │   ├── retriever.py             # ChromaDB similarity search + metadata filter
  │   │   │   │   ├── reranker.py              # Top-K sonuçları LLM ile re-rank
  │   │   │   │   └── context_builder.py       # Retrieved chunk'ları prompt formatına çevir
  │   │   │   │
  │   │   │   ├── agents/                      # Multi-agent sistemi
  │   │   │   │   ├── __init__.py
  │   │   │   │   ├── orchestrator.py          # LangGraph state graph: route → agents → merge → judge
  │   │   │   │   ├── query_classifier.py      # User query → type: text/numerical/comparison/general
  │   │   │   │   ├── text_analyst.py          # CrewAI agent: KAP raporlarını yorumla
  │   │   │   │   ├── code_executor.py         # AutoGen agent: metrik hesapla, chart data üret
  │   │   │   │   ├── merger.py                # Agent çıktılarını birleştir, source deduplicate
  │   │   │   │   └── judge.py                 # Judge Agent: faithfulness/relevance/consistency skoru
  │   │   │   │
  │   │   │   ├── eval/                        # EvalOps — halüsinasyon tespiti
  │   │   │   │   ├── __init__.py
  │   │   │   │   ├── metrics.py               # BERTScore, ROUGE, retrieval score hesapla
  │   │   │   │   ├── judge_evaluator.py       # Judge Agent wrapper: score → is_hallucinated karar
  │   │   │   │   └── retry_handler.py         # Score düşükse context genişlet ve tekrar dene
  │   │   │   │
  │   │   │   ├── chart_service.py             # Chart.js config JSON üret (line/bar/mixed)
  │   │   │   ├── notification_service.py      # Bildirim tetikleme: KAP→kullanıcı eşleştir→gönder
  │   │   │   └── telegram_service.py          # Telegram Bot API: /start, /link, mesaj gönder
  │   │   │
  │   │   ├── utils/                           # Yardımcı araçlar
  │   │   │   ├── __init__.py
  │   │   │   ├── logger.py                    # Structured logging config (loguru)
  │   │   │   ├── security.py                  # JWT encode/decode, bcrypt hash/verify
  │   │   │   ├── rate_limiter.py              # API rate limiting (slowapi)
  │   │   │   ├── exceptions.py                # Custom exception'lar: NotFoundError, AuthError, vb.
  │   │   │   ├── constants.py                 # BIST saatleri, sektör listesi, default config'ler
  │   │   │   └── helpers.py                   # Ortak utility fonksiyonlar (date format, currency, vb.)
  │   │   │
  │   │   └── prompts/                         # LLM prompt template'leri
  │   │       ├── system_prompt.txt            # Ana system prompt (rol, kurallar, Türkçe, no buy/sell)
  │   │       ├── judge_prompt.txt             # Judge Agent değerlendirme prompt'u
  │   │       ├── text_analyst_prompt.txt      # CrewAI text analyst prompt'u
  │   │       ├── code_executor_prompt.txt     # AutoGen code executor prompt'u
  │   │       ├── query_classifier_prompt.txt  # Query type sınıflandırma prompt'u
  │   │       └── summary_prompt.txt           # Context özetleme prompt'u (uzun sohbetler için)
  │   │
  │   ├── alembic/                             # Database migration'ları
  │   │   ├── alembic.ini
  │   │   ├── env.py                           # Async engine config, target_metadata
  │   │   ├── script.py.mako                   # Migration template
  │   │   └── versions/                        # Auto-generated migration dosyaları
  │   │       ├── 001_initial_schema.py
  │   │       ├── 002_seed_bist_stocks.py
  │   │       └── ...
  │   │
  │   ├── scripts/                             # Utility script'ler (one-off)
  │   │   ├── seed_stocks.py                   # 20+ BIST hissesini DB'ye ekle
  │   │   ├── backfill_prices.py               # Geçmiş fiyat verisini toplu çek
  │   │   ├── backfill_financials.py           # Geçmiş financial statements toplu çek
  │   │   ├── reindex_chromadb.py              # Tüm chunk'ları tekrar embed et
  │   │   └── create_partitions.py             # stock_prices tablo partition'larını oluştur
  │   │
  │   └── tests/                               # Backend testleri
  │       ├── __init__.py
  │       ├── conftest.py                      # Test DB, fixtures, mock factory, TestClient
  │       ├── factories.py                     # Factory Boy: UserFactory, StockFactory, vb.
  │       │
  │       ├── unit/                            # Birim testler
  │       │   ├── __init__.py
  │       │   ├── test_auth_service.py
  │       │   ├── test_stock_service.py
  │       │   ├── test_watchlist_service.py
  │       │   ├── test_chat_service.py
  │       │   ├── test_yfinance_service.py
  │       │   ├── test_kap_service.py
  │       │   ├── test_chunking_service.py
  │       │   ├── test_embedding_service.py
  │       │   ├── test_retriever.py
  │       │   ├── test_query_classifier.py
  │       │   ├── test_judge.py
  │       │   ├── test_metrics.py
  │       │   ├── test_chart_service.py
  │       │   └── test_notification_service.py
  │       │
  │       ├── integration/                     # Entegrasyon testler
  │       │   ├── __init__.py
  │       │   ├── test_auth_flow.py            # Register → Login → Token → /me
  │       │   ├── test_stock_api.py
  │       │   ├── test_watchlist_api.py
  │       │   ├── test_chat_api.py
  │       │   ├── test_news_api.py
  │       │   ├── test_data_pipeline.py        # KAP → chunk → embed → retrieve
  │       │   └── test_eval_pipeline.py        # Query → response → judge → retry
  │       │
  │       ├── e2e/                             # End-to-end testler
  │       │   ├── __init__.py
  │       │   └── test_full_flow.py            # Register → Watchlist → Chat → Notification
  │       │
  │       └── mocks/                           # Mock data & fixtures
  │           ├── __init__.py
  │           ├── mock_yfinance.py             # Fake yfinance responses
  │           ├── mock_kap.py                  # Fake KAP HTML + PDF
  │           ├── mock_chromadb.py             # In-memory ChromaDB
  │           ├── mock_gemini.py               # Fake LLM responses
  │           └── sample_data/
  │               ├── thyao_kap_report.pdf     # Test PDF dosyası
  │               ├── sample_chunks.json       # Pre-generated chunk'lar
  │               └── sample_financials.json   # Fake financial data
  │
  ├── frontend/
  │   ├── index.html                           # News Feed sayfası (ana sayfa)
  │   ├── dashboard.html                       # Stock Dashboard sayfası
  │   ├── chat.html                            # AI Chat sayfası
  │   ├── watchlist.html                       # Watchlist sayfası
  │   ├── login.html                           # Login sayfası
  │   ├── register.html                        # Register sayfası
  │   │
  │   ├── css/
  │   │   ├── main.css                         # Global stiller, CSS variables, typography
  │   │   ├── components.css                   # Reusable component stilleri (cards, buttons, modals, badges)
  │   │   ├── news.css                         # News Feed sayfası stilleri
  │   │   ├── dashboard.css                    # Stock Dashboard stilleri
  │   │   ├── chat.css                         # Chat interface stilleri (bubbles, sidebar, streaming)
  │   │   ├── watchlist.css                    # Watchlist kartları, sparkline stilleri
  │   │   └── auth.css                         # Login/register form stilleri
  │   │
  │   ├── js/
  │   │   ├── api.js                           # Base API client: fetch wrapper, auth header, error handling
  │   │   ├── auth.js                          # JWT token yönetimi, login/register logic, protected route guard
  │   │   ├── news.js                          # News Feed: API call, kategori filtre, infinite scroll
  │   │   ├── dashboard.js                     # Stock Dashboard: arama, fiyat chart, metrik kartlar, financials tablo
  │   │   ├── chat.js                          # Chat: session yönetimi, SSE streaming, inline chart render, source panel
  │   │   ├── watchlist.js                     # Watchlist: kart render, sparkline, add/remove, notification toggle
  │   │   │
  │   │   ├── components/                      # Reusable JS bileşenleri
  │   │   │   ├── chart-factory.js             # Chart.js instance oluşturucu (line, bar, mixed, sparkline)
  │   │   │   ├── stock-search.js              # Autocomplete hisse arama widget'ı
  │   │   │   ├── notification-toast.js        # Toast notification bileşeni
  │   │   │   ├── loading-skeleton.js          # Skeleton loading placeholder'ları
  │   │   │   ├── empty-state.js               # Boş durum mesajları
  │   │   │   └── modal.js                     # Genel modal bileşeni (add stock, confirm delete, vb.)
  │   │   │
  │   │   └── utils/
  │   │       ├── constants.js                 # API_BASE_URL, chart renkleri, timeframe'ler
  │   │       ├── formatters.js                # Para formatı, tarih formatı, yüzde, kısaltma (1.2M, 3.4B)
  │   │       └── validators.js                # Email, password, symbol validation
  │   │
  │   └── assets/
  │       ├── img/
  │       │   ├── logo.svg                     # FinMatrix logosu
  │       │   ├── logo-dark.svg                # Dark mode logo
  │       │   ├── favicon.ico
  │       │   ├── og-image.png                 # Social media preview image
  │       │   └── empty-states/
  │       │       ├── no-watchlist.svg
  │       │       ├── no-chat.svg
  │       │       └── no-results.svg
  │       └── fonts/                           # Custom fontlar (varsa)
  │
  ├── docs/
  │   ├── screenshots/                         # Her sayfa için UI screenshot'ları
  │   │   ├── news-feed.png
  │   │   ├── stock-dashboard.png
  │   │   ├── ai-chat.png
  │   │   ├── watchlist.png
  │   │   └── telegram-bot.png
  │   ├── diagrams/
  │   │   ├── architecture.mermaid             # Sistem mimarisi (frontend ↔ backend ↔ DB ↔ ChromaDB)
  │   │   ├── agent-flow.mermaid               # LangGraph → CrewAI / AutoGen → Judge akışı
  │   │   ├── data-pipeline.mermaid            # KAP scrape → chunk → embed → retrieve
  │   │   └── er-diagram.mermaid               # Database ER diyagramı
  │   ├── api/
  │   │   └── openapi.json                     # Swagger'dan export (auto-generated)
  │   ├── FinMatrix_Planning_Document.pdf
  │   └── DEPLOYMENT.md                        # Production deploy rehberi
  │
  ├── infra/                                   # DevOps & deployment config'leri
  │   ├── nginx/
  │   │   └── nginx.conf                       # Reverse proxy config (production)
  │   ├── scripts/
  │   │   ├── backup_postgres.sh               # PostgreSQL günlük backup script'i
  │   │   └── health_check.sh                  # Container health check script'i
  │   └── github/
  │       └── workflows/
  │           ├── ci.yml                       # GitHub Actions: lint → test → build
  │           └── deploy.yml                   # GitHub Actions: deploy to production
  │
  ├── docker-compose.yml                       # Development: api + postgres + chromadb
  ├── docker-compose.prod.yml                  # Production: resource limits, restart policies
  ├── .env.example                             # Tüm env variable'ların template'i
  ├── .gitignore
  ├── .dockerignore
  ├── Makefile                                 # Kısayollar: make up, make down, make test, make seed, make migrate
  ├── README.md
  └── ROADMAP.md
  ```
- [x] `.gitignore` dosyası ekle (Python, Node, Docker, .env, __pycache__, chroma_data/)
- [x] `README.md` ilk taslağını yaz
- [x] Initial commit & push

### Task 1.2: Environment Configuration

**Tahmini Süre:** 1 saat
**Durum:** ✅ Tamamlandı (09.03.2026)

- [x] `.env.example` oluştur (tüm environment variables ile)
- [x] `.env` dosyası oluştur ve `.gitignore`'da olduğunu doğrula
- [x] API key placeholder'ları ekle:
  - [x] `GOOGLE_API_KEY` (Gemini Flash)
  - [x] `OPENAI_API_KEY` (Judge Agent fallback)
  - [x] `DATABASE_URL` (PostgreSQL connection string)
  - [x] `CHROMA_HOST` / `CHROMA_PORT`
  - [x] `TELEGRAM_BOT_TOKEN`
  - [x] `SECRET_KEY` (JWT auth)
- [x] `config.py` modülünü yaz (pydantic-settings ile env okuma)

### Task 1.3: Docker Setup

**Tahmini Süre:** 3 saat
**Durum:** ✅ Tamamlandı (09.03.2026)

- [x] `backend/Dockerfile` oluştur (Python 3.11-slim base image)
- [x] `.dockerignore` oluştur
- [x] `requirements.txt` oluştur (fastapi, uvicorn, sqlalchemy, alembic, asyncpg, chromadb, httpx, pydantic-settings)
- [x] `docker-compose.yml` oluştur — 3 servis:
  - [x] `finmatrix-api` → FastAPI backend (port 8002 → container:8000)
  - [x] `finmatrix-db` → PostgreSQL 15 (port 5433 → container:5432)
  - [x] `finmatrix-vector` → ChromaDB (port 8001 → container:8000)
- [x] Volume tanımları ekle (`postgres_data`, `chroma_data`)
- [x] `docker-compose build` ile build al — hatasız geçtiğini doğrula
- [x] `docker-compose up -d` ile container'ları başlat
- [x] `docker-compose ps` ile 3 servisin de "Up" olduğunu kontrol et
- [x] `curl http://localhost:8002/health` ile backend'e erişimi test et
- [x] ChromaDB v2 API erişimi mevcut (port 8001)

### Task 1.4: FastAPI Boilerplate

**Tahmini Süre:** 2 saat
**Durum:** ✅ Tamamlandı (09.03.2026)

- [x] `backend/app/main.py` — FastAPI app instance, CORS middleware, health endpoint
- [x] Router yapısını kur (`routers/` altında boş dosyalar):
  - [x] `auth.py`
  - [x] `stocks.py`
  - [x] `watchlist.py`
  - [x] `chat.py`
  - [x] `news.py`
- [x] Swagger UI çalışıyor mu kontrol et → `http://localhost:8002/docs`
- [x] ReDoc çalışıyor mu kontrol et → `http://localhost:8002/redoc`
- [x] Structured logging ayarla (loguru)
- [x] Global exception handler middleware ekle
- [x] Custom exception sınıfları oluştur (`utils/exceptions.py`)

### Task 1.5: Test Infrastructure Setup

**Tahmini Süre:** 1.5 saat
**Durum:** ✅ Tamamlandı (10.03.2026)

- [x] `tests/` klasör yapısını oluştur:
  - [x] `tests/__init__.py`
  - [x] `tests/conftest.py` — async fixtures, TestClient, test DB URL
  - [x] `tests/unit/` — birim testler
  - [x] `tests/integration/` — entegrasyon testleri
  - [x] `tests/mocks/` — mock data ve fixtures
  - [x] `tests/e2e/` — end-to-end testler
- [x] pytest + pytest-asyncio + httpx (TestClient) kur
- [x] pytest-cov (coverage reporting) ekle
- [x] factory-boy (test data factories) ekle
- [x] testcontainers (Docker test containers) ekle
- [x] `pytest.ini` oluştur — async mode, coverage config
- [x] `docker-compose.test.yml` oluştur — test PostgreSQL (port 5434, tmpfs)
- [x] `backend/tests/conftest.py` içine:
  - [x] `app` fixture (FastAPI app)
  - [x] `client` fixture (async TestClient)
  - [x] `test_db_url` fixture
  - [x] Commented fixtures for when DB is implemented
- [x] `tests/factories.py` oluştur — base factory class
- [x] İlk unit test: `tests/unit/test_main.py` — 8 test (health, root, CORS, exception handling)
- [x] `pytest` komutunun çalıştığını doğrula — 8 passed, 80% coverage
- [x] Test DB container'ı başlat (`finmatrix-test-db`)

---

## 📅 Week 2: Database Schema & Migrations

**Tarih:** 12-?.03.2026
**Hedef:** Tüm tabloları oluştur, Alembic migration pipeline'ını kur

### Task 2.1: Alembic Setup

**Tahmini Süre:** 1.5 saat
**Durum:** ✅ Tamamlandı (12.03.2026)

- [x] `backend/app/database.py` oluştur (async engine, session factory, Base)
- [x] `alembic.ini` oluştur (config, logging)
- [x] `alembic/env.py` oluştur (async engine desteği)
- [x] `alembic/script.py.mako` oluştur (migration template)
- [x] `alembic/versions/.gitkeep` oluştur
- [x] `models/__init__.py` güncelle (Base import)
- [x] Stale `__pycache__` dizinlerini temizle
- [x] Test migration oluştur: `init_alembic_setup`
- [x] `alembic upgrade head` ile migration'ın uygulandığını doğrula
- [x] `alembic downgrade -1` ile rollback'in çalıştığını doğrula

### Task 2.2: SQLAlchemy Models — Users & Auth

**Tahmini Süre:** 2 saat
**Durum:** ✅ Tamamlandı (12.03.2026)

- [x] `models/user.py` → `users` ve `telegram_settings` tabloları (tek dosyada)
  - [x] `users`: id, username (unique), email (unique), password_hash, telegram_chat_id, notification_enabled, created_at, updated_at
  - [x] `telegram_settings`: user_id (FK, PK), notification_times (JSONB), event_types (JSONB)
  - [x] One-to-one relationship (back_populates)
- [x] Index: `idx_users_email` on `users(email)`
- [x] Migration oluştur ve uygula
- [x] `psql` ile tabloların oluştuğunu doğrula

> **Not:** Her iki model de `user.py` dosyasında tanımlandı. Daha temiz import ve relationship yönetimi için tek dosya yaklaşımı kullanıldı.

### Task 2.3: SQLAlchemy Models — Stocks & Watchlist

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] `models/stock.py` → `stocks` tablosu
  - [ ] id, symbol (unique), yfinance_symbol, company_name, sector, exchange (default 'BIST'), is_active, created_at
- [ ] `models/watchlist.py` → `watchlist` tablosu
  - [ ] user_id (FK), stock_id (FK), added_at, notification_enabled
  - [ ] UNIQUE(user_id, stock_id) constraint
- [ ] Index: `idx_watchlist_user` on `watchlist(user_id)`
- [ ] Migration oluştur ve uygula
- [ ] Seed data: En az 20 popüler BIST hissesi ekle (THYAO, ASELS, GARAN, BIMAS, SISE, EREGL, KCHOL, AKBNK, TUPRS, SAHOL, TOASO, FROTO, TCELL, HEKTS, PGSUS, KOZAA, SASA, ENKAI, TAVHL, PETKM)

### Task 2.4: SQLAlchemy Models — Financial Data

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `models/stock_prices.py` → `stock_prices` tablosu
  - [ ] stock_id, timestamp, open, high, low, close, volume
  - [ ] PRIMARY KEY (stock_id, timestamp)
  - [ ] PARTITION BY RANGE (timestamp) — aylık partition
- [ ] `models/balance_sheet.py` → `balance_sheets` tablosu
  - [ ] stock_id, period, date, fiscal_year, fiscal_quarter, total_assets, total_liabilities, equity, cash, total_debt
  - [ ] UNIQUE(stock_id, period, date)
- [ ] `models/income_statement.py` → `income_statements` tablosu
  - [ ] stock_id, period, date, fiscal_year, fiscal_quarter, revenue, net_income, operating_income, gross_profit, ebitda
  - [ ] UNIQUE(stock_id, period, date)
- [ ] `models/cash_flow.py` → `cash_flows` tablosu
  - [ ] stock_id, period, date, fiscal_year, fiscal_quarter, operating_cash_flow, investing_cash_flow, financing_cash_flow, free_cash_flow
  - [ ] UNIQUE(stock_id, period, date)
- [ ] Index: `idx_stock_prices_stock_time` on `stock_prices(stock_id, timestamp)`
- [ ] Migration oluştur ve uygula
- [ ] Partition oluşturma SQL scriptini yaz (son 2 yıl + gelecek 6 ay)

### Task 2.5: SQLAlchemy Models — KAP Reports & News

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] Custom ENUM type'ları tanımla: `sync_status`, `news_source`
- [ ] `models/kap_report.py` → `kap_reports` tablosu
  - [ ] stock_id, title, pdf_url, published_date, fetched_date, chroma_sync_status (PENDING/SUCCESS/FAILED), chunk_count
  - [ ] UNIQUE(stock_id, title, published_date)
- [ ] `models/news.py` → `news` tablosu
  - [ ] stock_id (nullable FK), title, content, published_date, source_type (kap_summary/external_news/manual), source_ref_id
- [ ] `models/user_news.py` → `user_news` tablosu
  - [ ] user_id, news_id, is_read, read_at
  - [ ] UNIQUE(user_id, news_id)
- [ ] Migration oluştur ve uygula

### Task 2.6: SQLAlchemy Models — Chat & AI Messages

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] Custom ENUM'lar: `message_role` (user/assistant/system), `message_type` (text/chart/table/system)
- [ ] `models/chat_session.py` → `chat_sessions` tablosu
  - [ ] user_id (FK), title, created_at, updated_at, last_message_at
- [ ] `models/chat_message.py` → `chat_messages` tablosu
  - [ ] session_id (FK), role, content, message_type, metadata (JSONB), sources (JSONB), timestamp
- [ ] Custom ENUM: `embedding_status` (PENDING/SUCCESS/FAILED)
- [ ] `models/document_chunk.py` → `document_chunks` tablosu
  - [ ] kap_report_id (FK), chunk_index, chunk_text_hash, chroma_document_id, embedding_status
  - [ ] UNIQUE(kap_report_id, chunk_index)
- [ ] Index: `idx_chat_messages_session` on `chat_messages(session_id, timestamp)`
- [ ] Index: `idx_document_chunks_report` on `document_chunks(kap_report_id)`
- [ ] Migration oluştur ve uygula

### Task 2.7: SQLAlchemy Models — EvalOps & Pipeline

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] Custom ENUM: `pipeline_status` (PENDING/RUNNING/SUCCESS/FAILED)
- [ ] `models/pipeline_log.py` → `pipeline_logs` tablosu
  - [ ] run_id (UUID, unique), pipeline_name, job_name, step_name, stock_id (nullable), status, started_at, finished_at, error_message, processed_count, details (JSONB)
- [ ] `models/eval_log.py` → `eval_logs` tablosu
  - [ ] message_id (FK), pipeline_run_id (FK to run_id), bert_score, rouge_score, retrieval_score, judge_model_used, judge_reason, is_hallucinated, retry_count, source_chunks_used (JSONB), details (JSONB)
- [ ] `hallucination_reports` VIEW oluştur → `SELECT * FROM eval_logs WHERE is_hallucinated = TRUE`
- [ ] Index: `idx_eval_hallucinated` on `eval_logs(is_hallucinated, pipeline_run_id)`
- [ ] Index: `idx_pipeline_logs_run_id` on `pipeline_logs(run_id)`
- [ ] Migration oluştur ve uygula
- [ ] Tüm tabloların listesini `\dt` ile kontrol et — 14 tablo + 1 view olmalı

---

# Phase 2 — Data Pipeline & KAP Entegrasyonu

---

## 📅 Week 3: yfinance & KAP Data Ingestion

**Tarih:** \_\_\_\_\_\_\_\_\_\_
**Hedef:** Hisse fiyatları ve KAP raporlarını otomatik çek, veritabanına yaz

### Task 3.1: yfinance Data Service

**Tahmini Süre:** 4 saat
**Durum:** ⬜

- [ ] `services/yfinance_service.py` oluştur
- [ ] Tek hisse için fiyat geçmişi çekme fonksiyonu (symbol → DataFrame)
  - [ ] `.IS` suffix'ini otomatik ekle (THYAO → THYAO.IS)
  - [ ] Timeframe parametresi: 1d, 5d, 1mo, 3mo, 6mo, 1y, 5y
- [ ] Tek hisse için temel metrikleri çekme (marketCap, trailingPE, returnOnEquity, vb.)
- [ ] Batch fonksiyonu: Tüm aktif hisseler için fiyat güncelleme
- [ ] `stock_prices` tablosuna yazma (upsert — duplicate'leri atla)
- [ ] Rate limiting ekle (Yahoo Finance throttle'a takılmamak için)
- [ ] Error handling: Sembol bulunamazsa, API timeout olursa
- [ ] Test: THYAO, GARAN, ASELS için son 1 yıllık veri çek ve DB'ye yaz
- [ ] Logları kontrol et — başarılı kayıt sayısını doğrula

### Task 3.2: Financial Statements Service

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `services/financials_service.py` oluştur
- [ ] yfinance `.financials`, `.quarterly_financials`, `.balance_sheet`, `.cashflow` verilerini parse et
- [ ] `income_statements` tablosuna yaz (annual + quarterly)
- [ ] `balance_sheets` tablosuna yaz (annual + quarterly)
- [ ] `cash_flows` tablosuna yaz (annual + quarterly)
- [ ] Upsert mantığı: Aynı (stock_id, period, date) varsa güncelle
- [ ] Test: En az 5 hisse için financial statements'ı çek ve doğrula
- [ ] Quarterly net profit verilerinin son 8 çeyrek için geldiğini doğrula (dashboard chart için kritik)

### Task 3.3: KAP Report Scraper

**Tahmini Süre:** 5 saat
**Durum:** ⬜

- [ ] `services/kap_service.py` oluştur
- [ ] kap.org.tr'den bildirimleri çekme fonksiyonu (httpx + BeautifulSoup/Selectolax)
  - [ ] Hisse bazlı filtreleme (symbol parametresi)
  - [ ] Tarih aralığı parametresi
- [ ] PDF URL'lerini parse et
- [ ] PDF'leri indir ve geçici dizine kaydet
- [ ] `kap_reports` tablosuna metadata yaz (title, pdf_url, published_date, chroma_sync_status=PENDING)
- [ ] Duplicate kontrolü: Aynı (stock_id, title, published_date) varsa atla
- [ ] Error handling: PDF indirilemezse status'u FAILED yap
- [ ] Test: THYAO için son 10 KAP bildirimini çek, DB'ye yaz, PDF'leri kontrol et
- [ ] Rate limiting: kap.org.tr'ye aşırı istek atmayı engelle (1 req/2sec)

### Task 3.4: PDF Text Extraction & Chunking

**Tahmini Süre:** 4 saat
**Durum:** ⬜

- [ ] `services/chunking_service.py` oluştur
- [ ] PDF → text çıkarma (PyMuPDF/fitz veya pdfplumber)
- [ ] Türkçe karakter desteğini test et (ş, ğ, ü, ö, ç, ı)
- [ ] Text'i chunk'lara böl:
  - [ ] Chunk size: ~500 token
  - [ ] Overlap: ~50 token
  - [ ] Paragraf sınırlarına saygı gösteren splitting
- [ ] Her chunk için hash hesapla (`chunk_text_hash`)
- [ ] `document_chunks` tablosuna yaz (kap_report_id, chunk_index, chunk_text_hash, embedding_status=PENDING)
- [ ] `kap_reports.chunk_count` alanını güncelle
- [ ] Test: 3 farklı KAP PDF'i için chunk'ları oluştur, sayıları ve içerikleri doğrula

### Task 3.5: ChromaDB Embedding Pipeline

**Tahmini Süre:** 4 saat
**Durum:** ⬜

- [ ] `services/embedding_service.py` oluştur
- [ ] ChromaDB client bağlantısı (`http://finmatrix-vector:8001`)
- [ ] Collection oluştur: `kap_documents`
- [ ] Embedding modeli seç ve konfigüre et (sentence-transformers veya OpenAI embedding)
- [ ] PENDING status'teki chunk'ları batch olarak embed et ve ChromaDB'ye yaz
- [ ] Her chunk için metadata ekle: stock_symbol, report_title, published_date, chunk_index
- [ ] `document_chunks.chroma_document_id` alanını güncelle
- [ ] `document_chunks.embedding_status` → SUCCESS yap
- [ ] `kap_reports.chroma_sync_status` → SUCCESS yap (tüm chunk'lar başarılıysa)
- [ ] Test: ChromaDB'den bir query at ("THYAO net kar"), ilgili chunk'ların döndüğünü doğrula
- [ ] Hata durumunda embedding_status → FAILED yap, error logla

### Task 3.6: Data Services Unit Tests

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `tests/mocks/mock_yfinance.py` → Fake yfinance responses (fixture data)
- [ ] `tests/mocks/mock_kap.py` → Fake KAP HTML responses + sample PDF
- [ ] `tests/mocks/mock_chromadb.py` → In-memory ChromaDB for testing
- [ ] `tests/unit/test_yfinance_service.py`:
  - [ ] Test: Symbol suffix (.IS) auto-add
  - [ ] Test: Price history fetching
  - [ ] Test: Error handling (symbol not found, timeout)
  - [ ] Test: Batch update with rate limiting
- [ ] `tests/unit/test_kap_service.py`:
  - [ ] Test: KAP HTML parsing
  - [ ] Test: PDF download and storage
  - [ ] Test: Duplicate detection
  - [ ] Test: Rate limiting compliance
- [ ] `tests/unit/test_chunking_service.py`:
  - [ ] Test: PDF text extraction (Turkish characters)
  - [ ] Test: Chunk size and overlap
  - [ ] Test: Hash calculation
- [ ] `tests/unit/test_embedding_service.py`:
  - [ ] Test: ChromaDB connection
  - [ ] Test: Batch embedding
  - [ ] Test: Status updates (SUCCESS/FAILED)
- [ ] `pytest tests/unit/` ile tüm testlerin geçtiğini doğrula

---

## 📅 Week 4: Data Sync Jobs & API Endpoints (Stocks/Watchlist)

**Tarih:** \_\_\_\_\_\_\_\_\_\_
**Hedef:** Otomatik data sync, ilk REST API endpoint'leri

### Task 4.1: Scheduled Data Sync

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `services/scheduler.py` oluştur (APScheduler veya custom async loop)
- [ ] Job 1: Hisse fiyatlarını güncelle — her 15 dakikada (borsa açıkken)
- [ ] Job 2: Financial statements güncelle — günde 1 kez (gece)
- [ ] Job 3: KAP bildirimleri kontrol — her 30 dakikada
- [ ] Job 4: PENDING chunk'ları embed et — her 10 dakikada
- [ ] Her job için `pipeline_logs` tablosuna kayıt yaz (run_id, status, timestamps, processed_count)
- [ ] Hata durumunda `pipeline_logs.error_message` doldur, status=FAILED
- [ ] İş saatleri dışında fiyat güncellemeyi devre dışı bırak (BIST: 10:00–18:00 TR saati)
- [ ] Test: Scheduler'ı başlat, 1 saat çalıştır, pipeline_logs'u kontrol et

### Task 4.2: Auth API — Register & Login

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `routers/auth.py` endpoint'lerini yaz
- [ ] `POST /api/auth/register` → username, email, password → user oluştur
  - [ ] Password hashing (bcrypt)
  - [ ] Duplicate email/username kontrolü
  - [ ] Validation (Pydantic schema)
- [ ] `POST /api/auth/login` → email + password → JWT token döndür
  - [ ] JWT token oluşturma (python-jose)
  - [ ] Token expiry: 24 saat
- [ ] `GET /api/auth/me` → Token ile current user bilgisi
- [ ] Auth middleware/dependency oluştur (`get_current_user`)
- [ ] Swagger UI'da test et: register → login → token al → /me ile doğrula

### Task 4.3: Stocks API

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `routers/stocks.py` endpoint'lerini yaz
- [ ] `GET /api/stocks` → Tüm aktif hisseleri listele (pagination, search by symbol/name)
- [ ] `GET /api/stocks/{symbol}` → Tek hisse detay (company_name, sector, son fiyat)
- [ ] `GET /api/stocks/{symbol}/prices` → Fiyat geçmişi (timeframe query param: 1d/1w/3m/6m/1y/5y)
- [ ] `GET /api/stocks/{symbol}/financials` → Son 3 yıl: revenue, net_income, ebitda, total_assets, equity
- [ ] `GET /api/stocks/{symbol}/quarterly` → Son 8 çeyrek net profit (dashboard chart için)
- [ ] `GET /api/stocks/{symbol}/metrics` → Anlık metrikler: marketCap, P/E, ROE + sektör ortalaması karşılaştırma
- [ ] `GET /api/stocks/{symbol}/kap-reports` → İlgili KAP bildirimleri listesi
- [ ] Response schema'ları tanımla (Pydantic models)
- [ ] Her endpoint için Swagger'da test et

### Task 4.4: Watchlist API

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] `routers/watchlist.py` endpoint'lerini yaz
- [ ] `GET /api/watchlist` → Kullanıcının watchlist'i (canlı fiyat + değişim % ile)
- [ ] `POST /api/watchlist` → Hisse ekle (stock_id)
- [ ] `DELETE /api/watchlist/{stock_id}` → Hisse kaldır
- [ ] `PATCH /api/watchlist/{stock_id}/notifications` → Bildirim toggle (notification_enabled)
- [ ] Watchlist summary stats endpoint: toplam hisse, bugünkü kazananlar, kaybedenler, aktif alarm sayısı
- [ ] Auth required: Tüm endpoint'ler JWT token gerektirsin
- [ ] Test: Hisse ekle → listele → bildirim aç/kapa → kaldır

### Task 4.5: News API

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] `routers/news.py` endpoint'lerini yaz
- [ ] `GET /api/news` → Kullanıcının watchlist'indeki hisselerin haberleri
  - [ ] Filtreler: `category` (all / kap / activity / financial)
  - [ ] Pagination (limit + offset)
  - [ ] Sıralama: en yeni önce
- [ ] `GET /api/news/{id}` → Tek haber detayı
- [ ] `POST /api/news/{id}/read` → Okundu olarak işaretle (user_news)
- [ ] KAP raporu → news kaydı oluşturma servisi (yeni KAP raporu geldiğinde otomatik news oluştur)
- [ ] Test: Watchlist'e 3 hisse ekle, haberlerinin geldiğini doğrula

### Task 4.6: API Endpoints Unit Tests

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `tests/unit/test_auth_service.py`:
  - [ ] Test: Password hashing and verification
  - [ ] Test: JWT token creation and validation
  - [ ] Test: Token expiry handling
- [ ] `tests/integration/test_auth_api.py`:
  - [ ] Test: Register user → success
  - [ ] Test: Register duplicate email → 400 error
  - [ ] Test: Login valid credentials → token returned
  - [ ] Test: Login invalid credentials → 401 error
  - [ ] Test: GET /me with valid token → user info
  - [ ] Test: GET /me without token → 401 error
- [ ] `tests/integration/test_stocks_api.py`:
  - [ ] Test: GET /stocks → list all stocks
  - [ ] Test: GET /stocks/{symbol} → stock detail
  - [ ] Test: GET /stocks/{symbol}/prices → price history
  - [ ] Test: GET /stocks/invalid → 404 error
- [ ] `tests/integration/test_watchlist_api.py`:
  - [ ] Test: POST /watchlist → add stock
  - [ ] Test: GET /watchlist → list user's watchlist
  - [ ] Test: DELETE /watchlist/{stock_id} → remove stock
  - [ ] Test: PATCH /watchlist/{stock_id}/notifications → toggle
  - [ ] Test: Unauthorized access → 401 error
- [ ] `tests/integration/test_news_api.py`:
  - [ ] Test: GET /news → list news
  - [ ] Test: GET /news with filter → filtered results
  - [ ] Test: POST /news/{id}/read → mark as read
- [ ] `pytest tests/integration/` ile tüm testlerin geçtiğini doğrula

---

# Phase 3 — AI Chat & RAG Pipeline

---

## 📅 Week 5: RAG Pipeline & Agent Architecture

**Tarih:** \_\_\_\_\_\_\_\_\_\_
**Hedef:** LangGraph orchestrator, CrewAI text analyst, AutoGen code executor

### Task 5.1: LangGraph Orchestrator Setup

**Tahmini Süre:** 5 saat
**Durum:** ⬜

- [ ] `services/agents/orchestrator.py` oluştur
- [ ] LangGraph state graph tanımla:
  - [ ] `START` → Query Classifier node
  - [ ] Query Classifier → route to: text_analysis / numerical_analysis / comparison / general
  - [ ] Text Analysis → CrewAI agent
  - [ ] Numerical Analysis → AutoGen agent
  - [ ] Comparison → CrewAI + AutoGen (parallel)
  - [ ] Results Merge node → combine all agent outputs
  - [ ] Judge Agent node → evaluate merged response
  - [ ] `END` → return final response
- [ ] State schema tanımla (TypedDict): user_query, query_type, agent_results, sources, judge_score, final_response
- [ ] Compile ve test: Basit bir query'yi graph'tan geçir, akışı logla

### Task 5.2: ChromaDB RAG Retrieval Service

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `services/rag_service.py` oluştur
- [ ] `retrieve_relevant_chunks(query, stock_symbols, top_k=5)` fonksiyonu
  - [ ] ChromaDB'den similarity search
  - [ ] Stock symbol'e göre metadata filtreleme
  - [ ] Sonuçları source bilgisiyle döndür (document name, date, excerpt)
- [ ] Re-ranking: İlk 10 sonucu çek, LLM ile en relevant 5'ini seç
- [ ] Context window builder: Retrieved chunk'ları prompt'a uygun formatta birleştir
- [ ] Test: "THYAO net kar" sorgusu → ilgili KAP chunk'larının döndüğünü doğrula
- [ ] Test: Olmayan hisse sorgusu → boş sonuç, hata değil

### Task 5.3: CrewAI Text Analysis Agent

**Tahmini Süre:** 4 saat
**Durum:** ⬜

- [ ] `services/agents/text_analyst.py` oluştur
- [ ] CrewAI Agent tanımla: role="Financial Text Analyst", goal="KAP raporlarından şirket analizi çıkar"
- [ ] CrewAI Task tanımla: RAG context + user query → structured analysis
- [ ] Output formatı: Özet, riskler, fırsatlar, kaynak referansları
- [ ] Gemini Flash'ı LLM olarak bağla
- [ ] Tool: `search_kap_documents` → ChromaDB'den ilgili chunk'ları çek
- [ ] Test: "BIMAS'ın 2025 faaliyet raporunda uluslararası genişleme hakkında ne diyor?" → anlamlı cevap döndüğünü doğrula
- [ ] Türkçe prompt template'lerini optimize et

### Task 5.4: AutoGen Code Executor Agent

**Tahmini Süre:** 4 saat
**Durum:** ⬜

- [ ] `services/agents/code_executor.py` oluştur
- [ ] AutoGen AssistantAgent + UserProxyAgent tanımla
- [ ] Sandbox ortamı: Docker container içinde güvenli Python execution
- [ ] Erişebileceği veriler:
  - [ ] yfinance API (canlı fiyat, metrikler)
  - [ ] DB'den financial statements (SQLAlchemy query)
- [ ] Chart generation: matplotlib/plotly → base64 image veya Chart.js config JSON
- [ ] Metric hesaplama: P/E karşılaştırma, büyüme oranları, debt/equity ratio
- [ ] Test: "THYAO ve ASELS son 3 yıl net kar karşılaştırması" → chart + veri döndüğünü doğrula
- [ ] Timeout: Kod execution 30 saniye ile sınırla
- [ ] Security: Dosya sistemi erişimini kısıtla, network'ü sadece yfinance'a aç

### Task 5.5: Results Merger

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] `services/agents/merger.py` oluştur
- [ ] CrewAI + AutoGen çıktılarını birleştirme mantığı
- [ ] Chart varsa: response'a embed et (inline chart)
- [ ] Source referanslarını birleştir ve deduplicate et
- [ ] Comparison tablosu oluşturma: Side-by-side metrik karşılaştırma (Net Profit, P/E, ROE, Debt/Equity)
- [ ] Suggested questions oluştur: Cevaba bağlı context-aware öneriler (3 adet)
- [ ] Test: Hem text hem numerical cevap gerektiren bir query'nin merged output'unu doğrula

### Task 5.6: Agent & RAG Unit Tests

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `tests/mocks/mock_gemini.py` → Fake Gemini API responses
- [ ] `tests/mocks/mock_langgraph.py` → Mock graph state for testing
- [ ] `tests/unit/test_query_classifier.py`:
  - [ ] Test: Text query → text_analysis
  - [ ] Test: Numerical query → numerical_analysis
  - [ ] Test: Comparison query → comparison
  - [ ] Test: General query → general
- [ ] `tests/unit/test_rag_retriever.py`:
  - [ ] Test: Similarity search returns relevant chunks
  - [ ] Test: Metadata filtering by stock symbol
  - [ ] Test: Empty result for non-existent stock
  - [ ] Test: Re-ranking improves relevance
- [ ] `tests/unit/test_text_analyst.py`:
  - [ ] Test: CrewAI agent returns structured analysis
  - [ ] Test: Source references are included
  - [ ] Test: Turkish language response
- [ ] `tests/unit/test_code_executor.py`:
  - [ ] Test: Chart config generation
  - [ ] Test: Metric calculation accuracy
  - [ ] Test: Timeout handling
  - [ ] Test: Security sandbox restrictions
- [ ] `tests/unit/test_merger.py`:
  - [ ] Test: Merging text + numerical outputs
  - [ ] Test: Source deduplication
  - [ ] Test: Comparison table generation
- [ ] `pytest tests/unit/` ile tüm testlerin geçtiğini doğrula

---

## 📅 Week 6: Chat API & Session Management

**Tarih:** \_\_\_\_\_\_\_\_\_\_
**Hedef:** Chat endpoint'leri, streaming, session history

### Task 6.1: Chat API Endpoints

**Tahmini Süre:** 4 saat
**Durum:** ⬜

- [ ] `routers/chat.py` endpoint'lerini yaz
- [ ] `POST /api/chat/sessions` → Yeni sohbet oturumu oluştur
- [ ] `GET /api/chat/sessions` → Kullanıcının tüm oturumları (sidebar için)
- [ ] `GET /api/chat/sessions/{id}` → Oturum detayı + mesaj geçmişi
- [ ] `DELETE /api/chat/sessions/{id}` → Oturumu sil
- [ ] `POST /api/chat/sessions/{id}/messages` → Mesaj gönder:
  - [ ] User mesajını DB'ye yaz
  - [ ] LangGraph orchestrator'ı çağır
  - [ ] Assistant cevabını DB'ye yaz (content, message_type, metadata, sources)
  - [ ] Response'u döndür
- [ ] Response formatı:
  ```json
  {
    "content": "...",
    "message_type": "text|chart|table",
    "chart_config": {...},
    "sources": [...],
    "suggested_questions": [...]
  }
  ```
- [ ] Auth required: Tüm endpoint'ler JWT token gerektirsin

### Task 6.2: Streaming Response (SSE)

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `POST /api/chat/sessions/{id}/messages/stream` → Server-Sent Events endpoint
- [ ] LangGraph'tan gelen partial response'ları stream et
- [ ] Event türleri:
  - [ ] `token` → text token'ları (typing effect)
  - [ ] `chart` → chart config (tamamlanınca)
  - [ ] `sources` → kaynak referansları (tamamlanınca)
  - [ ] `done` → stream bitti
  - [ ] `error` → hata oluştu
- [ ] Frontend tarafında EventSource ile consume edilebilirliğini doğrula
- [ ] Timeout: 60 saniye sonra stream'i kapat

### Task 6.3: Conversation Context Management

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] Son N mesajı (default: 10) LLM context'ine ekle
- [ ] Token limit kontrolü: Context çok uzunsa eski mesajları summarize et
- [ ] System prompt template'i yaz:
  - [ ] FinMatrix rolü ve kuralları
  - [ ] "Asla al/sat tavsiyesi verme" kuralı
  - [ ] Türkçe yanıt ver
  - [ ] Kaynaklarını belirt
  - [ ] Chart gerekiyorsa JSON config üret
- [ ] Test: 5+ mesajlık bir sohbette context'in doğru aktarıldığını doğrula

### Task 6.4: Chart Generation Pipeline

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `services/chart_service.py` oluştur
- [ ] Chart.js config JSON oluşturma fonksiyonları:
  - [ ] Line chart (fiyat trendi)
  - [ ] Bar chart (quarterly net profit, karşılaştırma)
  - [ ] Mixed chart (revenue + net profit overlay)
- [ ] AutoGen'den gelen raw data → Chart.js config dönüşümü
- [ ] Color palette: Tutarlı renk şeması (hisse başına sabit renk)
- [ ] Responsive config: Mobile ve desktop uyumlu
- [ ] Test: 3 farklı chart tipi için config oluştur, frontend'de render et

### Task 6.5: Chat API & Streaming Tests

**Tahmini Süre:** 2.5 saat
**Durum:** ⬜

- [ ] `tests/integration/test_chat_api.py`:
  - [ ] Test: POST /chat/sessions → create session
  - [ ] Test: GET /chat/sessions → list sessions
  - [ ] Test: GET /chat/sessions/{id} → session with messages
  - [ ] Test: DELETE /chat/sessions/{id} → delete session
  - [ ] Test: POST /chat/sessions/{id}/messages → send message
  - [ ] Test: Response format validation (content, message_type, sources)
  - [ ] Test: Unauthorized access → 401 error
- [ ] `tests/unit/test_chat_service.py`:
  - [ ] Test: Session creation
  - [ ] Test: Message storage
  - [ ] Test: Context management (last N messages)
  - [ ] Test: Token limit handling
- [ ] `tests/unit/test_chart_service.py`:
  - [ ] Test: Line chart config generation
  - [ ] Test: Bar chart config generation
  - [ ] Test: Mixed chart config generation
  - [ ] Test: Color palette consistency
- [ ] `tests/integration/test_streaming.py`:
  - [ ] Test: SSE endpoint returns events
  - [ ] Test: Event types (token, chart, sources, done, error)
  - [ ] Test: Stream timeout handling
- [ ] `pytest tests/integration/test_chat_api.py tests/unit/test_chat_service.py` ile testleri çalıştır

---

# Phase 4 — Frontend–Backend Entegrasyonu

---

## 📅 Week 7: Frontend API Integration

**Tarih:** \_\_\_\_\_\_\_\_\_\_
**Hedef:** Mevcut HTML/JS frontend'i backend API'ye bağla

### Task 7.1: API Client & Auth Flow

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `js/api.js` → Base API client (fetch wrapper, auth header, error handling)
- [ ] `js/auth.js` → Login/register formları, JWT token yönetimi (localStorage)
- [ ] Login sayfası oluştur (`login.html`)
- [ ] Register sayfası oluştur (`register.html`)
- [ ] Protected route mantığı: Token yoksa login'e yönlendir
- [ ] Token refresh: Expire yaklaşınca otomatik yenile
- [ ] Test: Register → Login → Dashboard'a erişim akışı

### Task 7.2: News Feed Page Integration

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `js/news.js` → News API'yi çağır
- [ ] Kategori filtreleri çalışsın (All / KAP Filings / Activity / Financial)
- [ ] Sol sidebar: Watchlist API → canlı fiyat + değişim %
- [ ] Sağ panel: BIST100 index mini chart + top gainers/losers
- [ ] Sektör performans overview (sector bazlı ortalama değişim)
- [ ] Infinite scroll veya pagination
- [ ] "AI Analysis" linki: Habere tıklayınca chat sayfasına yönlendir (pre-filled query)
- [ ] Loading states ve empty states

### Task 7.3: Stock Dashboard Page Integration

**Tahmini Süre:** 4 saat
**Durum:** ⬜

- [ ] `js/dashboard.js` → Stocks API'yi çağır
- [ ] Arama: Symbol/isim ile hisse arama, autocomplete
- [ ] Fiyat chart'ı: `/prices` endpoint → Chart.js line chart (timeframe selector: 1D/1W/3M/6M/1Y/5Y)
- [ ] Metrik kartları: `/metrics` endpoint → Market Cap, P/E, Net Profit, ROE kartları
  - [ ] Sektör ortalaması karşılaştırma badge'leri (Cheap/Expensive, Strong/Weak)
- [ ] Quarterly net profit bar chart: `/quarterly` endpoint → Chart.js bar chart
- [ ] Financial summary tablosu: `/financials` endpoint → Son 3 yıl tablo
- [ ] Related KAP filings: `/kap-reports` endpoint → Alt kısımda liste
- [ ] Loading skeleton'ları ekle

### Task 7.4: AI Chat Page Integration

**Tahmini Süre:** 5 saat
**Durum:** ⬜

- [ ] `js/chat.js` → Chat API'yi çağır
- [ ] Sol sidebar: Session listesi (GET /sessions) + yeni sohbet butonu
- [ ] Chat alanı: Mesaj baloncukları (user + assistant)
- [ ] SSE streaming: EventSource ile token-by-token render
- [ ] Inline chart rendering: `message_type === 'chart'` → Chart.js render
- [ ] Source transparency: Her AI cevabının altında kullanılan KAP dokümanları
- [ ] Sağ panel: Quick comparison table (karşılaştırma varsa)
- [ ] Suggested questions: Cevabın altında tıklanabilir öneriler
- [ ] Input alanı: Enter ile gönder, Shift+Enter ile yeni satır
- [ ] Loading indicator: AI düşünürken animasyon

### Task 7.5: Watchlist Page Integration

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `js/watchlist.js` → Watchlist API'yi çağır
- [ ] Hisse kartları: Şirket adı, fiyat, değişim, sparkline mini-chart, P/E, market cap, volume, 52-week high
- [ ] Sparkline chart'lar: Yeşil (yukarı trend), kırmızı (aşağı trend)
- [ ] Telegram bildirim toggle: PATCH endpoint ile
- [ ] "+ Add Stock" butonu: Modal ile hisse arama ve ekleme
- [ ] Hisse kaldırma: Karttan silme butonu
- [ ] Üst bar: Toplam hisse, günün kazananları, kaybedenleri, aktif alarm sayısı
- [ ] Boş state: "Henüz hisse eklemediniz" mesajı

### Task 7.6: Frontend Integration Tests

**Tahmini Süre:** 2.5 saat
**Durum:** ⬜

- [ ] Playwright veya Cypress kur (frontend E2E testing)
- [ ] `tests/e2e/test_auth_flow.spec.js`:
  - [ ] Test: Register form → success redirect
  - [ ] Test: Login form → dashboard redirect
  - [ ] Test: Invalid login → error message
  - [ ] Test: Protected route without token → login redirect
- [ ] `tests/e2e/test_news_page.spec.js`:
  - [ ] Test: News list loads
  - [ ] Test: Category filter works
  - [ ] Test: Click news → detail page
- [ ] `tests/e2e/test_dashboard.spec.js`:
  - [ ] Test: Stock search autocomplete
  - [ ] Test: Price chart renders
  - [ ] Test: Metrics cards display
  - [ ] Test: Quarterly chart renders
- [ ] `tests/e2e/test_chat_page.spec.js`:
  - [ ] Test: Session list sidebar
  - [ ] Test: Send message → AI response
  - [ ] Test: Chart renders inline
  - [ ] Test: Sources displayed
- [ ] `tests/e2e/test_watchlist_page.spec.js`:
  - [ ] Test: Watchlist cards display
  - [ ] Test: Add stock modal
  - [ ] Test: Remove stock
  - [ ] Test: Notification toggle
- [ ] `npx playwright test` ile tüm E2E testleri çalıştır

---

# Phase 5 — EvalOps & Judge Agent

---

## 📅 Week 8: Judge Agent & Hallucination Detection

**Tarih:** \_\_\_\_\_\_\_\_\_\_
**Hedef:** Her AI yanıtını değerlendir, halüsinasyonları engelle

### Task 8.1: Judge Agent Implementation

**Tahmini Süre:** 5 saat
**Durum:** ⬜

- [ ] `services/agents/judge.py` oluştur
- [ ] Judge Agent rolü: Her AI yanıtını kaynak dokümanlarla karşılaştır
- [ ] Input: AI response + source chunks + user query
- [ ] Evaluation kriterleri:
  - [ ] **Faithfulness** — Cevaptaki her claim kaynaklarda var mı?
  - [ ] **Relevance** — Cevap soruyla ne kadar ilgili?
  - [ ] **Completeness** — Kaynaktaki kritik bilgi atlanmış mı?
  - [ ] **Consistency** — Sayısal veriler doğru aktarılmış mı?
- [ ] Output: score (0-10), is_hallucinated (bool), reason (text)
- [ ] Threshold: score < 6 → halüsinasyon olarak işaretle
- [ ] Gemini Flash ile judge prompt'u optimize et
- [ ] Test: Bilinen doğru cevap → yüksek skor, uydurma cevap → düşük skor

### Task 8.2: Automated Metrics (BERTScore + ROUGE)

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `services/eval/metrics.py` oluştur
- [ ] BERTScore hesaplama: AI response vs source chunks → precision, recall, F1
- [ ] ROUGE score hesaplama: ROUGE-1, ROUGE-2, ROUGE-L
- [ ] Retrieval score: Retrieved chunk'ların query'ye relevance skoru
- [ ] Tüm skorları `eval_logs` tablosuna yaz
- [ ] Test: 10 farklı query-response çifti için metrikleri hesapla ve doğrula

### Task 8.3: Retry Pipeline

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] LangGraph graph'ına retry logic ekle:
  - [ ] Judge score < 6 → retry
  - [ ] Retry stratejisi: Daha fazla context chunk ekle (top_k artır)
  - [ ] Max retry: 2
  - [ ] Her retry'da `eval_logs.retry_count` artır
- [ ] 2 retry sonra hala başarısızsa: "Yeterli bilgi bulunamadı" mesajı döndür
- [ ] Test: Kasıtlı olarak kötü context ver → retry tetiklensin → daha iyi sonuç dönsün
- [ ] Pipeline log'larına retry event'lerini yaz

### Task 8.4: EvalOps Dashboard Data

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] `GET /api/admin/eval/stats` → Genel eval istatistikleri:
  - [ ] Toplam mesaj, ortalama judge score, halüsinasyon oranı, retry oranı
- [ ] `GET /api/admin/eval/hallucinations` → `hallucination_reports` view'dan liste
- [ ] `GET /api/admin/eval/pipeline-logs` → Pipeline run geçmişi
- [ ] Bu endpoint'ler admin-only (role-based auth)
- [ ] Test: 50+ mesaj sonrası istatistikleri kontrol et

### Task 8.5: EvalOps & Judge Agent Tests

**Tahmini Süre:** 2.5 saat
**Durum:** ⬜

- [ ] `tests/unit/test_judge.py`:
  - [ ] Test: High score for faithful response
  - [ ] Test: Low score for hallucinated response
  - [ ] Test: Faithfulness evaluation
  - [ ] Test: Relevance evaluation
  - [ ] Test: Consistency check for numerical data
- [ ] `tests/unit/test_metrics.py`:
  - [ ] Test: BERTScore calculation
  - [ ] Test: ROUGE score calculation
  - [ ] Test: Retrieval score calculation
  - [ ] Test: Metrics stored in eval_logs
- [ ] `tests/unit/test_retry_handler.py`:
  - [ ] Test: Retry triggered when score < 6
  - [ ] Test: Context expansion on retry
  - [ ] Test: Max retry limit (2)
  - [ ] Test: "Insufficient information" after max retries
- [ ] `tests/integration/test_eval_api.py`:
  - [ ] Test: GET /admin/eval/stats (admin only)
  - [ ] Test: GET /admin/eval/hallucinations
  - [ ] Test: GET /admin/eval/pipeline-logs
  - [ ] Test: Non-admin access → 403 error
- [ ] `pytest tests/unit/test_judge.py tests/unit/test_metrics.py tests/unit/test_retry_handler.py` ile testleri çalıştır

---

# Phase 6 — Telegram Bot & Notifications

---

## 📅 Week 9: Telegram Integration

**Tarih:** \_\_\_\_\_\_\_\_\_\_
**Hedef:** KAP bildirimlerini Telegram'a gönder

### Task 9.1: Telegram Bot Setup

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] BotFather'dan yeni bot oluştur → Token al
- [ ] `services/telegram_service.py` oluştur
- [ ] python-telegram-bot veya aiogram kütüphanesi kur
- [ ] `/start` komutu: Kullanıcıyı tanı, chat_id'yi kaydet
- [ ] `/link <email>` komutu: Telegram hesabını FinMatrix hesabına bağla → `users.telegram_chat_id` güncelle
- [ ] `/watchlist` komutu: Takip edilen hisseleri listele
- [ ] `/alerts` komutu: Bildirim ayarlarını göster
- [ ] Test: Bot'a /start yaz → cevap dönsün

### Task 9.2: Notification Service

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] `services/notification_service.py` oluştur
- [ ] KAP filing notification: Yeni KAP raporu geldiğinde
  - [ ] Watchlist'te bu hisseyi takip eden ve notification_enabled=True olan kullanıcıları bul
  - [ ] Telegram mesajı formatla: Hisse sembolü, rapor başlığı, tarih, link
  - [ ] Mesajı gönder
- [ ] Financial report notification: Çeyreklik/yıllık rapor yayınlandığında
- [ ] Price alert notification (opsiyonel): Fiyat belirli bir eşiği aştığında
- [ ] Watchlist digest: Günlük özet (belirlenen saatte)
- [ ] `telegram_settings.event_types` ile filtrele — sadece aktif türleri gönder
- [ ] `telegram_settings.notification_times` ile zamanlama kontrolü
- [ ] Rate limiting: Aynı kullanıcıya dakikada max 5 mesaj
- [ ] Test: Bir KAP raporu ekle → ilgili kullanıcılara bildirim gitsin

### Task 9.3: Notification Trigger Integration

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] KAP scraper'a hook ekle: Yeni rapor geldiğinde → notification_service çağır
- [ ] Scheduler'a watchlist digest job'ı ekle
- [ ] Pipeline log'a notification event'lerini yaz
- [ ] Hata durumunda: Mesaj gönderilemezse loglat, kullanıcıyı engelleme
- [ ] Test: End-to-end akış: KAP raporu → scrape → DB → notification → Telegram mesajı

### Task 9.4: Telegram & Notification Tests

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] `tests/mocks/mock_telegram.py` → Fake Telegram Bot API responses
- [ ] `tests/unit/test_telegram_service.py`:
  - [ ] Test: /start command → user registered
  - [ ] Test: /link command → account linked
  - [ ] Test: /watchlist command → stocks listed
  - [ ] Test: /alerts command → settings displayed
  - [ ] Test: Invalid command → help message
- [ ] `tests/unit/test_notification_service.py`:
  - [ ] Test: KAP filing notification sent to relevant users
  - [ ] Test: Event type filtering
  - [ ] Test: Notification time scheduling
  - [ ] Test: Rate limiting (max 5/min)
  - [ ] Test: Watchlist digest generation
- [ ] `tests/integration/test_notification_flow.py`:
  - [ ] Test: New KAP report → notification triggered
  - [ ] Test: User with notification_enabled=False → no notification
  - [ ] Test: Pipeline log entry created
  - [ ] Test: Failed notification → logged, not blocking
- [ ] `pytest tests/unit/test_telegram_service.py tests/unit/test_notification_service.py` ile testleri çalıştır

---

# Phase 7 — Test, Deploy & Polish

---

## 📅 Week 10: Testing, Deployment & Final Touches

**Tarih:** \_\_\_\_\_\_\_\_\_\_
**Hedef:** Test coverage, production deploy, dökümantasyon

### Task 10.1: Backend Unit Tests

**Tahmini Süre:** 4 saat
**Durum:** ⬜

- [ ] `tests/` klasör yapısını oluştur
- [ ] pytest + pytest-asyncio + httpx (TestClient) kur
- [ ] Auth testleri: register, login, invalid credentials, token expiry
- [ ] Stocks API testleri: list, detail, prices, financials, metrics
- [ ] Watchlist API testleri: add, remove, list, notification toggle
- [ ] Chat API testleri: session CRUD, message send, response format
- [ ] News API testleri: list, filter, read status
- [ ] Service testleri: yfinance_service, kap_service, chunking_service, rag_service
- [ ] Mock'lar: yfinance API, KAP scraper, ChromaDB, Gemini API
- [ ] Minimum coverage hedefi: %70
- [ ] `pytest --cov` ile coverage raporu oluştur

### Task 10.2: Integration Tests

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] Docker Compose ile test ortamı kur (test DB + test ChromaDB)
- [ ] End-to-end akış testi:
  - [ ] Register → Login → Watchlist'e hisse ekle → News'i gör → Chat'te soru sor → Cevap al
- [ ] Data pipeline testi: KAP raporu → chunk → embed → retrieve → AI response
- [ ] Judge Agent testi: Bilinen iyi/kötü response'lar → doğru değerlendirme
- [ ] Notification testi: KAP raporu geldi → Telegram bildirimi gitti
- [ ] Load test: 10 concurrent chat query → tümü 60 saniye altında cevap

### Task 10.3: Frontend Polish

**Tahmini Süre:** 3 saat
**Durum:** ⬜

- [ ] Responsive design kontrolü: Mobile, tablet, desktop
- [ ] Loading states: Tüm sayfalarda skeleton/spinner
- [ ] Error states: API hatalarında kullanıcı dostu mesajlar
- [ ] Empty states: Boş watchlist, boş chat, sonuç yok durumları
- [ ] Accessibility: Semantic HTML, aria labels, keyboard navigation
- [ ] Dark mode (opsiyonel)
- [ ] Favicon ve meta tags
- [ ] Performance: Lazy loading, image optimization, minimize JS/CSS

### Task 10.4: Production Deployment

**Tahmini Süre:** 4 saat
**Durum:** ⬜

- [ ] Production environment variables ayarla
- [ ] Docker Compose production config (resource limits, restart policies)
- [ ] PostgreSQL: Production password, connection pooling (pgbouncer)
- [ ] HTTPS setup (Let's Encrypt / Cloudflare)
- [ ] Frontend deploy: Vercel veya GitHub Pages
- [ ] Backend deploy: Railway / Fly.io / VPS (Docker)
- [ ] ChromaDB persistent storage doğrula
- [ ] CI/CD pipeline: GitHub Actions → test → build → deploy
- [ ] Health check endpoint'leri monitoring'e bağla
- [ ] Backup stratejisi: PostgreSQL daily backup

### Task 10.5: Documentation

**Tahmini Süre:** 2 saat
**Durum:** ⬜

- [ ] `README.md` güncelle (kurulum, kullanım, mimari, API docs linki)
- [ ] API documentation: Swagger UI üzerinden export
- [ ] Architecture diagram: Mermaid veya draw.io ile sistem mimarisi çiz
- [ ] Agent flow diagram: LangGraph → CrewAI / AutoGen → Judge akışı
- [ ] Database ER diagram
- [ ] Deployment guide
- [ ] Contributing guide (opsiyonel)
- [ ] Screenshots klasörünü güncelle (her sayfa için)

### Task 10.6: Final Checklist

**Tahmini Süre:** 1 saat
**Durum:** ⬜

- [ ] Tüm environment variable'lar documented
- [ ] Docker Compose tek komutla çalışıyor (`docker-compose up --build`)
- [ ] Seed data script'i var ve çalışıyor
- [ ] Tüm API endpoint'leri Swagger'da görünüyor ve çalışıyor
- [ ] AI Chat: Türkçe soru sor → kaynaklı cevap al → chart oluşsun
- [ ] Judge Agent: Halüsinasyonu tespit edip retry yapıyor
- [ ] Telegram Bot: KAP bildirimi geliyor
- [ ] Frontend: Tüm 4 sayfa çalışıyor (News, Dashboard, Chat, Watchlist)
- [ ] Güvenlik: SQL injection, XSS, JWT expiry, rate limiting
- [ ] README'de demo GIF veya video linki var
- [ ] GitHub repo public ve clean (no secrets, no .env committed)

---

## 📊 Toplam İş Tahmini

| Phase | Toplam Saat (tahmini) |
|-------|----------------------|
| Phase 1 — Altyapı & Database | ~24.5 saat |
| Phase 2 — Data Pipeline | ~32 saat |
| Phase 3 — AI Chat & RAG | ~27.5 saat |
| Phase 4 — Frontend Integration | ~20.5 saat |
| Phase 5 — EvalOps & Judge | ~14.5 saat |
| Phase 6 — Telegram Bot | ~9 saat |
| Phase 7 — Test & Deploy | ~17 saat |
| **TOPLAM** | **~145 saat** |

> 💡 Haftada ~15-20 saat çalışırsan 10 haftada tamamlanır.
> Buffer ekle: Beklenmedik sorunlar için her phase'e +%20 süre.
> 🧪 Test task'ları her phase'e entegre edilmiştir (shift-left testing).

---

*Son güncelleme: Mart 2026*