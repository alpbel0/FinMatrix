# FinMatrix 📊

**AI-Powered Stock Analysis Platform for BIST Investors**

FinMatrix is a financial analysis platform where users can query Turkish stock market (BIST) data using natural language. Ask questions like *"Compare THYAO and ASELS net profit over 3 years"* and get dynamically generated charts and AI-powered analysis — backed by real KAP filings and yfinance data.

> ⚠️ FinMatrix never makes buy/sell recommendations. It provides data-driven, unbiased analysis only.



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

### File Structure

```
FinMatrix/
├── index.html          # News Feed page
├── dashboard.html      # Stock Dashboard page
├── chat.html           # AI Chat page
├── watchlist.html      # Watchlist page
├── docs/
│   ├── screenshots/    # UI screenshots
│   └── FinMatrix_Planning_Document.docx
└── README.md
```

---

## 📄 Planning Document

The AI Agent integration planning document is available here:  
👉 [`docs/FinMatrix_Planning_Document.pdf`](docs/FinMatrix_Planning_Document.docx)

It covers:
- Project overview and target users
- Multi-agent architecture (LangGraph + CrewAI + AutoGen + Judge Agent)
- Two-pipeline system design (data ingestion + real-time query)
- EvalOps / hallucination detection layer
- Full development roadmap (7 phases)

---

## 🗺 Development Roadmap

| Phase | Module | Description |
|-------|--------|-------------|
| ✅ 1 | Foundations | React website, mock data, yfinance price charts |
| 🔄 2 | OpenAI | Real LLM chat integration, basic financial Q&A |
| 🔄 3 | CrewAI | CrewAI agents for KAP report analysis |
| 🔄 4 | LangGraph | LangGraph + RAG pipeline + ChromaDB |
| 🔄 5 | AutoGen | AutoGen code execution for dynamic charts |
| 🔄 6 | MCP | MCP data layer, Telegram bot, scheduler |
| 🔄 7 | EvalOps | Judge Agent, hallucination detection, monitoring |

---

## 👤 Author

**Yiğitalp** — [@alpbel0](https://github.com/alpbel0)

---

*March 2026*