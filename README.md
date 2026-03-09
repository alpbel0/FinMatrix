# FinMatrix 📊

**AI-Powered Stock Analysis Platform for BIST Investors**

FinMatrix is a financial analysis platform where users can query Turkish stock market (BIST) data using natural language. Ask questions like *"Compare THYAO and ASELS net profit over 3 years"* and get dynamically generated charts and AI-powered analysis — backed by real KAP filings and yfinance data.

> ⚠️ FinMatrix never makes buy/sell recommendations. It provides data-driven, unbiased analysis only.

---



## ✨ Features

### 📰 News Feed
The main landing page of FinMatrix. Displays a live-updating stream of KAP (Public Disclosure Platform) filings and financial news, filtered specifically for the stocks in your watchlist — so you only see what's relevant to you.

- Filter news by category: **All**, **KAP Filings**, **Activity**, **Financial**
- Each card shows the stock tag, disclosure type, publication time, excerpt, and a direct link to AI analysis
- Left sidebar shows your entire watchlist with live prices and daily change percentages
- Sector-level performance overview (Aviation, Banking, Defense, Retail...)
- Right panel shows the **BIST100 index** with a live mini bar chart, top gainers, top losers, and market summary (total volume, advancing/declining counts)

---

### 📊 Stock Dashboard
A deep-dive analysis page for any individual stock. Search any BIST ticker to instantly load its full financial profile.

- **Price chart** with selectable timeframes: 1D, 1W, 3M, 6M, 1Y, 5Y — powered by yfinance data
- **Key metric cards**: Market Cap, P/E Ratio, Net Profit, ROE — each with sector average comparison and a visual badge (e.g. "Cheap", "Strong")
- **Quarterly net profit bar chart** — visualizes the last 8 quarters side by side to reveal growth trends at a glance
- **Financial summary table** — Revenue, Net Profit, EBITDA, Total Assets, Equity across the last 3 fiscal years
- **Related KAP filings list** — most recent disclosures for the selected stock, directly below the charts

---

### 🤖 AI Chat Interface
The core feature of FinMatrix. Users type natural language questions about any BIST stock and receive AI-generated analysis backed by real KAP reports and financial data.

- Powered by **Gemini Flash + RAG pipeline** — responses are grounded in actual KAP PDF filings, not hallucinated
- **Inline chart generation** — when a question requires visualization (e.g. "compare profits"), a chart is automatically generated and embedded directly inside the chat response
- **Source transparency** — every AI response shows exactly which KAP documents and data sources were used (document name, date, excerpt)
- **Quick comparison table** — side-by-side metric comparison (Net Profit, P/E, ROE, Debt/Equity) rendered in the right panel
- **Session history** — past conversations are saved and accessible from the left sidebar
- **Suggested questions** — context-aware prompt suggestions shown below each response
- **Hallucination protection** — a Judge Agent evaluates every response before delivery; responses that fail the quality check are automatically retried with broader context

Example queries the system handles:
> *"Compare THYAO and ASELS net profit over the last 3 years"*
> *"What does BIMAS's 2025 annual report say about international expansion?"*
> *"What is GARAN's debt situation? Are there any risks?"*

---

### 📋 Watchlist
A personalized dashboard for managing all your tracked stocks in one place.

- Each stock is displayed as a **card** with: company name, live price, daily change, sparkline mini-chart, P/E ratio, market cap, trading volume, and 52-week high
- **Sparkline charts** — color-coded mini charts (green for upward trend, red for downward) rendered per card
- **Telegram notification toggle** — per-stock toggle to enable or disable KAP filing alerts on Telegram
- **Summary stats bar** at the top: total tracked stocks, today's gainers, today's losers, active Telegram alerts
- Add or remove stocks instantly with the **+ Add Stock** button

---

### 📱 Telegram Bot
FinMatrix integrates with Telegram to deliver KAP filing alerts without requiring users to actively check the platform.

- Automatically sends notifications when a tracked stock publishes a new KAP filing
- Notification preferences are managed per-stock directly from the Watchlist page
- Notification types include: KAP filings, financial reports, price alerts, and watchlist digests

---

## 🛠 Technologies Used

| Layer | Technology |
|-------|-----------|
| Frontend | HTML, CSS, JavaScript, Chart.js |
| Stock Data | yfinance (Yahoo Finance) |
| Financial Filings | KAP (kap.org.tr) |
| Charts | Chart.js |
| Hosting | GitHub Pages / Vercel |

### Architecture & Role Separation

One of the core design decisions in FinMatrix is **strict role separation** between AI frameworks to prevent agent chaos — a common failure mode in multi-agent systems where agents duplicate work, conflict, or make redundant API calls.

Each framework has a single, non-overlapping responsibility:

| Agent | Role | Does |
|-------|------|------|
| **LangGraph** | 🧠 Orchestrator | Receives user query, decides which agents to activate, merges results, triggers Judge Agent for quality control |
| **CrewAI** | 📄 Text Analyst | Reads and interprets KAP PDF reports from ChromaDB — summarizes company risks, strategy, and financial narrative |
| **AutoGen** | 📊 Code Executor | Handles all numerical work — writes and runs Python to calculate metrics, generate charts, and process yfinance data |
| **Judge Agent** | ⚖️ Evaluator | Scores every response against source documents before delivery — blocks hallucinated answers and triggers retries |

> LangGraph is the brain. CrewAI reads. AutoGen computes. The Judge verifies. None of them do each other's job.

---

### Planned (Future Assignments)

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python) |
| Orchestration | LangGraph |
| Text Analysis | CrewAI |
| Code Execution | AutoGen |
| Vector Database | ChromaDB |
| Data Layer | MCP (Model Context Protocol) |
| Database | PostgreSQL |
| EvalOps / Judge | LLM-as-Judge + BERTScore + ROUGE |
| LLM | Gemini Flash |
| Notifications | Telegram Bot API |

---

## 🚀 Setup & Run

### Prerequisites
- A modern web browser (Chrome, Firefox, Edge)
- No installation required for the frontend

### Run Locally

```bash
# Clone the repository
git clone https://github.com/alpbel0/FinMatrix.git

# Navigate to project directory
cd FinMatrix

# Open in browser
open index.html
# or simply double-click index.html
```

---

### 🐳 Run with Docker

Docker is used to run the full backend stack (FastAPI + PostgreSQL + ChromaDB) in isolated containers. No manual installation of databases or dependencies needed.

#### Prerequisites
- [Docker](https://www.docker.com/products/docker-desktop) installed
- [Docker Compose](https://docs.docker.com/compose/) installed (included in Docker Desktop)

#### Start all services

```bash
# Clone the repository
git clone https://github.com/alpbel0/FinMatrix.git
cd FinMatrix

# Start all containers
docker-compose up --build
```

This will spin up:
| Container | Service | Port |
|-----------|---------|------|
| `finmatrix-api` | FastAPI backend | `http://localhost:8000` |
| `finmatrix-db` | PostgreSQL database | `5432` |
| `finmatrix-vector` | ChromaDB vector store | `8001` |

#### Stop all services

```bash
docker-compose down
```

#### Stop and wipe all data

```bash
docker-compose down -v
```

#### `docker-compose.yml`

```yaml
version: "3.9"

services:
  api:
    container_name: finmatrix-api
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://finmatrix:finmatrix@db:5432/finmatrix
      - CHROMA_HOST=vector
      - CHROMA_PORT=8001
    depends_on:
      - db
      - vector

  db:
    container_name: finmatrix-db
    image: postgres:15
    restart: always
    environment:
      POSTGRES_USER: finmatrix
      POSTGRES_PASSWORD: finmatrix
      POSTGRES_DB: finmatrix
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  vector:
    container_name: finmatrix-vector
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chroma_data:/chroma/chroma

volumes:
  postgres_data:
  chroma_data:
```

#### API Docs

Once running, FastAPI's auto-generated API documentation is available at:
- Swagger UI → `http://localhost:8000/docs`
- ReDoc → `http://localhost:8000/redoc`

---

### File Structure

```
FinMatrix/
├── index.html               # News Feed page
├── dashboard.html           # Stock Dashboard page
├── chat.html                # AI Chat page
├── watchlist.html           # Watchlist page
├── docker-compose.yml       # Docker services config
├── backend/
│   ├── Dockerfile
│   ├── main.py              # FastAPI entry point
│   ├── requirements.txt
│   └── ...
├── docs/
│   ├── screenshots/         # UI screenshots
│   └── FinMatrix_Planning_Document.pdf
└── README.md
```

---

## 🗄 Database Schema

FinMatrix uses **PostgreSQL** as the primary relational database. The schema is designed to be production-ready with partitioning, indexing, unique constraints, and a full EvalOps layer for hallucination tracking.

### Users & Auth

```sql
CREATE TABLE users (
    id                   SERIAL PRIMARY KEY,
    username             VARCHAR(50) UNIQUE NOT NULL,
    email                VARCHAR(255) UNIQUE NOT NULL,
    password_hash        TEXT NOT NULL,
    telegram_chat_id     BIGINT,
    notification_enabled BOOLEAN DEFAULT TRUE,
    created_at           TIMESTAMP DEFAULT NOW(),
    updated_at           TIMESTAMP DEFAULT NOW()
);

CREATE TABLE telegram_settings (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_times  JSONB,   -- e.g. ["09:00", "18:00"]
    event_types         JSONB,   -- e.g. ["kap_news", "price_alert", "financial_report", "watchlist_digest"]
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id)
);
```

### Stocks & Watchlist

```sql
CREATE TABLE stocks (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) UNIQUE NOT NULL,  -- e.g. "THYAO"
    yfinance_symbol VARCHAR(20),                  -- e.g. "THYAO.IS"
    company_name    VARCHAR(255),
    sector          VARCHAR(100),
    exchange        VARCHAR(20) DEFAULT 'BIST',
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE watchlist (
    id                   SERIAL PRIMARY KEY,
    user_id              INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stock_id             INT NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    added_at             TIMESTAMP DEFAULT NOW(),
    notification_enabled BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, stock_id)
);
```

### Price & Financial Data

```sql
-- Monthly partitioned for performance
CREATE TABLE stock_prices (
    stock_id  INT NOT NULL REFERENCES stocks(id),
    timestamp TIMESTAMP NOT NULL,
    open      NUMERIC(12,4),
    high      NUMERIC(12,4),
    low       NUMERIC(12,4),
    close     NUMERIC(12,4),
    volume    BIGINT,
    PRIMARY KEY (stock_id, timestamp)
) PARTITION BY RANGE (timestamp);

CREATE TABLE balance_sheets (
    id                SERIAL PRIMARY KEY,
    stock_id          INT NOT NULL REFERENCES stocks(id),
    period            VARCHAR(10),  -- "annual" | "quarterly"
    date              DATE NOT NULL,
    fiscal_year       INT,
    fiscal_quarter    INT,
    total_assets      NUMERIC(20,2),
    total_liabilities NUMERIC(20,2),
    equity            NUMERIC(20,2),
    cash              NUMERIC(20,2),
    total_debt        NUMERIC(20,2),
    created_at        TIMESTAMP DEFAULT NOW(),
    UNIQUE(stock_id, period, date)
);

CREATE TABLE income_statements (
    id               SERIAL PRIMARY KEY,
    stock_id         INT NOT NULL REFERENCES stocks(id),
    period           VARCHAR(10),
    date             DATE NOT NULL,
    fiscal_year      INT,
    fiscal_quarter   INT,
    revenue          NUMERIC(20,2),
    net_income       NUMERIC(20,2),
    operating_income NUMERIC(20,2),
    gross_profit     NUMERIC(20,2),
    ebitda           NUMERIC(20,2),
    created_at       TIMESTAMP DEFAULT NOW(),
    UNIQUE(stock_id, period, date)
);

CREATE TABLE cash_flows (
    id                  SERIAL PRIMARY KEY,
    stock_id            INT NOT NULL REFERENCES stocks(id),
    period              VARCHAR(10),
    date                DATE NOT NULL,
    fiscal_year         INT,
    fiscal_quarter      INT,
    operating_cash_flow NUMERIC(20,2),
    investing_cash_flow NUMERIC(20,2),
    financing_cash_flow NUMERIC(20,2),
    free_cash_flow      NUMERIC(20,2),
    created_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE(stock_id, period, date)
);
```

### KAP Reports & News

```sql
CREATE TYPE sync_status AS ENUM ('PENDING', 'SUCCESS', 'FAILED');

CREATE TABLE kap_reports (
    id                 SERIAL PRIMARY KEY,
    stock_id           INT NOT NULL REFERENCES stocks(id),
    title              TEXT NOT NULL,
    pdf_url            TEXT,           -- Cloudflare R2 / DO Spaces URL
    published_date     DATE,
    fetched_date       TIMESTAMP,
    chroma_sync_status sync_status DEFAULT 'PENDING',
    chunk_count        INT DEFAULT 0,
    created_at         TIMESTAMP DEFAULT NOW(),
    UNIQUE(stock_id, title, published_date)
);

CREATE TYPE news_source AS ENUM ('kap_summary', 'external_news', 'manual');

CREATE TABLE news (
    id             SERIAL PRIMARY KEY,
    stock_id       INT REFERENCES stocks(id),
    title          TEXT NOT NULL,
    content        TEXT,
    published_date TIMESTAMP,
    source_type    news_source DEFAULT 'kap_summary',
    source_ref_id  INT,   -- nullable FK to kap_reports.id
    created_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE user_news (
    id      SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    news_id INT NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP,
    UNIQUE(user_id, news_id)
);
```

### Chat & AI Messages

```sql
CREATE TABLE chat_sessions (
    id              SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(255),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    last_message_at TIMESTAMP
);

CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system');
CREATE TYPE message_type AS ENUM ('text', 'chart', 'table', 'system');

CREATE TABLE chat_messages (
    id           SERIAL PRIMARY KEY,
    session_id   INT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role         message_role NOT NULL,
    content      TEXT NOT NULL,
    message_type message_type DEFAULT 'text',
    metadata     JSONB,   -- chart config, agent info, etc.
    sources      JSONB,   -- KAP document references used
    timestamp    TIMESTAMP DEFAULT NOW()
);

-- SQL as source of truth for ChromaDB chunk sync
CREATE TYPE embedding_status AS ENUM ('PENDING', 'SUCCESS', 'FAILED');

CREATE TABLE document_chunks (
    id                 SERIAL PRIMARY KEY,
    kap_report_id      INT NOT NULL REFERENCES kap_reports(id) ON DELETE CASCADE,
    chunk_index        INT NOT NULL,
    chunk_text_hash    TEXT,
    chroma_document_id TEXT,
    embedding_status   embedding_status DEFAULT 'PENDING',
    created_at         TIMESTAMP DEFAULT NOW(),
    UNIQUE(kap_report_id, chunk_index)
);
```

### EvalOps — Hallucination Detection

```sql
CREATE TYPE pipeline_status AS ENUM ('PENDING', 'RUNNING', 'SUCCESS', 'FAILED');

CREATE TABLE pipeline_logs (
    id              SERIAL PRIMARY KEY,
    run_id          UUID UNIQUE NOT NULL,
    pipeline_name   VARCHAR(100),
    job_name        VARCHAR(100),
    step_name       VARCHAR(100),
    stock_id        INT REFERENCES stocks(id),   -- nullable
    status          pipeline_status DEFAULT 'PENDING',
    started_at      TIMESTAMP,
    finished_at     TIMESTAMP,
    error_message   TEXT,
    processed_count INT DEFAULT 0,
    details         JSONB
);

CREATE TABLE eval_logs (
    id                 SERIAL PRIMARY KEY,
    message_id         INT NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    pipeline_run_id    UUID REFERENCES pipeline_logs(run_id),
    bert_score         FLOAT,
    rouge_score        FLOAT,
    retrieval_score    FLOAT,
    judge_model_used   VARCHAR(100),
    judge_reason       TEXT,
    is_hallucinated    BOOLEAN DEFAULT FALSE,
    retry_count        INT DEFAULT 0,
    source_chunks_used JSONB,
    details            JSONB,
    timestamp          TIMESTAMP DEFAULT NOW()
);

-- View: no separate table needed
CREATE VIEW hallucination_reports AS
    SELECT * FROM eval_logs WHERE is_hallucinated = TRUE;
```

### Indexes

```sql
CREATE INDEX idx_users_email             ON users(email);
CREATE INDEX idx_watchlist_user          ON watchlist(user_id);
CREATE INDEX idx_stock_prices_stock_time ON stock_prices(stock_id, timestamp);
CREATE INDEX idx_chat_messages_session   ON chat_messages(session_id, timestamp);
CREATE INDEX idx_eval_hallucinated       ON eval_logs(is_hallucinated, pipeline_run_id);
CREATE INDEX idx_document_chunks_report  ON document_chunks(kap_report_id);
CREATE INDEX idx_pipeline_logs_run_id    ON pipeline_logs(run_id);
```

---



## 👤 Author

**Yiğitalp** — [@alpbel0](https://github.com/alpbel0)

---

*March 2026*