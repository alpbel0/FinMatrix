# FinMatrix - Development Roadmap

> Proje: AI-Powered Stock Analysis Platform for BIST Investors
> Baslangic: Nisan 2026
> Tahmini Sure: 11 Hafta
> Yazar: Yigitalp (@alpbel0)
> Gelistirme modeli: Local-first, Docker yok

---

## Genel Bakis

| Phase | Hafta | Odak | Durum |
|---|---|---|---|
| Phase 1 | Week 1-2 | Temel iskelet, database, UI shell, auth temeli | **✅ Completed** |
| Phase 2 | Week 3-4 | Veri kaynaklari + dashboard/watchlist/news slice'lari | **✅ Completed** |
| Phase 3 | Week 5-6 | RAG, AI chat ve frontend chat deneyimi | **✅ Completed** |
| Phase 4 | Week 7 | LangGraph Bridge - Agent Graph Mimarisi | **✅ Completed** |
| Phase 5 | Week 8 | Entegrasyon derinlestirme ve admin/api tamamlama | Planned |
| Phase 6 | Week 9 | EvalOps, Judge ve guvenilirlik | Planned |
| Phase 7 | Week 10 | Telegram bot ve notification sistemi | Planned |
| Phase 8 | Week 11 | Test, deploy hazirligi ve polish | Planned |

---

## Temel Kararlar

### 1. Docker Kullanilmayacak

Bu roadmap local gelistirme uzerine kuruludur:

- Python virtual environment
- Local PostgreSQL veya mevcut yerel veritabani
- Local ya da ayri calisan ChromaDB
- Manuel veya scheduler tabanli sync isleri

Docker, docker-compose, container orchestration ve container networking bu roadmap kapsamindan cikarilmistir.

### 2. Veri Kaynagi Stratejisi

| Gereksinim | Ana kaynak | Rol |
|---|---|---|
| Fiyat, OHLCV, market snapshot, teknik veri | `borsapy` | Ana market data provider |
| Finansal tablolar | `borsapy` | Gelir tablosu, bilanco, cashflow |
| KAP sirket listesi, genel bilgi, disclosure sorgulari | `pykap` | Ana KAP/disclosure provider |
| Ikinci KAP erisim yolu | `kap_sdk` | Fallback ve capraz kontrol |

### 3. Bu 3 veri kaynagi neyi cozer

- BIST hisse verisi
- Dashboard icin tarihsel fiyat verisi
- Hisse karsilastirma ve finansal tablo verisi
- Watchlist veri besleme
- KAP disclosure listesi ve sirket metadata'si
- News feed icin KAP tabanli veri toplama
- RAG icin belge metadata ve filing kaydi toplama

### 4. Bu 3 veri kaynagi neyi tek basina cozmez

- Ortak provider abstraction katmani
- Veri normalizasyonu ve canonical schema
- PDF indirme ve belge saklama
- Chunking, embedding ve retrieval
- Incremental sync scheduler
- Retry, cache, dedup, observability
- Agent orchestration, judge, guardrail

### 5. `kap_sdk` Notu

- `search/kap_sdk/` klasoru repoda bos
- `kap_sdk` repo ici kaynak degil, kurulu Python dependency olarak ele alinacak
- Bu nedenle ana KAP provider `pykap`, ikinci provider `kap_sdk` olacak

### 6. Gelistirme Akisi: Frontend + Backend Paralel

Bu projede akış "once backend tamamen bitsin, sonra frontend" seklinde olmayacak.

- Her hafta backend ve frontend ayni anda ilerleyecek
- Isler teknik katmanlara gore degil, urun slice'larina gore planlanacak
- Her ana ozellikte minimum calisan akış hedeflenecek:
- [ ] veri kaynagi
- [ ] backend endpoint / servis
- [ ] frontend baglantisi
- [ ] temel test
- Dashboard, Watchlist, News Feed ve Chat ayrik ama paralel ilerleyen dikey dilimler olarak ele alinacak

### 7. LLM Stratejisi: Rol Bazli Ayrim

Model adlari bu asamada sabitlenmeyecek, ancak OpenRouter uzerinden rol bazli bir strateji izlenecek:

- Chat / text analysis agent:
- [ ] Daha guclu muhakeme ve daha iyi uzun baglam yonetimi gereken ana yanit uretim katmani
- [ ] KAP dokumanlarini yorumlama, risk/firsat cikarimi, kaynakli anlatim burada olacak
- Judge agent:
- [ ] Ayrik calisan denetleyici model/cagri olarak ele alinacak
- [ ] Gorevi yeni icerik uretmek degil, cevabin kaynaklarla tutarliligini ve kapsamini denetlemek olacak
- [ ] Maliyet dusurmek icin ana chat modelinden daha hafif bir secenek tercih edilebilecek
- Reranker / query helper:
- [ ] Retrieval sonuclarini siralama, kisitli secim ve siniflandirma gibi daha dar gorevlerde kullanilacak
- [ ] Burada daha ucuz ve hizli model sinifi tercih edilecek
- Numerical/code executor flow:
- [ ] Mumkun oldugunca LLM bagimliligini azaltacak
- [ ] Sayisal hesap, veri donusumu ve chart config uretimi once deterministic kod ile cozulecek
- [ ] LLM sadece gerekli yorumlama veya sunum katmaninda devreye girecek

### 8. OpenRouter Maliyet Kontrolu ve Fallback Yaklasimi

- [ ] Tum LLM cagrilari OpenRouter uzerinden gidecek
- [ ] Her agent tipi icin ayri token ve maliyet izleme metrikleri tutulacak
- [ ] Prompt boyutu kontrol edilecek; gereksiz dokuman ve uzun gecmis modele gonderilmeyecek
- [ ] Retrieval ile gelen context once daraltilacak, sonra modele verilecek
- [ ] Chat agent icin birincil model basarisiz olursa ayni rol icin ikincil bir fallback model tanimlanacak
- [ ] Judge agent icin bagimsiz fallback stratejisi olacak; ana chat fallback'i ile ayni olmak zorunda olmayacak
- [ ] Reranker/helper gorevlerinde varsayilan olarak daha dusuk maliyetli model sinifi kullanilacak
- [ ] Rate limit, timeout veya provider hatalarinda otomatik retry + sinirli fallback uygulanacak
- [ ] Butce kontrolu icin:
- [ ] request bazli max token limiti
- [ ] gunluk/haftalik harcama gozlemi
- [ ] pahali agent akislari icin degrade mode
- [ ] Degrade mode senaryolari:
- [ ] reranker'i kapatip sadece retrieval skoru ile devam etmek
- [ ] judge'i kisaltilmis context ile calistirmak
- [ ] chat cevabini daha kisa formatta uretmek
- [ ] kritik olmayan suggested questions gibi ek ciktilari kapatmak

---

# Phase 1 - Altyapi ve Database

## Week 1: Project Setup ve Local Infrastructure

**Tarih:** 2026-04-07
**Hedef:** Repo yapisini, local backend altyapisini ve gelistirme ortamını kurmak
**Durum:** ✅ Completed

### Task 1.1: Project Setup

**Tahmini Sure:** 2 saat
**Durum:** ✅ Completed

- [x] `backend/` klasorunu olustur
- [x] Ana klasor yapisini olustur:

```text
FinMatrix/
|
|-- backend/
|   |-- requirements.txt
|   |-- pyproject.toml
|   |
|   |-- app/
|   |   |-- __init__.py
|   |   |-- main.py
|   |   |-- config.py
|   |   |-- database.py
|   |   |-- dependencies.py
|   |   |
|   |   |-- models/
|   |   |   |-- __init__.py
|   |   |   |-- user.py
|   |   |   |-- stock.py
|   |   |   |-- watchlist.py
|   |   |   |-- stock_price.py
|   |   |   |-- balance_sheet.py
|   |   |   |-- income_statement.py
|   |   |   |-- cash_flow.py
|   |   |   |-- kap_report.py
|   |   |   |-- news.py
|   |   |   |-- chat.py
|   |   |   |-- document_chunk.py
|   |   |   |-- pipeline_log.py
|   |   |   `-- eval_log.py
|   |   |
|   |   |-- schemas/
|   |   |   |-- __init__.py
|   |   |   |-- auth.py
|   |   |   |-- stock.py
|   |   |   |-- watchlist.py
|   |   |   |-- news.py
|   |   |   |-- chat.py
|   |   |   |-- financials.py
|   |   |   |-- eval.py
|   |   |   `-- telegram.py
|   |   |
|   |   |-- routers/
|   |   |   |-- __init__.py
|   |   |   |-- auth.py
|   |   |   |-- stocks.py
|   |   |   |-- watchlist.py
|   |   |   |-- news.py
|   |   |   |-- chat.py
|   |   |   `-- admin.py
|   |   |
|   |   |-- services/
|   |   |   |-- __init__.py
|   |   |   |-- auth_service.py
|   |   |   |-- stock_service.py
|   |   |   |-- watchlist_service.py
|   |   |   |-- news_service.py
|   |   |   |-- chat_service.py
|   |   |   |-- financials_service.py
|   |   |   |-- chart_service.py
|   |   |   |-- notification_service.py
|   |   |   |-- telegram_service.py
|   |   |   |
|   |   |   |-- data/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- market_data_service.py
|   |   |   |   |-- kap_data_service.py
|   |   |   |   |-- provider_registry.py
|   |   |   |   |-- provider_models.py
|   |   |   |   |-- borsapy_provider.py
|   |   |   |   |-- pykap_provider.py
|   |   |   |   `-- kap_sdk_provider.py
|   |   |   |
|   |   |   |-- pipeline/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- chunking_service.py
|   |   |   |   |-- embedding_service.py
|   |   |   |   |-- sync_service.py
|   |   |   |   `-- scheduler.py
|   |   |   |
|   |   |   |-- rag/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- retriever.py
|   |   |   |   |-- reranker.py
|   |   |   |   `-- context_builder.py
|   |   |   |
|   |   |   |-- agents/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- orchestrator.py
|   |   |   |   |-- query_classifier.py
|   |   |   |   |-- text_analyst.py
|   |   |   |   |-- code_executor.py
|   |   |   |   |-- merger.py
|   |   |   |   `-- judge.py
|   |   |   |
|   |   |   |-- eval/
|   |   |   |   |-- __init__.py
|   |   |   |   |-- metrics.py
|   |   |   |   |-- judge_evaluator.py
|   |   |   |   `-- retry_handler.py
|   |   |   |
|   |   |   `-- utils/
|   |   |       |-- __init__.py
|   |   |       |-- logger.py
|   |   |       |-- security.py
|   |   |       |-- rate_limiter.py
|   |   |       |-- exceptions.py
|   |   |       |-- constants.py
|   |   |       `-- helpers.py
|   |   |
|   |   `-- prompts/
|   |       |-- system_prompt.txt
|   |       |-- judge_prompt.txt
|   |       |-- text_analyst_prompt.txt
|   |       |-- code_executor_prompt.txt
|   |       |-- query_classifier_prompt.txt
|   |       `-- summary_prompt.txt
|   |
|   |-- alembic/
|   |   |-- env.py
|   |   |-- script.py.mako
|   |   `-- versions/
|   |
|   |-- scripts/
|   |   |-- seed_stocks.py
|   |   |-- backfill_prices.py
|   |   |-- backfill_financials.py
|   |   |-- backfill_kap_reports.py
|   |   `-- reindex_chromadb.py
|   |
|   `-- tests/
|       |-- __init__.py
|       |-- conftest.py
|       |-- factories.py
|       |
|       |-- unit/
|       |-- integration/
|       |-- e2e/
|       `-- mocks/
|
|-- frontend/
|-- search/
|-- README.md
`-- ROADMAP.md
```

- [ ] Local-first setup mantigini README ve roadmap ile uyumlu hale getir
- [ ] Docker ile ilgili tasklari roadmap disinda tut

### Task 1.1B: Frontend Shell ve Temel Yapi

**Tahmini Sure:** 2 saat
**Durum:** ✅ Completed

- [x] `frontend/` altindaki mevcut sayfa yapisini netlestir
- [x] `index.html`, `dashboard.html`, `chat.html`, `watchlist.html`, `login.html`, `register.html` sayfalarinin rollerini kesinlestir
- [x] Ortak `api.js`, auth state ve temel navigation akisini planla
- [x] Frontend tarafinda mock veri ile ilk iskelet render akisini koru
- [x] Backend gelmeden de sayfalarin bos durum / loading durumlarini tasarla

### Task 1.2: Local Environment Configuration

**Tahmini Sure:** 2 saat
**Durum:** ✅ Completed

- [x] `.env.example` dosyasi olustur
- [x] `DATABASE_URL`, `CHROMA_HOST`, `CHROMA_PORT`, `OPENROUTER_API_KEY`, `TELEGRAM_BOT_TOKEN` gibi degiskenleri tanimla
- [x] `config.py` icinde `pydantic-settings` tabanli ayarlari kur (Pydantic v2 SettingsConfigDict)
- [x] Local Python virtual environment standardini netlestir
- [x] Local PostgreSQL baglantisini test et
- [x] Local veya harici ChromaDB baglantisini test et (deferred to Week 5)
- [x] `main.py` icin basic FastAPI app instance kur (CORS middleware included)
- [x] `services/utils/logging.py` merkezi log yapisi kuruldu

### Task 1.3: Database Foundation

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] `database.py` icinde SQLAlchemy async engine ve session factory kur
- [x] Base declarative yapisini kur
- [x] Alembic yapisini initialize et (async env.py with run_async_migrations)
- [x] Ilk migration akisini test et (`29954d31f5c6_initial_empty_schema`)
- [x] `GET /health` endpoint'i ile DB baglantisini dogrula (`{"status":"ok","database":"connected"}`)

---

## Week 2: SQLAlchemy Models ve Temel Domain

**Tarih:** 2026-04-07
**Hedef:** Uygulamanin kalici veri modelini kurmak
**Durum:** ✅ Completed

### Task 2.1: User ve Watchlist Modelleri

**Tahmini Sure:** 2 saat
**Durum:** ✅ Completed (Week 1'de yapildi)

- [x] `models/user.py` -> `users`, `telegram_settings`
- [x] `models/watchlist.py` -> `watchlist`
- [x] Alanlar:
- [x] `users`: id, username, email, password_hash, is_admin, created_at
- [x] `watchlist`: id, user_id, stock_id, notifications_enabled, created_at
- [x] Unique constraint: `(user_id, stock_id)`

### Task 2.2: Stock ve Price Modelleri

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed (Week 1'de yapildi)

- [x] `models/stock.py` -> `stocks`
- [x] `models/stock_price.py` -> `stock_prices`
- [x] Alanlar:
- [x] `stocks`: id, symbol, company_name, sector, exchange, is_active, created_at
- [x] `stock_prices`: id, stock_id, date, open, high, low, close, volume, adjusted_close, source, created_at
- [x] Index: `idx_stock_symbol`
- [x] Index: `idx_stock_price_stock_date`

### Task 2.3: Finansal Tablo Modelleri

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed (Week 1'de yapildi)

- [x] `models/income_statement.py`
- [x] `models/balance_sheet.py`
- [x] `models/cash_flow.py`
- [x] Annual ve quarterly ayrimini modelde destekle
- [x] Kaynak provider bilgisini kaydet
- [x] `(stock_id, period_type, statement_date, source)` bazli unique constraint tanimla

### Task 2.4: KAP, News, Chat ve Pipeline Modelleri

**Tahmini Sure:** 4 saat
**Durum:** ✅ Completed (Week 1'de yapildi)

- [x] `models/kap_report.py` -> `kap_reports`
- [x] `models/news.py` -> `news`, `user_news`
- [x] `models/chat.py` -> `chat_sessions`, `chat_messages`
- [x] `models/document_chunk.py` -> `document_chunks`
- [x] `models/pipeline_log.py` -> `pipeline_logs`
- [x] `models/eval_log.py` -> `eval_logs`
- [x] `kap_reports` alanlari:
- [x] stock_id, title, filing_type, pdf_url, source_url, published_at, provider, sync_status, chunk_count, created_at
- [x] `document_chunks` alanlari:
- [x] kap_report_id, chunk_index, chunk_text, chunk_text_hash, chroma_document_id, embedding_status
- [x] `pipeline_logs` alanlari:
- [x] run_id, pipeline_name, status, started_at, finished_at, processed_count, error_message, details

### Task 2.5: Migrationlar

**Tahmini Sure:** 2 saat
**Durum:** ✅ Completed

- [x] Ilk migration dosyasini olustur (`f8ada4730564_initial_schema.py`)
- [x] Migration'i local DB'ye uygula
- [x] Tum tablolarin olustugunu dogrula (14 tablo + alembic_version)

### Task 2.6: Auth ve App Shell Frontend

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] `services/auth_service.py` - Password hashing (bcrypt), JWT (python-jose)
- [x] `routers/auth.py` - `/register`, `/login`, `/me` endpointleri
- [x] `schemas/auth.py` - RegisterRequest, LoginRequest, TokenResponse, UserResponse
- [x] `frontend/js/auth.js` - registerUser, loginUser, getCurrentUser, logout
- [x] `frontend/js/navigation.js` - Token validation, force redirect
- [x] `frontend/login.html`, `frontend/register.html` - Gercek API baglantisi
- [x] Unit testler: `tests/unit/test_auth_service.py` (11 test)
- [x] Integration testler: `tests/integration/test_auth.py` (9 test)

---

# Phase 2 - Data Pipeline ve Ilk Urun Slice'lari

## Week 3: Market Data ve Dashboard Slice

**Tarih:** 2026-04-07
**Hedef:** `borsapy`, `pykap` ve `kap_sdk` tabanli provider servislerini kurarken dashboard sayfasini da ayni hafta calisir hale getirmek
**Durum:** ✅ Completed

### Task 3.1: Provider Abstraction

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] `services/data/provider_models.py` olustur
- [x] Ortak veri modelleri:
- [x] `PriceBar`
- [x] `StockSnapshot`
- [x] `FinancialStatementSet`
- [x] `KapFiling`
- [x] `CompanyProfile`
- [x] `ProviderCapabilities`
- [x] `provider_exceptions.py` olustur - custom exception hierarchy (10 exception class)
- [x] `provider_interface.py` olustur - Protocol tanimi
- [x] `provider_registry.py` icinde capability bazli secim mantigi kur
- [x] Uygulama kodunun provider implementation detayini bilmemesini sagla

### Task 3.2: Borsapy Market Data Provider

**Tahmini Sure:** 4 saat
**Durum:** ✅ Completed

- [x] `borsapy_provider.py` olustur
- [x] Tek hisse icin fiyat gecmisi cekme fonksiyonu yaz
- [x] Batch fiyat update akisini yaz
- [x] Temel metrikleri alma akisini yaz
- [x] Finansal tablolari alma akisini yaz
- [x] Endeks, sektor veya ilgili piyasa ozetleri icin uygun borsapy yuzeylerini incele
- [x] Timeout, retry, error handling ekle
- [x] SQLAlchemy mapper'lar olustur: `mappers/stock_price_mapper.py`, `mappers/financials_mapper.py`
- [x] Test: THYAO, GARAN, ASELS icin veri cek (22/26 integration test passed)

### Task 3.3: Pykap KAP Provider

**Tahmini Sure:** 4 saat
**Durum:** ✅ Completed

- [x] `pykap_provider.py` olustur
- [x] Sirket arama ve ticker esleme yaz
- [x] Genel sirket bilgisi alma akisini yaz
- [x] Disclosure listesi cekme akisini yaz
- [x] Belirli tarih araligi ile filing sorgusu yaz
- [x] Filing metadata'sini ortak `KapFiling` modeline map et
- [x] Test: THYAO, GARAN, ASELS icin son bildirimleri cek (23/23 integration tests passed)

### Task 3.4: KAP SDK Fallback Provider

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] `kap_sdk_provider.py` olustur
- [x] `kap_sdk` importunu opsiyonel tut
- [x] Paket kurulu degilse graceful degrade yap
- [x] KAP sorgulari icin ikinci provider yuzeyi kur
- [x] `pykap` hata verdiginde fallback mantigi ekle
- [x] Fallback sonucu ile primary sonucu deduplicate et
- [x] Mumkun olan alanlarda `kap_sdk` `disclosureDetail` metadata'si ile primary sonucu enrich et
- [x] Hangi endpoint'lerde fallback kullanilacagini netlestir

### Task 3.5: Data Provider Unit Tests

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] `tests/mocks/mock_borsapy.py` - MockTicker, MockTickers, MockFastInfo, create_mock_price_dataframe
- [x] `tests/mocks/mock_pykap.py` - MockBISTCompany, create_mock_disclosure_dict
- [x] `tests/mocks/mock_kap_sdk.py` - Already existed (enhanced)
- [x] `tests/unit/test_borsapy_provider.py` - 35+ tests for BorsapyProvider
- [x] `tests/unit/test_provider_registry.py` - 22 tests for ProviderRegistry
- [x] `tests/factories.py` - Provider model factories (PriceBarFactory, KapFilingFactory, etc.)
- [x] Testler:
  - [x] Provider secimi (capability-based selection)
  - [x] Fallback davranisi (FallbackKapProvider preference)
  - [x] Hata durumlari (exception mapping tests)
  - [x] Timeout ve retry davranisi (base provider tests)
- Note: test_market_data_service.py and test_kap_data_service.py deferred to Week 4 (services not yet created)

### Task 3.6: Dashboard API ve Frontend Slice

**Tahmini Sure:** 4 saat
**Durum:** ✅ Completed

- [x] `GET /api/stocks` - List stocks with search filter
- [x] `GET /api/stocks/{symbol}` - Stock detail endpoint
- [x] `GET /api/stocks/{symbol}/prices` - Price history endpoint
- [ ] `GET /api/stocks/{symbol}/metrics` - Deferred to Task 4.x (requires stock_metrics table)
- [x] `backend/app/schemas/stock.py` - Added PriceBarResponse, PriceHistoryResponse, StockDetailResponse, StockListResponse
- [x] `backend/app/services/stock_service.py` - Service layer with get_all_stocks, get_stock_by_symbol, get_price_history
- [x] `backend/app/routers/stocks.py` - 3 endpoints with auth protection
- [x] `backend/scripts/seed_stocks.py` - Seed BIST stocks + backfill prices
- [x] `frontend/js/stockApi.js` - Stock API functions
- [x] `frontend/js/dashboard.js` - Real API connection with Chart.js
- [x] `frontend/dashboard.html` - Stock search input + chart canvas
- [x] `frontend/package.json` - Added Chart.js dependency
- [x] Unit tests: `tests/unit/test_stock_service.py` (14 tests)
- [x] Integration tests: `tests/integration/test_stocks_api.py` (16 tests)
- [x] Total: 30 tests passing

---

## Week 4: Ingestion, Watchlist ve News Feed Slice

**Tarih:** 2026-04-08
**Hedef:** Ham provider verisini normalize edip veritabanina yazarken watchlist ve news feed ekranlarini ayni anda ilerletmek
**Durum:** In Progress

### Task 4.1: Price Ingestion

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] `market_data_service.py` olustur
- [x] Provider'dan gelen `PriceBar` verisini `stock_prices` tablosuna yaz
- [x] Upsert mantigi kur
- [x] Duplicate kayitlari atla
- [x] Batch sync islemini yaz
- [x] PipelineLog tracking ekle
- [x] Error handling ve retry logic
- [x] Unit tests: 17 tests passing
- [x] Integration tests: 8 tests passing

### Task 4.2: Financial Statements Ingestion

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] `financials_service.py` olustur
- [x] `borsapy` gelir tablosu verisini normalize et
- [x] `borsapy` bilanco verisini normalize et
- [x] `borsapy` cashflow verisini normalize et
- [x] Annual + quarterly kayit akisini destekle
- [x] Son 8 ceyreklik net kar verisini dogrula (validate_quarterly_net_income)
- [x] PipelineLog tracking ekle
- [x] Error handling ve retry logic
- [x] Unit tests: 20 tests passing
- [x] Integration tests: 9 tests passing
- [x] `pykap` ile tum BIST sirketlerini cekip `stocks` tablosuna otomatik seed et

### Task 4.3: KAP Reports Ingestion

**Tahmini Sure:** 4 saat
**Durum:** ✅ Completed

- [x] `kap_data_service.py` olustur
- [x] `pykap` ve `kap_sdk` ciktilarini ortak formatta birlestir
- [x] `kap_reports` tablosuna metadata yaz
- [x] Duplicate kontrolu ekle
- [x] `stocks` ile filing eslemesini netlestir
- [x] KapReport modeline enrichment fields ekle (summary, attachment_count, is_late, related_stocks)
- [x] PostgreSQL JSONB kullan related_stocks için
- [x] filing_types default: ["FR"] (Financial Reports)
- [x] Validation: source_url zorunlu, pdf_url opsiyonel
- [x] Unit tests: 31 tests passing
- [x] Integration tests: 9 tests passing
- [x] Test: THYAO icin son 10 filing'i DB'ye yaz

### Task 4.4: Scheduled Sync Jobs

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] `services/pipeline/scheduler.py` olustur - APScheduler AsyncIOScheduler
- [x] `services/pipeline/market_hours.py` olustur - BIST islem saat kontrolu
- [x] `services/pipeline/job_policy.py` olustur - universe selection logic
- [x] `services/data/providers/bist_index_provider.py` - BIST100 adapter
- [x] Job 1: Fiyat guncelleme - her 15 dakikada, sadece BIST is saatlerinde
- [x] Job 2a: Finansal tablo weekly - her Pazartesi 06:00
- [x] Job 2b: Finansal tablo reporting - 4 saatte 1 (reporting mode aktifken)
- [x] Job 3: KAP hourly - BIST100 icin saatlik
- [x] Job 4: KAP watchlist daily - her gun 21:00
- [x] Job 5: KAP slow - 3 gunde 1, watchlist ve BIST100 disindaki hisseler
- [x] Job 6: PENDING chunk'lari embed et - Week 5'e ertelendi
- [x] Her is icin `pipeline_logs` tablosuna kayit yaz
- [x] BIST is saatlerine gore fiyat sync kosulu ekle
- [x] Scheduler icin job policy / universe secimi tanimla (`BIST100`, `watchlist`, `slow`, `all`)
- [x] `models/scheduler_setting.py` - Financial reporting mode DB config
- [x] Finansal tablo reporting mode kontrolu (7 gun otomatik expiry)
- [x] Admin endpoint'ler: GET status, POST financial-reporting-mode, POST run/prices, POST run/financials, POST run/kap
- [x] `main.py` lifespan context manager ile scheduler lifecycle
- [x] Unit tests: test_market_hours.py, test_job_policy.py, test_bist_index_provider.py
- [x] `schemas/scheduler.py` - Admin endpoint request/response schemas

### Task 4.5: Mocklar ve Testler

**Tahmini Sure:** 2 saat
**Durum:** ✅ Completed

- [x] `tests/mocks/mock_kap.py` -> provider-agnostic KAP fixtures
- [x] `tests/mocks/mock_chromadb.py` -> ChromaDB mock for Week 5
- [ ] `tests/unit/test_chunking_service.py` -> deferred to Week 5
- [ ] `tests/unit/test_embedding_service.py` -> deferred to Week 5
- [x] Scheduler tests verified: test_scheduler.py (2), test_market_hours.py (23), test_job_policy.py (14), test_bist_index_provider.py (10) = 49 tests passing

### Task 4.6: Watchlist Slice

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] `GET /api/watchlist` - List user's watchlist with price snapshot
- [x] `POST /api/watchlist` - Add stock to watchlist (by symbol)
- [x] `DELETE /api/watchlist/{id}` - Remove from watchlist
- [x] `PATCH /api/watchlist/{id}/notifications` - Toggle notifications
- [x] `frontend/js/watchlist.js` - Real API connection with price snapshot
- [x] `backend/app/schemas/watchlist.py` - Request/response schemas
- [x] `backend/app/services/watchlist_service.py` - CRUD functions
- [x] `backend/app/routers/watchlist.py` - 4 endpoints implemented
- [x] Unit tests: `tests/unit/test_watchlist_service.py` (15 tests)
- [x] Integration tests: `tests/integration/test_watchlist_api.py` (11 tests)
- [x] Total: 26 tests passing

### Task 4.7: News Feed Slice

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] KAP filing -> news kaydi donusumu (`transform_kap_to_news`)
- [x] `backend/alembic/versions/e5f6a7b8c9d0_*.py` - Migration for source_type, source_id, filing_type
- [x] `backend/app/models/news.py` - Added 3 fields + unique constraint
- [x] `GET /api/news` - News feed with category filter
- [x] `GET /api/news/{id}` - News detail
- [x] `POST /api/news/{id}/read` - Mark read/unread
- [x] `frontend/js/news.js` - Category filters (all/financial/activity/kap)
- [x] `frontend/js/news-main.js` - Entry point
- [x] `frontend/index.html` - News root section
- [x] `backend/app/schemas/news.py` - Request/response schemas
- [x] `backend/app/services/news_service.py` - Transform + feed functions
- [x] `backend/app/routers/news.py` - 3 endpoints implemented
- [x] `backend/app/services/data/kap_data_service.py` - Transform hook after sync
- [x] Unit tests: `tests/unit/test_news_service.py` (19 tests)
- [x] Integration tests: `tests/integration/test_news_api.py` (10 tests)
- [x] Total: 29 tests passing

---

# Phase 3 - AI Chat ve RAG Pipeline

## Week 5: Retrieval, Text Analysis ve Chat UI Slice

**Tarih:** ___________
**Hedef:** KAP dokumanlarini AI tarafinda retrieval'a uygun hale getirirken chat ekraninin ilk gercek veri akisini kurmak
**Durum:** Planned

### Task 5.1: PDF Download Service

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] Filing metadata icinden PDF URL'lerini cikar
- [x] PDF indirme servisini yaz (`pdf_download_service.py`)
- [x] Indirme hatalarini `pipeline_logs` ile kaydet
- [x] Storage stratejisi: `backend/data/pdfs/{symbol}/{year}/{disclosure_index}.pdf`
- [x] KapReport modeline 5 yeni alan eklendi (local_pdf_path, pdf_download_status, pdf_file_size, pdf_downloaded_at, pdf_download_error)
- [x] Scheduled job: `pdf_download_hourly` (hourly)
- [x] Unit tests: 31 tests passing
- [x] Integration tests: Real PDF download tests for THYAO, GARAN, AKBNK

### Task 5.2: PDF Yapisal Ayristirma ve Chunking (Docling)

**Tahmini Sure:** 6 saat
**Durum:** Planned

- [ ] `pipeline/document_parser.py` olustur
  - [ ] Docling (DocumentConverter) ana parser olarak entegre et
  - [ ] pdfplumber fallback: Docling None donersa devreye girer
  - [ ] Her blok icin section_path, block_type, raw_text cikar
  - [ ] Tablo bloklarini ayir: PostgreSQL `extracted_tables` + Markdown olarak ChromaDB icin hazirla
  - [ ] `document_contents` tablosuna yaz (yeni RAG-ready tablo)
  - [ ] `chunk_report_links` tablosunu doldur (parent-child iliskisi)
- [ ] DB schema guncelleme (Alembic migration):
  - [ ] `document_contents`: id, kap_report_id, section_path, block_type, raw_text, processed_text, content_hash, parent_content_id, embedding_status, created_at
  - [ ] `extracted_tables`: id, kap_report_id, section_path, table_markdown, table_json, page_number, created_at
  - [ ] `chunk_report_links`: id, parent_id, child_id, link_type
  - [ ] `processing_cache`: id, section_path, decision (KEEP/DISCARD), suggested_label, decided_by, decided_at
- [ ] Unit tests: test_document_parser.py
- [ ] Integration tests: Real PDF parse ile THYAO/GARAN ornekleri

### Task 5.3: Triage Sistemi (Blacklist/Whitelist/Greylist)

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] `pipeline/triage_service.py` olustur
- [ ] Blacklist: "Bagimsiz Denetci Gorusu", kapak sayfasi, TOC -> direkt DISCARD
- [ ] Whitelist: "Finansal Durum", "Gelir Tablosu", "Yonetim Kurulu Raporu" -> direkt KEEP
- [ ] Greylist: 20 karakterden kisa ve harf icermeyenler -> hizli DISCARD
- [ ] LLM Check (4o-mini): Kalan None / bilinmeyen basliklar 4o-mini'ye gonder
  - [ ] Batch size: 20-30 baslik per call
  - [ ] Prompt: Ust Baslik + metin (ilk 100 token) -> {"is_valuable": true/false, "suggested_section": "..."}
  - [ ] Deger tasiyan None bloklara yapay baslik ata
- [ ] processing_cache tablosunu kullan: ayni section_path icin karar onceden verildiyse tekrar sorma
- [ ] Unit tests: test_triage_service.py (blacklist, whitelist, greylist, LLM check, cache hit)

### Task 5.4: Semantik Chunking + Parent-Child Retrieval

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] `pipeline/chunking_service.py` olustur (yeniden yazildi)
- [ ] Semantic chunking: Docling anlamsal bloklari temel birim, cumleler ortadan bolunmuyor
  - [ ] Hedef: 512-1024 token / chunk
  - [ ] Kesim noktasi: onceki cumlenin bittigi yer
  - [ ] Overlap yok (Parent-Child ile baglam saglanacak)
- [ ] Parent-Child kayit:
  - [ ] Parent: tum seksiyon metni document_contents'e yaz
  - [ ] Child: alt parcalar ayni tabloya yaz, parent_content_id ile parent'a bagla
  - [ ] chunk_report_links ile iliskiyi kaydet
- [ ] Semantic Context Prepend: Her child chunk basina [BAGIAM: {symbol} - {year} - {section_path}] etiketi ekle
- [ ] Unit tests: test_chunking_service.py (parent-child olusturma, context prepend)

### Task 5.5: Embedding Pipeline Guncellemesi

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `pipeline/embedding_service.py` guncelle (yeni document_contents tablosuna yazar)
- [ ] Model: openai/text-embedding-3-small (1536 dim) -- degismedi
- [ ] Metadata guncelle: stock_symbol, report_year, section_path, block_type, parent_content_id, kap_report_id
- [ ] Batch processing: 100 chunk per API call, 500 per scheduler run
- [ ] Status: EmbeddingStatus enum (PENDING/COMPLETED/FAILED) -> document_contents.embedding_status
- [ ] Scheduled job: embedding_10min (every 10 minutes)
- [ ] Unit tests: test_embedding_service.py

### Task 5.6: Retriever (Parent-Child + Cross-Encoder Reranker)

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] `rag/retriever.py` yeniden yaz
- [ ] Arama akisi:
  1. ChromaDB'de child chunk'lari sorgula (similarity search)
  2. Her child icin parent_content_id ile parent chunk'i PostgreSQL'den cek
  3. Child + Parent birlesik metni Cross-Encoder'a ver
  4. Cross-Encoder skoruna gore sirala, top-k sec
- [ ] Cross-Encoder: cross-encoder/ms-marco-MiniLM-L-2-v2 (~67MB, lokal calistir)
  - [ ] sentence_transformers.CrossEncoder ile yukle
  - [ ] Torch: Docling zaten yukluyor, ek yuk minimal
  - [ ] Async: asyncio.run_in_executor ile threadpool'da calistir
- [ ] Metadata filter: stock_symbol, report_year, section_path
- [ ] RetrievedChunk modeli guncelle: child_text, parent_text, cross_encoder_score, section_path
- [ ] Unit tests: test_retriever.py (parent-child birlestirme, cross-encoder siralama, metadata filter)

### Task 5.7: Chat Frontend Entegrasyonu

**Tahmini Sure:** 3 saat
**Durum:** Completed

- [x] `services/chat_service.py` - Session/message management
- [x] `routers/chat.py` - API endpoints (GET/POST sessions, POST messages)
- [x] `models/chat.py` - sources_metadata JSONB field
- [x] `frontend/js/api.js` - Chat API functions
- [x] `frontend/js/chat.js` - Real API connection, source panel rendering
- [x] `frontend/chat.html` - Source cards UI, loading state
- [x] Chat session creation + message persistence

### Task 5.8: Chat/RAG Trace Logging

**Tahmini Sure:** 3 saat
**Durum:** Completed

- [x] `models/chat_trace.py` olustur
- [x] `services/chat_trace_service.py` - structured trace persistence
- [x] Query understanding payload JSONB olarak kaydedildi
- [x] Retrieval summary + source metadata JSONB olarak kaydedildi
- [x] duration_ms ve error_message alanlari dolduruldu
- [x] Unit tests: test_chat_trace_service.py

---

# Phase 4 - 6-Ajan LangGraph Mimarisi

## Week 6: 6-Ajan Tanimi ve Altyapi

**Tarih:** ___________
**Hedef:** 6 ajanin rollerini, state semasini ve YAML konfigurasyon dosyalarini tanimlamak; her ajan icin izole unit testleri yazmak
**Durum:** Planned

### Week 6 Mimari Karari: 6-Ajan LangGraph State-Machine

Yeni mimari dogrudan LangGraph uzerine kurulacak.

| Ajan | Rol | Model |
|---|---|---|
| Router Agent | Sorguyu siniflandir, chit_chat ise direkt yanitla | google/gemini-3.1-flash-lite-preview |
| SQL Worker | SELECT-only SQL yaz ve calistir | openai/gpt-4o-mini |
| Fallback Agent | SQL hatalarinda yardim et (maks 3 retry) | z-ai/glm-5 |
| RAG Worker | ChromaDB chunk getir, Cross-Encoder ile sirala | cross-encoder/ms-marco-MiniLM-L-2-v2 (lokal) |
| Analysis Agent | SQL + RAG ciktilarini sentezle, chart_decision uret | anthropic/claude-haiku-4.5 |
| Visualization Agent | chart_decision + sql_raw_data -> chart_data JSON | openai/gpt-4o-mini |

**Akis:** Router => [SQL Worker || RAG Worker] => Analysis Agent => Visualization Agent (kosullu) => Final Output

**FinMatrixState alanlari:**
- user_query, chat_history (k=3 sliding window)
- resolved_symbol, query_type (rag_only / sql_rag / chit_chat)
- sql_query, sql_raw_data, sql_error, sql_retry_count
- retrieved_chunks, rag_context
- summary_markdown, chart_decision, chart_data
- node_history, fallback_reason

### Task 6.1: FinMatrixState Tanimi

**Tahmini Sure:** 2 saat
**Durum:** Planned

- [ ] `services/agents/graph/state.py` yeniden yaz
- [ ] FinMatrixState(TypedDict) tum alanlari ile tanimla
- [ ] query_type enum: rag_only / sql_rag / chit_chat
- [ ] sql_retry_count: int (maks 3)
- [ ] chart_decision: Optional[str], chart_data: Optional[dict]
- [ ] Unit tests: test_graph_state.py

### Task 6.2: YAML Konfigurasyon

**Tahmini Sure:** 2 saat
**Durum:** Planned

- [ ] `services/agents/config/agents.yaml`: Her ajan icin role, model, temperature, max_tokens
- [ ] `services/agents/config/tasks.yaml`: Her ajan icin system_prompt, expected_output_format
- [ ] YAML loader utility: `config/loader.py`
- [ ] Unit tests: test_yaml_config.py

### Task 6.3: Router Agent

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `services/agents/router_agent.py` olustur
- [ ] Model: google/gemini-3.1-flash-lite-preview
- [ ] Cikti: query_type (rag_only / sql_rag / chit_chat) + resolved_symbol
- [ ] chit_chat: Router direkt yanitlar, diger ajanlar tetiklenmez
- [ ] LangGraph edge: query_type'a gore routing
- [ ] Unit tests: test_router_agent.py (rag_only, sql_rag, chit_chat senaryolari)

### Task 6.4: SQL Worker + Fallback Agent

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] `services/agents/sql_worker.py` olustur
  - [ ] Model: openai/gpt-4o-mini
  - [ ] SELECT-only izolasyonu: ayri read-only DB kullanicisi
  - [ ] Math Tool: deterministik hesaplamalar icin Python fonksiyonlari
  - [ ] SQL Tool: sadece SELECT sorgulari calistir
  - [ ] Hata yonetimi: sql_error state alanina yaz
- [ ] `services/agents/fallback_agent.py` olustur
  - [ ] Model: z-ai/glm-5
  - [ ] SQL hatasi alindiysa devreye gir
  - [ ] Maks 3 retry: cozemezse sql_raw_data = null, Analysis devam eder
  - [ ] Retry sayacini sql_retry_count ile takip et
- [ ] Unit tests: test_sql_worker.py, test_fallback_agent.py

### Task 6.5: RAG Worker

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `services/agents/rag_worker.py` olustur
- [ ] Task 5.6 Retriever'i cagir (Parent-Child + Cross-Encoder)
- [ ] retrieved_chunks -> rag_context metni olarak hazirla
- [ ] Section path bilgisini context'e ekle
- [ ] SQL Worker ile PARALEL calisir (LangGraph async)
- [ ] Unit tests: test_rag_worker.py

### Task 6.6: Analysis Agent

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `services/agents/analysis_agent.py` olustur
- [ ] Model: anthropic/claude-haiku-4.5
- [ ] Giris: sql_raw_data + rag_context + user_query
- [ ] Cikti: summary_markdown + chart_decision (grafik tipi ve hangi veri -- chart_data uretmez)
- [ ] Unit tests: test_analysis_agent.py

### Task 6.7: Visualization Agent

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `services/agents/visualization_agent.py` olustur
- [ ] Model: openai/gpt-4o-mini
- [ ] Giris: chart_decision + sql_raw_data
- [ ] Cikti: chart_data (Chart.js uyumlu JSON)
- [ ] Analysis Agent'tan sonra sekans olarak calisir (sadece chart_decision doluysa tetiklenir)
- [ ] Unit tests: test_visualization_agent.py

### Task 6.8: Loglama ve Trace Altyapisi

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] Her ajan node'una structured logging ekle (node adi, giris/cikis ozeti, sure, hata)
- [ ] node_history state alanini her node'dan sonra guncelle
- [ ] chat_trace_service.py guncelle: node_history JSONB olarak kaydet
- [ ] LangSmith entegrasyonu:
  - [ ] LANGCHAIN_TRACING_V2=true env variable
  - [ ] LANGCHAIN_API_KEY config.py'ye ekle
  - [ ] Her LangGraph calismasini LangSmith'e otomatik gonder
  - [ ] Proje adi: FinMatrix
- [ ] Unit tests: test_logging_trace.py

---

## Week 7: LangGraph Orchestration + Chat Entegrasyonu

**Tarih:** ___________
**Hedef:** 6 ajani LangGraph graph'ina bagla, chat API'ye entegre et, E2E testleri yaz
**Durum:** Planned

### Task 7.1: LangGraph Workflow Tasarimi

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `services/agents/graph/workflow.py` yeniden yaz
- [ ] Node ekle: router, sql_worker, fallback_agent, rag_worker, analysis_agent, visualization_agent
- [ ] Edge tanimla:
  - [ ] router -> chit_chat_end (chit_chat ise direkt bitis)
  - [ ] router -> sql_worker + rag_worker (paralel, sql_rag ise)
  - [ ] router -> rag_worker (rag_only ise)
  - [ ] sql_worker -> fallback_agent (hata varsa) ya da analysis_agent (basariliysa)
  - [ ] fallback_agent -> sql_worker (retry) ya da analysis_agent (maks retry dolunca)
  - [ ] rag_worker -> analysis_agent
  - [ ] analysis_agent -> visualization_agent (chart_decision doluysa)
  - [ ] visualization_agent -> END
- [ ] get_graph() fonksiyonu: compiled graph dondur
- [ ] Unit tests: test_graph_workflow.py (routing, parallel exec, retry logic)

### Task 7.2: Orchestrator Entegrasyonu

**Tahmini Sure:** 2 saat
**Durum:** Planned

- [ ] `services/agents/orchestrator.py` yeniden yaz
- [ ] run_orchestrated_pipeline(query, chat_history, symbol) imzasini koru
- [ ] Iceride get_graph().ainvoke(initial_state) cagir
- [ ] final_state["summary_markdown"] + chart_data -> ChatPipelineResult dondur
- [ ] node_history -> chat_trace_service'e yaz
- [ ] Unit tests: test_orchestrator.py

### Task 7.3: API Retry Politikasi

**Tahmini Sure:** 2 saat
**Durum:** Planned

- [ ] Her LLM cagrisina exponential backoff ekle (max 3 retry, 1s/2s/4s)
- [ ] Timeout: 30s per LLM call
- [ ] OpenRouter rate limit handling: 429 -> retry with backoff
- [ ] Unit tests: test_retry_policy.py

### Task 7.4: Chat API Entegrasyonu

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `routers/chat.py` guncelle: yeni orchestrator'i cagir
- [ ] `schemas/chat.py` guncelle: chart_data, summary_markdown response alanlari
- [ ] Sliding window chat history: son k=3 mesaji state'e gec
- [ ] Frontend guncelle: chart_data varsa Chart.js ile render et
- [ ] Unit tests: test_chat_api.py

### Task 7.5: Graph ve E2E Testleri

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] `tests/unit/test_graph_routing.py`: query_type'a gore dogru node'a gidiyor mu?
- [ ] `tests/unit/test_graph_fallback.py`: SQL retry -> fallback -> Analysis akisi dogru mu?
- [ ] `tests/unit/test_graph_nodes.py`: Her node mock LLM ile dogru state donduruyor mu?
- [ ] `tests/unit/test_graph_state.py`: FinMatrixState alanlari dogru mu?
- [ ] `tests/unit/test_graph_trace_history.py`: node_history dogru dolduruluyor mu?
- [ ] `tests/integration/test_live_graph_e2e.py`: Gercek LLM + gercek ChromaDB ile tam akis

### Task 7.6: LangSmith Dashboard Dogrulama

**Tahmini Sure:** 1 saat
**Durum:** Planned

- [ ] LangSmith'te trace'lerin geldigini dogrula
- [ ] Her ajan cagrisinin ayri span olarak gorundugunu kontrol et
- [ ] Latency ve token kullanimini incele

---

### Week 7 Sonunda Beklenen Cikti

- [ ] 6 ajan tam olarak entegre ve LangGraph graph'inda calisir
- [ ] Chat API yeni orchestrator'i kullanir
- [ ] Her sorgu icin LangSmith'te trace gorulur
- [ ] Graph testleri (routing, fallback, trace, E2E) gecmis durumda
- [ ] Yeni FinMatrixState ile tip guvenli state yonetimi saglanmis

---


# Phase 5 - Entegrasyon Derinlestirme

## Week 8: API Bosluklari, Admin ve Capraz Sayfa Entegrasyonu

**Tarih:** ___________
**Hedef:** Kalan API bosluklarini kapatmak ve tum sayfalar arasinda tutarli bir urun akisi olusturmak
**Durum:** Planned

### Task 8.1: Auth API ve Frontend Sertlestirme

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `POST /api/auth/register`
- [ ] `POST /api/auth/login`
- [ ] `GET /api/auth/me`
- [ ] JWT ve password hashing akisini tamamla
- [ ] Frontend token saklama ve logout akisini sertlestir
- [ ] Form validation ve hata mesajlarini duzenle

### Task 8.2: Kalan Stocks/News/Chat API Bosluklari

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] `GET /api/stocks/{symbol}/financials`
- [ ] `GET /api/stocks/{symbol}/kap-reports`
- [ ] `GET /api/chat/sessions`
- [ ] `POST /api/chat/sessions`
- [ ] `POST /api/chat/messages`
- [ ] SSE veya streaming response akisini planla
- [ ] Source transparency formatini frontend'e uygun hale getir

### Task 8.3: Capraz Sayfa Frontend Entegrasyonu

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] `frontend/js/api.js` hata yonetimini merkezilestir
- [ ] Dashboard -> Chat gecislerini bagla
- [ ] News card -> ilgili hisse/dashboard/chat gecislerini bagla
- [ ] Watchlist -> dashboard detay akisini bagla
- [ ] Global loading ve auth expiry davranislarini tutarli hale getir

---

# Phase 6 - EvalOps ve Judge

## Week 9: Guvenilirlik Katmani

**Tarih:** ___________
**Hedef:** Halusinasyon riskini azaltan judge ve eval altyapisini kurmak
**Durum:** Planned

### Task 9.1: Judge Agent

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `agents/judge.py` olustur
- [ ] Faithfulness, relevance, consistency skorlarini hesapla
- [ ] Source desteklenmeyen cevaplari tespit et
- [ ] Retry karari icin cikti ver

### Task 9.2: Eval Metrics

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `eval/metrics.py` olustur
- [ ] BERTScore, ROUGE, retrieval score entegrasyonu
- [ ] `eval_logs` tablosuna kaydet
- [ ] Hallucination raporlama mantigi yaz

### Task 9.3: Retry Handler

**Tahmini Sure:** 2 saat
**Durum:** Planned

- [ ] Dusuk skor durumunda context'i genislet
- [ ] Yeniden retrieval yap
- [ ] Yeniden cevap olustur
- [ ] Retry sayisini logla

### Task 9.4: Eval API

**Tahmini Sure:** 2 saat
**Durum:** Planned

- [ ] `GET /api/admin/eval/stats`
- [ ] `GET /api/admin/hallucinations`
- [ ] `GET /api/admin/pipeline-logs`

---

# Phase 7 - Telegram Bot ve Notification Sistemi

## Week 10: Bildirim Akislari

**Tarih:** ___________
**Hedef:** KAP filing ve watchlist temelli bildirim sistemini kurmak
**Durum:** Planned

### Task 10.1: Telegram Bot Servisi

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `telegram_service.py` olustur
- [ ] `/start`, `/link` akisini planla
- [ ] Kullanici esleme mantigini kur

### Task 10.2: Notification Service

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `notification_service.py` olustur
- [ ] Yeni KAP filing geldiginde ilgili kullanicilari bul
- [ ] Watchlist tabanli esleme yap
- [ ] Bildirim turlerini ayir:
- [ ] KAP filing
- [ ] Financial report
- [ ] Price alert
- [ ] Watchlist digest

### Task 10.3: End-to-End Notification Flow

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] KAP scraper/provider pipeline'a hook ekle
- [ ] Yeni filing -> news -> notification -> Telegram akisina bagla
- [ ] Test: ilgili kullanicilara dogru bildirim gidiyor mu

---

# Phase 8 - Test, Deploy Hazirligi ve Polish

## Week 11: Stabilizasyon ve Kalite

**Tarih:** ___________
**Hedef:** Sistemi kullanilabilir ve test edilebilir seviyeye getirmek
**Durum:** Planned

### Task 11.1: Unit Tests

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] Auth testleri
- [ ] Stocks API testleri
- [ ] Watchlist API testleri
- [ ] Chat API testleri
- [ ] News API testleri
- [ ] Service testleri:
- [ ] market_data_service
- [ ] kap_data_service
- [ ] chunking_service
- [ ] rag_service
- [ ] Mock'lar:
- [ ] borsapy
- [ ] pykap
- [ ] kap_sdk
- [ ] ChromaDB
- [ ] OpenRouter API
- [ ] Minimum coverage hedefi: %70

### Task 11.2: Integration Tests

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] Register -> Login -> Watchlist'e hisse ekle -> News gor -> Chat'te soru sor -> Cevap al
- [ ] Data pipeline testi: KAP filing -> PDF -> chunk -> embed -> retrieve -> AI response
- [ ] Judge agent testi: iyi ve kotu response'lari ayristiriyor mu
- [ ] Notification testi: yeni KAP filing -> Telegram bildirimi
- [ ] Load test: 10 concurrent chat query

### Task 11.3: Operasyonel Sertlestirme

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] Retry stratejileri
- [ ] Cache stratejileri
- [ ] Rate limiting
- [ ] Structured logging
- [ ] Temel hata izleme
- [ ] Timeout policy

### Task 11.4: Polish

**Tahmini Sure:** 2 saat
**Durum:** Planned

- [ ] README'yi yeni local-first akis ile guncelle
- [ ] Kurulum adimlarini sadeleştir
- [ ] Roadmap ile gercek repo yapisini uyumlu hale getir
- [ ] Frontend copy ve source transparency detaylarini temizle

---

## Kritik Basari Kriterleri

- [ ] THYAO gibi bir sembol icin fiyat, finansal tablo ve KAP filing verisi tek backend uzerinden alinabiliyor
- [ ] `borsapy` market data omurgasi stabil calisiyor
- [ ] `pykap` ana KAP provider olarak filing metadata sagliyor
- [ ] `kap_sdk` gerektiğinde fallback olarak devreye alinabiliyor
- [ ] KAP raporlari indirilebiliyor, parse edilebiliyor ve retrieval icin indexlenebiliyor
- [ ] AI chat cevaplari hem market data hem KAP kaynaklariyla destekleniyor
- [ ] Source transparency frontend'de gosterilebiliyor
- [ ] Sistem Docker olmadan local ortamda calisabiliyor

---

## Kalan Ana Riskler

- [ ] `kap_sdk` repo ici kaynak olmadigi icin davranis gorunurlugu sinirli
- [ ] KAP veri yuzeylerinde zaman zaman kirilganlik olabilir
- [ ] Provider'lar arasinda field uyumsuzlugu olabilir
- [ ] PDF kalitesi ve text extraction dogrulugu degisken olabilir
- [ ] AI cevap kalitesi retrieval kalitesine dogrudan bagli kalacak

---

## Son Not

Veri kaynagi secimi bu asamada buyuk olcude cozulmustur. Artik asil is:

- bu uc kaynagi tek abstraction altinda toplamak
- normalize etmek
- kalici hale getirmek
- belge pipeline'ina sokmak
- AI katmanini guvenilir bicimde bunun ustune kurmaktir
