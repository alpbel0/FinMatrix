# FinMatrix - Development Roadmap

> Proje: AI-Powered Stock Analysis Platform for BIST Investors
> Baslangic: Nisan 2026
> Tahmini Sure: 10 Hafta
> Yazar: Yigitalp (@alpbel0)
> Gelistirme modeli: Local-first, Docker yok

---

## Genel Bakis

| Phase | Hafta | Odak | Durum |
|---|---|---|---|
| Phase 1 | Week 1-2 | Temel iskelet, database, UI shell, auth temeli | **✅ Completed** |
| Phase 2 | Week 3-4 | Veri kaynaklari + dashboard/watchlist/news slice'lari | Planned |
| Phase 3 | Week 5-6 | RAG, AI chat ve frontend chat deneyimi | Planned |
| Phase 4 | Week 7 | Entegrasyon derinlestirme ve admin/api tamamlama | Planned |
| Phase 5 | Week 8 | EvalOps, Judge ve guvenilirlik | Planned |
| Phase 6 | Week 9 | Telegram bot ve notification sistemi | Planned |
| Phase 7 | Week 10 | Test, deploy hazirligi ve polish | Planned |

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
**Durum:** Planned

- [ ] Filing metadata icinden PDF URL'lerini cikar
- [ ] PDF indirme servisini yaz
- [ ] Indirme hatalarini `pipeline_logs` ile kaydet
- [ ] Gecici veya kalici storage stratejisini netlestir
- [ ] Test: En az 3 farkli KAP raporunu indir

### Task 5.2: PDF Text Extraction ve Chunking

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] `chunking_service.py` olustur
- [ ] PDF -> text extraction yaz
- [ ] Turkce karakterleri dogrula
- [ ] Chunk size: ~500 token
- [ ] Overlap: ~50 token
- [ ] Paragraf sinirina duyarli bolme mantigi yaz
- [ ] Hash hesapla
- [ ] `document_chunks` tablosuna yaz

### Task 5.3: Embedding Pipeline

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] `embedding_service.py` olustur
- [ ] ChromaDB client baglantisini kur
- [ ] Collection olustur: `kap_documents`
- [ ] Embedding modeli sec
- [ ] PENDING chunk'lari embed et
- [ ] Metadata ekle: stock_symbol, report_title, published_at, chunk_index
- [ ] Status alanlarini guncelle

### Task 5.4: Retriever

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `rag/retriever.py` olustur
- [ ] Similarity search yaz
- [ ] Stock symbol metadata filter ekle
- [ ] Source bilgisiyle sonuc don
- [ ] Test: "THYAO net kar" sorgusunda ilgili chunk'lar gelsin

### Task 5.5: CrewAI Text Analysis Agent

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] `agents/text_analyst.py` olustur
- [ ] Role: Financial Text Analyst
- [ ] Goal: KAP raporlarindan sirket analizi cikarmak
- [ ] RAG context + user query -> structured analysis
- [ ] Cikis formati: ozet, riskler, firsatlar, kaynaklar
- [ ] Türkce promptlari optimize et

### Task 5.6: Chat Frontend Ilk Entegrasyon

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `frontend/js/chat.js` icinde session akisini netlestir
- [ ] Mesaj gonderme formunu backend message endpoint'ine bagla
- [ ] Source panel iskeletini hazirla
- [ ] "loading / streaming / source yok" durumlarini goster
- [ ] Ilk duz cevap akisini SSE olmadan calistir

---

## Week 6: Numerical Agent, Orchestrator ve Chat UX Derinlestirme

**Tarih:** ___________
**Hedef:** Sayisal analiz ve agent birlestirme katmanini kurmak
**Durum:** Planned

### Task 6.1: Query Classifier

**Tahmini Sure:** 2 saat
**Durum:** Planned

- [ ] `agents/query_classifier.py` olustur
- [ ] Query type siniflari:
- [ ] text_analysis
- [ ] numerical_analysis
- [ ] comparison
- [ ] general
- [ ] Testler yaz

### Task 6.2: AutoGen Code Executor Agent

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] `agents/code_executor.py` olustur
- [ ] Sayisal veri icin `borsapy` + DB yuzeyini kullan
- [ ] Chart generation akisini yaz
- [ ] Metric hesaplamalari:
- [ ] Net profit growth
- [ ] P/E karsilastirma
- [ ] Debt/Equity
- [ ] ROE
- [ ] Timeout ve sandbox sinirlari ekle
- [ ] Test: THYAO vs ASELS net kar karsilastirmasi

### Task 6.3: Results Merger

**Tahmini Sure:** 2 saat
**Durum:** Planned

- [ ] `agents/merger.py` olustur
- [ ] Text agent + numerical agent ciktilarini birlestir
- [ ] Chart varsa response'a ekle
- [ ] Source referanslarini deduplicate et
- [ ] Comparison tablosu olustur
- [ ] Suggested questionlar uret

### Task 6.4: Orchestrator

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `agents/orchestrator.py` olustur
- [ ] Akis:
- [ ] Query classify
- [ ] Gereken agentlari calistir
- [ ] Sonuclari birlestir
- [ ] Judge'e gonder
- [ ] Son cevabi dondur

### Task 6.5: Agent Unit Tests

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `tests/mocks/mock_openrouter.py`
- [ ] `tests/mocks/mock_langgraph.py`
- [ ] `tests/unit/test_query_classifier.py`
- [ ] `tests/unit/test_rag_retriever.py`
- [ ] `tests/unit/test_judge.py`

### Task 6.6: Chat UX ve Inline Chart

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] Chat cevabindaki chart alanini frontend'de render et
- [ ] Source transparency UI'sini son sekline yaklastir
- [ ] Suggested question alanini ekle
- [ ] Comparison table varsa sag panel veya inline goster
- [ ] Chat gecmisinin temel UI akisini tamamla

---

# Phase 4 - Entegrasyon Derinlestirme

## Week 7: API Bosluklari, Admin ve Capraz Sayfa Entegrasyonu

**Tarih:** ___________
**Hedef:** Kalan API bosluklarini kapatmak ve tum sayfalar arasinda tutarli bir urun akisi olusturmak
**Durum:** Planned

### Task 7.1: Auth API ve Frontend Sertlestirme

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `POST /api/auth/register`
- [ ] `POST /api/auth/login`
- [ ] `GET /api/auth/me`
- [ ] JWT ve password hashing akisini tamamla
- [ ] Frontend token saklama ve logout akisini sertlestir
- [ ] Form validation ve hata mesajlarini duzenle

### Task 7.2: Kalan Stocks/News/Chat API Bosluklari

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] `GET /api/stocks/{symbol}/financials`
- [ ] `GET /api/stocks/{symbol}/kap-reports`
- [ ] `GET /api/chat/sessions`
- [ ] `POST /api/chat/sessions`
- [ ] `POST /api/chat/messages`
- [ ] SSE veya streaming response akisini planla
- [ ] Source transparency formatini frontend'e uygun hale getir

### Task 7.3: Capraz Sayfa Frontend Entegrasyonu

**Tahmini Sure:** 4 saat
**Durum:** Planned

- [ ] `frontend/js/api.js` hata yonetimini merkezilestir
- [ ] Dashboard -> Chat gecislerini bagla
- [ ] News card -> ilgili hisse/dashboard/chat gecislerini bagla
- [ ] Watchlist -> dashboard detay akisini bagla
- [ ] Global loading ve auth expiry davranislarini tutarli hale getir

---

# Phase 5 - EvalOps ve Judge

## Week 8: Guvenilirlik Katmani

**Tarih:** ___________
**Hedef:** Halusinasyon riskini azaltan judge ve eval altyapisini kurmak
**Durum:** Planned

### Task 8.1: Judge Agent

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `agents/judge.py` olustur
- [ ] Faithfulness, relevance, consistency skorlarini hesapla
- [ ] Source desteklenmeyen cevaplari tespit et
- [ ] Retry karari icin cikti ver

### Task 8.2: Eval Metrics

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `eval/metrics.py` olustur
- [ ] BERTScore, ROUGE, retrieval score entegrasyonu
- [ ] `eval_logs` tablosuna kaydet
- [ ] Hallucination raporlama mantigi yaz

### Task 8.3: Retry Handler

**Tahmini Sure:** 2 saat
**Durum:** Planned

- [ ] Dusuk skor durumunda context'i genislet
- [ ] Yeniden retrieval yap
- [ ] Yeniden cevap olustur
- [ ] Retry sayisini logla

### Task 8.4: Eval API

**Tahmini Sure:** 2 saat
**Durum:** Planned

- [ ] `GET /api/admin/eval/stats`
- [ ] `GET /api/admin/hallucinations`
- [ ] `GET /api/admin/pipeline-logs`

---

# Phase 6 - Telegram Bot ve Notification Sistemi

## Week 9: Bildirim Akislari

**Tarih:** ___________
**Hedef:** KAP filing ve watchlist temelli bildirim sistemini kurmak
**Durum:** Planned

### Task 9.1: Telegram Bot Servisi

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] `telegram_service.py` olustur
- [ ] `/start`, `/link` akisini planla
- [ ] Kullanici esleme mantigini kur

### Task 9.2: Notification Service

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

### Task 9.3: End-to-End Notification Flow

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] KAP scraper/provider pipeline'a hook ekle
- [ ] Yeni filing -> news -> notification -> Telegram akisina bagla
- [ ] Test: ilgili kullanicilara dogru bildirim gidiyor mu

---

# Phase 7 - Test, Deploy Hazirligi ve Polish

## Week 10: Stabilizasyon ve Kalite

**Tarih:** ___________
**Hedef:** Sistemi kullanilabilir ve test edilebilir seviyeye getirmek
**Durum:** Planned

### Task 10.1: Unit Tests

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

### Task 10.2: Integration Tests

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] Register -> Login -> Watchlist'e hisse ekle -> News gor -> Chat'te soru sor -> Cevap al
- [ ] Data pipeline testi: KAP filing -> PDF -> chunk -> embed -> retrieve -> AI response
- [ ] Judge agent testi: iyi ve kotu response'lari ayristiriyor mu
- [ ] Notification testi: yeni KAP filing -> Telegram bildirimi
- [ ] Load test: 10 concurrent chat query

### Task 10.3: Operasyonel Sertlestirme

**Tahmini Sure:** 3 saat
**Durum:** Planned

- [ ] Retry stratejileri
- [ ] Cache stratejileri
- [ ] Rate limiting
- [ ] Structured logging
- [ ] Temel hata izleme
- [ ] Timeout policy

### Task 10.4: Polish

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
