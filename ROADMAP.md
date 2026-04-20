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
| Phase 4 | Week 7 | LangGraph Bridge - Agent Graph Mimarisi | Planned |
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

### Task 5.2: PDF Text Extraction ve Chunking

**Tahmini Sure:** 4 saat
**Durum:** Completed

- [x] `chunking_service.py` olustur
- [x] PDF -> text extraction yaz (pdfplumber)
- [x] Turkce karakterleri dogrula
- [x] Chunk size: ~500 token
- [x] Overlap: ~50 token
- [x] Paragraf sinirina duyarli bolme mantigi yaz
- [x] Hash hesapla (SHA-256)
- [x] `document_chunks` tablosuna yaz
- [x] Boilerplate filtering (cover page, TOC, short blocks, low alpha ratio)
- [x] Empty PDF handling (COMPLETED + chunking_error)
- [x] Unique constraint: (kap_report_id, chunk_text_hash)
- [x] KapReport modeline chunking_status, chunking_error, chunked_at alanlari eklendi
- [x] Scheduled job: `chunking_hourly` (hourly)
- [x] Unit tests: 39 tests passing

### Task 5.3: Embedding Pipeline

**Tahmini Sure:** 4 saat
**Durum:** Completed

- [x] `embedding_service.py` olustur
- [x] ChromaDB client baglantisini kur
- [x] Collection olustur: `kap_documents`
- [x] Embedding modeli sec: openai/text-embedding-3-small (1536 dim)
- [x] PENDING chunk'lari embed et (OpenRouter API)
- [x] Metadata ekle: stock_symbol, report_title, published_at, chunk_index, filing_type, kap_report_id
- [x] Status alanlarini guncelle (EmbeddingStatus enum: PENDING/COMPLETED/FAILED)
- [x] Batch processing: 100 chunks per API call, 500 chunks per scheduler run
- [x] Scheduled job: `embedding_10min` (every 10 minutes)
- [x] Unit tests: 25 tests passing

### Task 5.4: Retriever

**Tahmini Sure:** 3 saat
**Durum:** Completed

- [x] `rag/retriever.py` olustur
- [x] Similarity search yaz (L2 distance)
- [x] Stock symbol metadata filter ekle
- [x] Source bilgisiyle sonuc don (RetrievedChunk model)
- [x] Dedup by chunk_text_hash
- [x] Unit tests: 17 tests passing

### Task 5.5: Query Understanding + Retrieval + Response Agent Layer

**Tahmini Sure:** 5 saat
**Durum:** Completed

- [x] `schemas/enums.py` olustur - DocumentType, QueryIntent enums
- [x] `config.py` - LLM model settings (query_understanding_model, response_agent_model)
- [x] `services/agents/symbol_resolver.py` - DB lookup + alias fallback
- [x] `services/agents/prompt_loader.py` - YAML prompt loader
- [x] `prompts/query_understanding.yaml` - Query analysis prompt
- [x] `services/agents/query_understanding_agent.py` - Intent/symbol extraction
- [x] `services/agents/retrieval_agent.py` - Deterministic retrieval wrapper
- [x] `prompts/response_agent.yaml` - Response generation prompt
- [x] `services/agents/response_agent.py` - Turkish response with citations
- [x] `services/chat_rag_service.py` - Pipeline orchestration
- [x] Multi-factor sufficiency check (distance + length + count)
- [x] Soft fallback for insufficient context
- [x] Greeting handling (belge odaklı yönlendirme)
- [x] Unit tests: 87 tests passing
- Models: query_understanding=gemma-4-26b, response=gemini-3.1-flash-lite

### Task 5.6: Chat Frontend Ilk Entegrasyon

**Tahmini Sure:** 3 saat
**Durum:** Completed

- [x] `services/chat_service.py` - Session/message management
- [x] `routers/chat.py` - API endpoints (GET/POST sessions, POST messages)
- [x] `models/chat.py` - sources_metadata JSONB field
- [x] `alembic/versions/a1b2c3d4e5f7_add_sources_metadata_to_chat_messages.py`
- [x] `frontend/js/api.js` - Chat API functions (getChatSessions, createChatSession, sendChatMessage)
- [x] `frontend/js/chat.js` - Real API connection, source panel rendering
- [x] `frontend/chat.html` - Source cards UI, loading state
- [x] Chat session creation + message persistence
- [x] Source transparency in frontend

### Task 5.7: Chat/RAG Trace Logging

**Tahmini Sure:** 3 saat
**Durum:** Completed

- [x] `models/chat_trace.py` olustur
- [x] `alembic/versions/b9d0e1f2a3b4_add_chat_traces.py` migration dosyasini ekle
- [x] `services/chat_trace_service.py` - structured trace persistence
- [x] `chat_service.py` icinde user_message_id / assistant_message_id ile trace lifecycle kur
- [x] Query understanding payload'ini JSONB olarak kaydet
- [x] Retrieval summary + source metadata'yi JSONB olarak kaydet
- [x] Response summary + insufficient_context bilgisini kaydet
- [x] resolved_symbol, document_type, intent, confidence gibi debug alanlarini sakla
- [x] duration_ms ve error_message alanlarini doldur
- [x] Basarili ve hatali akislari ayri status ile logla (`SUCCESS` / `FAILED`)
- [x] Unit tests: `test_chat_trace_service.py`

---

## Week 6: CrewAI Orchestration, Numerical Analysis ve Chat UX Derinlestirme

**Tarih:** ___________
**Hedef:** CrewAI tabanli agent koordinasyonunu kurmak, sayisal analiz akisini eklemek ve chat deneyimini daha analist seviyesine tasimak
**Durum:** Completed

### Week 6 Mimari Karari: Hibrit CrewAI

Bu hafta itibariyla agent orchestration katmani CrewAI ile kurulacak. Ancak tum is mantigi CrewAI icine gomulmeyecek.

**CrewAI olacak katmanlar:**
- [x] Query classifier agent
- [x] Text analyst agent
- [x] Code executor agent
- [x] Results merger agent
- [x] Orchestrator / crew wiring

**Custom kalacak katmanlar:**
- [x] Retrieval servisleri (`rag/retriever.py`, `services/agents/retrieval_agent.py`)
- [x] Symbol resolution ve enum normalization
- [x] Deterministic finansal hesaplar ve metric helper'lari
- [x] Chart data generation
- [x] DB yazimlari, API response schema'lari ve trace logging
- [x] Frontend render mantigi

**Temel ilke:**
- [x] LLM agent karar verir, custom kod icra eder
- [x] Sayisal hesaplar LLM'e birakilmaz
- [x] Retrieval ve persistence framework bagimsiz kalir

### Task 6.1: CrewAI Query Classifier

**Tahmini Sure:** 2 saat
**Durum:** Completed

- [x] `services/agents/query_classifier.py` dosyasini CrewAI uyumlu hale getir
- [x] Query type siniflarini netlestir:
- [x] `text_analysis`
- [x] `numerical_analysis`
- [x] `comparison`
- [x] `general`
- [x] Classifier output'unu structured schema ile sabitle
- [x] Orchestrator'a karar verebilir sinyaller ekle:
- [x] symbol list
- [x] comparison flag
- [x] chart_needed flag
- [x] Heuristic-first classification ekle
- [x] OpenRouter LLM fallback ekle
- [x] CrewAI adapter / agent role boundary ekle
- [x] Testler yaz

### Task 6.2: CrewAI Text Analyst Agent

**Tahmini Sure:** 3 saat
**Durum:** Completed

- [x] `services/agents/text_analyst.py` dosyasini CrewAI uyumlu role wrapper olarak kur
- [x] Mevcut RAG retrieval katmanini tool/service olarak kullan
- [x] Kaynakli text analysis uret
- [x] Risk/firsat/ozet sorularinda belge tabanli analiz ver
- [x] Retrieval sonucu ve source metadata'yi structured output olarak don
- [x] Fallback: retrieval bos veya zayifsa hallucination yerine soft failure don
- [x] TextAnalysisResult schema ekle
- [x] Unit testler yaz
- [x] Canli THYAO smoke testi yap

### Task 6.3: CrewAI Code Executor Agent

**Tahmini Sure:** 4 saat
**Durum:** ✅ Completed

- [x] `services/agents/code_executor.py` olustur
- [x] Agent'in rolunu "deterministic calculators'i cagiran karar katmani" olarak tasarla
- [x] Sayisal veri icin `borsapy` + DB yuzeyini kullan
- [x] Deterministic metric helper'lari yaz / bagla:
- [x] Net profit growth
- [x] P/E comparison
- [x] Debt/Equity
- [x] ROE
- [x] Chart data generation akisini ekle
- [x] Timeout ve sandbox sinirlari belirle
- [x] Test: `THYAO vs ASELS net kar` karsilastirmasi (40 test gecti)

### Task 6.4: CrewAI Results Merger

**Tahmini Sure:** 2 saat
**Durum:** ✅ Completed

- [x] `services/agents/merger.py` olustur
- [x] Text agent + numerical agent ciktilarini birlestir
- [x] Source referanslarini deduplicate et
- [x] Comparison table payload'i hazirla
- [x] Chart varsa final response schema'sina ekle
- [x] Suggested questions icin frontend'e uygun sabit button akisini destekle
- [x] Final output'u frontend dostu structured response'a cevir

### Task 6.5: CrewAI Orchestrator

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] `services/agents/orchestrator.py` olustur
- [x] Akis: Query classify → numerical/text analysis → merge (sequential)
- [x] Sonuclari birlestir: numerical once (yapilandirilmis metin/tablo/chart), sonra text (paragraf)
- [x] Final cevabi dondur: `run_orchestrated_pipeline` → `ChatPipelineResult`
- [x] Chat service baglantisi: orchestrator hazir, `chat_service.py` guncellemesi Task 6.5 scope'unda
- [x] Agent'lar: `classify_query`, `run_text_analysis`, `run_numerical_analysis` entegre
- [ ] Judge entegrasyonu icin hook birak, ama judge'i Week 8 scope'unda tut

### Task 6.6: Agent Tests ve Mock Katmani

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] `tests/mocks/mock_openrouter.py`
- [x] `tests/mocks/mock_crewai.py`
- [x] `tests/unit/test_query_classifier.py` (17 tests)
- [x] `tests/unit/test_text_analyst.py` (8 tests)
- [x] `tests/unit/test_code_executor.py` (40 tests)
- [x] `tests/unit/test_merger.py` (6 tests)
- [x] `tests/unit/test_orchestrator.py` (8 tests)
- [x] `tests/unit/test_agent_trace_logging.py` (15 tests)

### Task 6.7: Chat UX ve Inline Chart

**Tahmini Sure:** 3 saat
**Durum:** ✅ Completed

- [x] Chat cevabindaki chart alanini frontend'de render et
- [x] Source transparency UI'sini son sekline yaklastir
- [x] Suggested questions alanini ekle (frontend'de sabit 3 button, sticky behavior)
- [x] Comparison table varsa inline HTML tablo olarak goster
- [x] Chat gecmisinin temel UX akisini tamamla
- [x] Numerical/text/comparison cevap tipleri icin uygun render farklarini ekle

### Week 6 Sonunda Beklenen Cikti

- [x] Chat artik sadece belge cevabi degil, soru tipine gore agent secen bir sisteme donusmus olacak
- [x] Sayisal sorular deterministic hesaplarla cevaplanacak
- [x] Karsilastirma sorulari tek cevapta analiz + tablo + chart ile donulebilecek
- [x] CrewAI, agent koordinasyon katmaninda aktif olarak kullaniliyor olacak
- [x] Retrieval, DB, trace ve chart payload katmanlari halen custom ve debug edilebilir kalacak

---

# Phase 4 - LangGraph Bridge: Agent Graph Mimarisi

## Week 7: Orchestrator'i LangGraph ile Yeniden Yaz

**Tarih:** ___________
**Hedef:** Mevcut if/else orchestrator mantigini tipli, izlenebilir ve genisletilebilir bir LangGraph state machine'e donusturmek
**Durum:** In Progress

---

### Task 7.1: Altyapi ve Hazirlik

**Tahmini Sure:** 1 saat
**Durum:** ✅ Completed

- [x] `langgraph>=0.2.0,<1.0.0` paketini `backend/requirements.txt` dosyasina ekle
- [x] `langgraph` kurulumunu dogrula: `python -c "import langgraph"` basarili
- [x] `backend/app/services/agents/graph/` klasorunu olustur
- [x] `backend/app/services/agents/graph/__init__.py` dosyasini olustur (bos, sadece export icin)
- [x] `backend/app/services/agents/graph/state.py` bos dosyasini olustur
- [x] `backend/app/services/agents/graph/nodes.py` bos dosyasini olustur
- [x] `backend/app/services/agents/graph/workflow.py` bos dosyasini olustur
- [x] Mevcut `test_orchestrator.py`'deki 8 testin gectigini kaydet (baseline coverage)
- [x] Mevcut `test_agent_trace_logging.py`'deki 15 testin gectigini kaydet (baseline coverage)

---

### Task 7.2: State Tasarimi (state.py)

**Tahmini Sure:** 1.5 saat
**Durum:** ✅ Completed

**Implemente edilen:**
- [x] `state.py` dosyasi dolu — `NodeTraceEntry` + `AgentState` TypedDict tanimlari
- [x] `AgentState` 11 alan: query, user_id, session_id, http_client, classification, resolved_symbol, text_result, numerical_result, response, fallback_reason, node_history
- [x] `node_history` icin `Annotated[list[NodeTraceEntry], operator.add]` parallel-safe reducer
- [x] `graph/__init__.py` export eklendi
- [x] `test_graph_state.py` — 11 test gecti (4 NodeTraceEntry + 7 AgentState)

---

### Task 7.3: Ince Dugumler - Thin Nodes (nodes.py)

**Tahmini Sure:** 3 saat
**Durum:** Planned

**Yardimci fonksiyonlar:**
- [ ] `_start_trace(node_name: str) -> float` yaz: `time.time()` ile baslangic zamanini don
- [ ] `_make_entry(node: str, start: float, status: str, reason_code: str | None) -> NodeTraceEntry` yaz
- [ ] Her node'un yeni bir `dict` ile state donerken `node_history` listesini extend ettigini dogrula

**classify_query_node:**
- [ ] `classify_query` servisini `state["query"]` ile cagir
- [ ] Sonucu `classification` alanina yaz
- [ ] Basarisiz olursa: `fallback_reason = "classification_failed"`, status="error"
- [ ] `node_history`'ye NodeTraceEntry ekle (her iki durumda da)
- [ ] Return: degisen sadece `classification`, `fallback_reason`, `node_history`

**resolve_symbol_node:**
- [ ] `classification` None ise veya `classification.symbols` bos ise: no-op (status="skipped")
- [ ] `resolve_symbol(db, classification.symbols[0])` cagir
- [ ] Sonucu `resolved_symbol` alanina yaz
- [ ] Sembol cozulemezse: `fallback_reason = "symbol_not_resolved"`, status="error"
- [ ] `node_history`'ye NodeTraceEntry ekle

**numerical_analysis_node:**
- [ ] **KRITIK**: `run_numerical_analysis`'e `state["resolved_symbol"]`'i parametre olarak gec
- [ ] `code_executor.py` icindeki ic resolve_symbol cagrisini bypass etmek icin `symbols=[resolved_symbol]` kullan
- [ ] `numerical_result` alanina yaz
- [ ] Hata durumunda: `fallback_reason = "numerical_failed"`, status="error"
- [ ] `node_history`'ye NodeTraceEntry ekle

**text_analysis_node:**
- [ ] `run_text_analysis` servisini cagir
- [ ] `text_result` alanina yaz
- [ ] Hata durumunda: `fallback_reason = "text_failed"`, status="error"
- [ ] `node_history`'ye NodeTraceEntry ekle

**merge_node:**
- [ ] `merge_analysis_results(classification, resolved_symbol, numerical_result, text_result)` cagir
- [ ] Sonucu `response` alanina yaz
- [ ] `node_history`'ye NodeTraceEntry ekle

**fallback_node:**
- [ ] `run_document_pipeline(db, user_id, session_id, query)` cagir (mevcut RAG pipeline)
- [ ] Sonucu `response` alanina yaz
- [ ] `state["fallback_reason"]` degerini NodeTraceEntry'nin `reason_code`'una ekle
- [ ] `node_history`'ye NodeTraceEntry ekle

---

### Task 7.4: Is Akisi ve Guvenli Singleton (workflow.py)

**Tahmini Sure:** 2 saat
**Durum:** Planned

**Graph iskelet:**
- [ ] `StateGraph(AgentState)` olustur
- [ ] `add_node("classify_query", classify_query_node)` ekle
- [ ] `add_node("resolve_symbol", resolve_symbol_node)` ekle
- [ ] `add_node("numerical_analysis", numerical_analysis_node)` ekle
- [ ] `add_node("text_analysis", text_analysis_node)` ekle
- [ ] `add_node("merge", merge_node)` ekle
- [ ] `add_node("fallback", fallback_node)` ekle

**Entry ve edge'ler:**
- [ ] `set_entry_point("classify_query")` ile baslangic node'unu belirle
- [ ] `classify_query → resolve_symbol` duz edge ekle
- [ ] `resolve_symbol` → routing fonksiyonu `_route_after_symbol` ile conditional edge ekle:
  - [ ] `classification is None` veya `fallback_reason is not None` → `"fallback"`
  - [ ] `QueryType.GENERAL` → `"fallback"`
  - [ ] `needs_numerical_analysis AND needs_text_analysis` → `"numerical_analysis"` (oncelikli)
  - [ ] `needs_numerical_analysis` → `"numerical_analysis"`
  - [ ] `needs_text_analysis` → `"text_analysis"`
  - [ ] default → `"fallback"`
- [ ] `numerical_analysis` → routing fonksiyonu `_route_after_numerical` ile conditional edge ekle:
  - [ ] `classification.needs_text_analysis` → `"text_analysis"`
  - [ ] default → `"merge"`
- [ ] `text_analysis → merge` duz edge ekle
- [ ] `merge → END` edge ekle
- [ ] `fallback → END` edge ekle

**Singleton pattern:**
- [ ] Module-level `_compiled_graph = None` tanimla
- [ ] `build_workflow() -> StateGraph` fonksiyonu yaz (graph'i compile etmeden don)
- [ ] `get_graph()` fonksiyonu yaz:
  - [ ] `global _compiled_graph` kullan
  - [ ] `_compiled_graph is None` ise `build_workflow().compile()` cagir
  - [ ] Compile edilmis graph'i cache'le ve don
- [ ] `graph/__init__.py`'ye `get_graph` export et

---

### Task 7.5: Yeni Graph Testleri (TDD - Once Bunlar!)

**Tahmini Sure:** 3 saat
**Durum:** Planned

**test_graph_state.py:**
- [ ] `NodeTraceEntry`'nin tum alanlarini (`node`, `status`, `duration_ms`, `reason_code`) icerigini dogrula
- [ ] `AgentState`'in minimal required alanlari ile olusturulabildigini dogrula
- [ ] `node_history`'nin bos list ile basladigini dogrula
- [ ] `fallback_reason`'in default `None` oldugunu dogrula
- [ ] `resolved_symbol`'un default `None` oldugunu dogrula

**test_graph_nodes.py:**
- [ ] `classify_query_node` mock ile cagrildiginda `state["classification"]` doldugunu dogrula
- [ ] `classify_query_node` hata verdikten sonra `state["fallback_reason"] == "classification_failed"` oldugunu dogrula
- [ ] `resolve_symbol_node` sembol listesi bos oldugunda status="skipped" kaydettidgini dogrula
- [ ] `resolve_symbol_node` calistiktan sonra `state["resolved_symbol"]` doldugunu dogrula
- [ ] `numerical_analysis_node` calistiktan sonra `state["numerical_result"]` doldugunu dogrula
- [ ] `text_analysis_node` calistiktan sonra `state["text_result"]` doldugunu dogrula
- [ ] `merge_node` calistiktan sonra `state["response"]` doldugunu dogrula
- [ ] `fallback_node` calistiktan sonra `state["response"]` doldugunu dogrula
- [ ] Her node'un `node_history`'ye tam olarak 1 entry ekledigini dogrula

**test_graph_routing.py:**
- [ ] `test_graph_routing_text`: TEXT_ANALYSIS sorusu → `text_analysis_node` calisip `text_result` doldu mu?
- [ ] `test_graph_routing_numerical`: NUMERICAL sorusu → `numerical_analysis_node` calisip `numerical_result` doldu mu?
- [ ] `test_graph_routing_general`: GENERAL sorusu → `fallback_node` calisip `response` doldu mu?
- [ ] `test_graph_routing_both_types`: Hem text hem numerical gerektiginde ikiside de calisip merge yapildi mi?
- [ ] `test_graph_routing_comparison`: COMPARISON sorusu → dogru node'lara gitti mi?

**test_graph_fallback.py:**
- [ ] `test_graph_fallback_on_general_query`: GENERAL → fallback_node cagrildi mi?
- [ ] `test_graph_fallback_on_classification_error`: classify hata verirse fallback devreye girdi mi?
- [ ] `test_graph_fallback_reason_set`: fallback sonrasi `state["fallback_reason"]` dolu mu?
- [ ] `test_graph_fallback_returns_pipeline_result`: fallback_node `ChatPipelineResult` dondu mu?

**test_graph_trace_history.py:**
- [ ] `test_graph_trace_history_populated`: Her calistirilan node icin `node_history`'de kayit var mi?
- [ ] `test_graph_trace_entry_fields`: Her `NodeTraceEntry`'de `node`, `status`, `duration_ms`, `reason_code` var mi?
- [ ] `test_graph_trace_order`: `node_history` sirasi execution sirasiyla uyusuyor mu?
- [ ] `test_graph_trace_duration_positive`: Her kaydin `duration_ms > 0` oldugunu dogrula
- [ ] `test_graph_trace_error_status`: Hata veren node'un status="error" kaydettidgini dogrula

---

### Task 7.6: Orchestrator Refactor (Son Adim)

**Tahmini Sure:** 2 saat
**Durum:** Planned

**Refactor:**
- [ ] `orchestrator.py`'deki `run_orchestrated_pipeline` imzasini koru (disaridan cagrilan yer degismemeli)
- [ ] Icerdeki tum `if/else` routing mantigini sil
- [ ] `from app.services.agents.graph import get_graph` import et
- [ ] `initial_state: AgentState` olustur: tum zorunlu alanlari doldur
- [ ] `graph = get_graph()` ile graph'i al
- [ ] `final_state = await graph.ainvoke(initial_state)` ile grafigi calistir
- [ ] `final_state["response"]` → `ChatPipelineResult` olarak don
- [ ] `final_state["resolved_symbol"]` → `ChatPipelineResult.resolved_symbol`
- [ ] `final_state["node_history"]` → `chat_trace_service`'e ozet olarak gec

**Trace entegrasyonu:**
- [ ] `node_history` ozetini mevcut `chat_trace_service` trace yapisina yaz
- [ ] Graph summary: kac node calistigini, toplam sure ve son `fallback_reason`'i logla
- [ ] `build_orchestrator_agent()` ve `get_orchestrator_agent()` fonksiyonlarini sil ya da koru (geriye donuk uyumluluk)

**Dogrulama:**
- [ ] `pytest backend/tests/unit/test_orchestrator.py -v` → tum 8 test gec
- [ ] `pytest backend/tests/unit/test_agent_trace_logging.py -v` → tum 15 test gec
- [ ] `pytest backend/tests/unit/ -v` → hicbir mevcut test kirilmamali
- [ ] `pytest backend/tests/unit/test_graph_routing.py -v` → tum yeni graph testleri gec
- [ ] `pytest backend/tests/unit/test_graph_trace_history.py -v` → trace testleri gec

---

### Week 7 Sonunda Beklenen Cikti

- [ ] Orchestrator artik if/else yerine LangGraph graph ile yonlendiriyor
- [ ] Her sorgu turu dogru node zincirinden geciyor
- [ ] `node_history` her sorgu icin doluyor ve trace'e yaziliyor
- [ ] `fallback_reason` debug icin state'te mevcut
- [ ] Mevcut tum testler kiriilmadan geciyor
- [ ] Yeni graph testleri (routing, fallback, trace) gecmis durumda

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
