import { Chart, registerables } from "chart.js";
import "chartjs-adapter-luxon";

import { getStocks, getStockDetail, getPriceHistory } from "./stockApi.js";

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
      class="card"
      data-stock-symbol="${stock.symbol}"
      style="width: 100%; text-align: left; margin-top: 8px;"
    >
      <div class="card-header">
        <span class="badge">${stock.symbol}</span>
        <span class="muted">${stock.company_name || stock.sector || "No company info"}</span>
      </div>
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
    // Fetch stock detail
    const stockDetail = await getStockDetail(symbol);
    renderStockInfo(stockDetail);

    // Fetch price history
    const priceData = await getPriceHistory(symbol);
    renderPriceChart(priceData.prices);

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

  if (badge) badge.textContent = stock.symbol;
  if (companyName) companyName.textContent = stock.company_name || stock.sector || "No company info";
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
        borderColor: "#1a7f64",
        backgroundColor: "rgba(26, 127, 100, 0.1)",
        fill: true,
        tension: 0.1,
        pointRadius: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        }
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 10,
          }
        },
        y: {
          beginAtZero: false,
          ticks: {
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
}

// Legacy function for backward compatibility (uses mock data)
export function renderDashboard() {
  initDashboard();
}
