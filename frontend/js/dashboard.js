import { Chart, registerables } from "chart.js";
import "chartjs-adapter-luxon";

import { getStocks, getStockDetail, getPriceHistory, getLatestStockSnapshot } from "./stockApi.js";
import { formatLargeNumber, formatPercent, formatRatio } from "./utils/formatters.js";
import { getMetricSourceLabel, getMetricToneClass } from "./utils/metricPresentation.js";

Chart.register(...registerables);

// State
let selectedSymbol = "THYAO";
let priceChart = null;
let searchDebounceId = null;

/**
 * Initialize dashboard with default stock.
 */
export async function initDashboard() {
  // Set up search handlers
  setupSearchHandlers();

  // Load initial stock
  await loadStockData(selectedSymbol);
}

/**
 * Set up search input and button handlers.
 */
function setupSearchHandlers() {
  const searchInput = document.getElementById("stock-search");
  const searchBtn = document.getElementById("search-btn");

  if (!searchInput || !searchBtn) return;

  searchBtn.addEventListener("click", async () => {
    const query = searchInput.value.trim().toUpperCase();
    if (query) {
      await handleSearchSubmit(query);
    }
  });

  searchInput.addEventListener("keydown", async (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const query = searchInput.value.trim().toUpperCase();
      if (query) {
        await handleSearchSubmit(query);
      }
    }
  });

  searchInput.addEventListener("input", () => {
    const query = searchInput.value.trim().toUpperCase();

    if (searchDebounceId) {
      window.clearTimeout(searchDebounceId);
    }

    if (!query) {
      renderSearchResults([]);
      return;
    }

    searchDebounceId = window.setTimeout(async () => {
      await loadSearchResults(query);
    }, 250);
  });
}

async function handleSearchSubmit(query) {
  const results = await loadSearchResults(query);
  const exactMatch = results.find((stock) => stock.symbol === query);

  if (exactMatch) {
    await selectStock(exactMatch.symbol);
    return;
  }

  await selectStock(query);
}

async function loadSearchResults(query) {
  try {
    const response = await getStocks(query);
    const stocks = response.stocks || [];
    renderSearchResults(stocks);
    return stocks;
  } catch {
    renderSearchResults([]);
    return [];
  }
}

async function selectStock(symbol) {
  selectedSymbol = symbol.toUpperCase();
  renderSearchResults([]);
  await loadStockData(selectedSymbol);
}

function renderSearchResults(stocks) {
  const container = document.getElementById("stock-search-results");
  const list = document.getElementById("stock-search-results-list");

  if (!container || !list) return;

  if (!stocks.length) {
    container.style.display = "none";
    list.innerHTML = "";
    return;
  }

  list.innerHTML = stocks.map((stock) => `
    <button
      type="button"
      class="btn btn-secondary"
      data-stock-symbol="${stock.symbol}"
      style="width: 100%; text-align: left; justify-content: flex-start;"
    >
      <span class="badge badge-accent" style="margin-right: var(--space-2);">${stock.symbol}</span>
      <span class="text-muted">${stock.company_name || stock.sector || "No company info"}</span>
    </button>
  `).join("");

  container.style.display = "block";

  list.querySelectorAll("[data-stock-symbol]").forEach((button) => {
    button.addEventListener("click", async () => {
      await selectStock(button.dataset.stockSymbol || "");
    });
  });
}

/**
 * Load all stock data: detail + price history.
 * @param {string} symbol - Stock symbol
 */
async function loadStockData(symbol) {
  showLoading("#dashboard-root");

  try {
    const [stockDetail, priceData, snapshotData] = await Promise.all([
      getStockDetail(symbol),
      getPriceHistory(symbol),
      getLatestStockSnapshot(symbol),
    ]);

    renderStockInfo(stockDetail);
    renderPriceChart(priceData.prices);
    renderQuickStats(snapshotData);
    renderSnapshotHighlights(snapshotData);

    // Update search input
    const searchInput = document.getElementById("stock-search");
    if (searchInput) searchInput.value = symbol;
  } catch (error) {
    showError(error.message);
  }
}

/**
 * Render stock info card.
 * @param {object} stock - Stock detail data
 */
function renderStockInfo(stock) {
  const badge = document.getElementById("stock-symbol-badge");
  const companyName = document.getElementById("stock-company-name");
  const sector = document.getElementById("stock-sector");

  if (badge) badge.textContent = stock.symbol;
  if (companyName) companyName.textContent = stock.company_name || stock.sector || "No company info";
  if (sector) sector.textContent = stock.sector || stock.exchange || "";
}

function renderQuickStats(snapshot) {
  setMetricValue("stat-pe", formatRatio(snapshot.pe_ratio));
  setMetricValue("stat-roe", formatPercent(snapshot.roe));
  setMetricValue("stat-de", formatRatio(snapshot.debt_equity));
  setMetricValue("stat-npg", formatPercent(snapshot.net_profit_growth));

  const statusEl = document.getElementById("snapshot-status");
  if (!statusEl) return;

  const parts = [];
  if (snapshot.snapshot_date) {
    parts.push(`Güncellendi: ${snapshot.snapshot_date}`);
  }

  if (snapshot.is_stale) {
    parts.push(getStaleMessage(snapshot.stale_reason));
  } else {
    parts.push("Veri güncel.");
  }

  if (snapshot.is_partial) {
    parts.push("Bazı alanlar eksik olabilir.");
  }

  statusEl.textContent = parts.join(" • ");
}

function renderSnapshotHighlights(snapshot) {
  const container = document.getElementById("metrics-placeholder");
  if (!container) return;

  container.innerHTML = [
    renderMetricCard("Market Cap", formatLargeNumber(snapshot.market_cap), snapshot.market_cap, snapshot.field_sources?.market_cap),
    renderMetricCard("P/B Ratio", formatRatio(snapshot.pb_ratio), snapshot.pb_ratio, snapshot.field_sources?.pb_ratio),
    renderMetricCard("Dividend Yield", formatPercent(snapshot.dividend_yield), snapshot.dividend_yield, snapshot.field_sources?.dividend_yield),
    renderMetricCard("Free Float", formatPercent(snapshot.free_float), snapshot.free_float, snapshot.field_sources?.free_float),
  ].join("");
}

function renderMetricCard(label, value, rawValue, source) {
  const toneClass = getMetricToneClass(rawValue);
  const sourceLabel = getMetricSourceLabel(source);

  return `
    <div class="card metric-card">
      <div class="metric-value ${toneClass}">${value}</div>
      <div class="metric-label">${label}</div>
      <div class="text-muted">${sourceLabel || ""}</div>
    </div>
  `;
}

/**
 * Render price history chart using Chart.js.
 * @param {Array} prices - Array of {date, close} objects
 */
function renderPriceChart(prices) {
  const canvas = document.getElementById("price-chart");
  const loadingEl = document.getElementById("chart-loading");

  if (!canvas) return;

  // Hide loading, show canvas
  if (loadingEl) loadingEl.style.display = "none";
  canvas.style.display = "block";

  // Chart.js can keep an internal instance even if our module state is reset
  // during a dev reload. Always destroy any existing chart bound to this canvas.
  const existingChart = Chart.getChart(canvas);
  if (existingChart) {
    existingChart.destroy();
  }

  if (priceChart) {
    priceChart.destroy();
  }

  // Prepare data
  const labels = prices.map(p => p.date);
  const closePrices = prices.map(p => p.close ?? 0);

  // Create chart
  const ctx = canvas.getContext("2d");
  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        label: "Close Price (₺)",
        data: closePrices,
        borderColor: "#3b82f6",
        backgroundColor: "rgba(59, 130, 246, 0.1)",
        fill: true,
        tension: 0.3,
        pointRadius: 2,
        pointHoverRadius: 5,
        borderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        },
        tooltip: {
          backgroundColor: "#1e293b",
          titleColor: "#f1f5f9",
          bodyColor: "#94a3b8",
          borderColor: "#334155",
          borderWidth: 1,
          padding: 12,
          cornerRadius: 8,
        }
      },
      scales: {
        x: {
          grid: {
            color: "rgba(51, 65, 85, 0.5)",
            drawBorder: false,
          },
          ticks: {
            color: "#64748b",
            maxTicksLimit: 10,
          }
        },
        y: {
          grid: {
            color: "rgba(51, 65, 85, 0.5)",
            drawBorder: false,
          },
          ticks: {
            color: "#64748b",
            callback: (value) => `₺${value.toFixed(2)}`
          }
        }
      }
    }
  });
}

/**
 * Show loading state in a container.
 * @param {string} selector - CSS selector
 */
function showLoading(selector) {
  const el = document.querySelector(selector);
  resetSnapshotState();
  if (!el) return;

  // Don't replace entire grid - just update specific elements
  const chartLoading = document.getElementById("chart-loading");
  if (chartLoading) chartLoading.style.display = "block";

  const canvas = document.getElementById("price-chart");
  if (canvas) canvas.style.display = "none";
}

/**
 * Show error state.
 * @param {string} message - Error message
 */
function showError(message) {
  const badge = document.getElementById("stock-symbol-badge");
  const companyName = document.getElementById("stock-company-name");

  if (badge) badge.textContent = "ERROR";
  if (companyName) companyName.textContent = message;
  renderSearchResults([]);

  const chartLoading = document.getElementById("chart-loading");
  if (chartLoading) {
    chartLoading.style.display = "block";
    chartLoading.textContent = `Error: ${message}`;
  }

  resetSnapshotState(`Snapshot error: ${message}`);
}

function resetSnapshotState(statusMessage = "Snapshot loading...") {
  setMetricValue("stat-pe", "--");
  setMetricValue("stat-roe", "--");
  setMetricValue("stat-de", "--");
  setMetricValue("stat-npg", "--");

  const statusEl = document.getElementById("snapshot-status");
  if (statusEl) statusEl.textContent = statusMessage;
}

function setMetricValue(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function getStaleMessage(staleReason) {
  switch (staleReason) {
    case "awaiting_daily_sync":
      return "Bu veri son kapanış snapshot’ıdır; gece sync bekleniyor.";
    case "market_closed":
      return "Piyasa kapalı olabilir; son mevcut snapshot gösteriliyor.";
    case "sync_delayed":
      return "Veri güncellenemedi; son başarılı snapshot gösteriliyor.";
    case "no_snapshot":
      return "Henüz snapshot verisi bulunmuyor.";
    default:
      return "Veri güncellik kontrolü bekleniyor.";
  }
}

// Legacy function for backward compatibility (uses mock data)
export function renderDashboard() {
  initDashboard();
}
