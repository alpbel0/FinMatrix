/** @module watchlist
 *  Watchlist page functionality - displays user's tracked stocks with price snapshot.
 */
import { apiFetch } from "./api.js";

/**
 * Fetch user's watchlist from API.
 * @returns {Promise<{items: Array, total: number}>}
 */
export async function fetchWatchlist() {
  return apiFetch("/api/watchlist");
}

/**
 * Add a stock to watchlist.
 * @param {string} symbol - Stock symbol (e.g., "THYAO")
 * @param {boolean} [notificationsEnabled=true] - Whether to enable notifications
 * @returns {Promise<Object>}
 */
export async function addToWatchlist(symbol, notificationsEnabled = true) {
  return apiFetch("/api/watchlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, notifications_enabled: notificationsEnabled }),
  });
}

/**
 * Remove a stock from watchlist.
 * @param {number} id - Watchlist item ID
 * @returns {Promise<void>}
 */
export async function removeFromWatchlist(id) {
  return apiFetch(`/api/watchlist/${id}`, { method: "DELETE" });
}

/**
 * Toggle notifications for a watchlist item.
 * @param {number} id - Watchlist item ID
 * @param {boolean} enabled - New notifications state
 * @returns {Promise<Object>}
 */
export async function toggleNotifications(id, enabled) {
  return apiFetch(`/api/watchlist/${id}/notifications`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ notifications_enabled: enabled }),
  });
}

/**
 * Format price change percentage for display.
 * @param {number|null} change - Absolute price change
 * @param {number|null} changePercent - Percentage change
 * @returns {string}
 */
export function formatPriceChange(change, changePercent) {
  if (change === null || changePercent === null) return "N/A";
  const sign = change >= 0 ? "+" : "";
  return `${sign}${changePercent.toFixed(2)}%`;
}

/**
 * Render watchlist cards to the DOM.
 * @param {Array} items - Watchlist items from API
 */
export function renderWatchlist(items) {
  const root = document.querySelector("#watchlist-root");
  if (!root) return;

  if (!items || items.length === 0) {
    root.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">⭐</div>
        <p class="text-muted">No stocks in watchlist. Add your first stock!</p>
      </div>
    `;
    return;
  }

  const changeClass = (change) => change >= 0 ? "text-success" : "text-danger";

  root.innerHTML = items.map((item) => `
    <div class="card watchlist-item" data-watchlist-id="${item.id}">
      <div class="flex-between mb-4">
        <div>
          <div class="stock-symbol">${item.symbol}</div>
          <div class="stock-name">${item.company_name || ""}</div>
        </div>
        <button class="switch ${item.notifications_enabled ? "active" : ""}" data-enabled="${item.notifications_enabled}" title="${item.notifications_enabled ? "Notifications On" : "Notifications Off"}"></button>
      </div>
      <div class="stock-price">${item.latest_price ? `₺${item.latest_price.toFixed(2)}` : "N/A"}</div>
      <div class="stock-change ${changeClass(item.price_change)}">${formatPriceChange(item.price_change, item.price_change_percent)}</div>
      <div class="divider"></div>
      <button class="btn btn-danger" type="button" style="width: 100%;">Remove</button>
    </div>
  `).join("");

  // Bind event handlers
  root.querySelectorAll(".switch").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const card = e.target.closest(".watchlist-item");
      const id = parseInt(card.dataset.watchlistId, 10);
      const currentEnabled = e.target.dataset.enabled === "true";
      const newEnabled = !currentEnabled;

      try {
        await toggleNotifications(id, newEnabled);
        setFeedback("Notification preference updated.");
        await refreshWatchlist();
      } catch (err) {
        if (err.message.toLowerCase().includes("not found")) {
          setFeedback("Watchlist item was already removed. Refreshing list.");
          await refreshWatchlist();
          return;
        }
        setFeedback(`Error: ${err.message}`, true);
      }
    });
  });

  root.querySelectorAll(".btn-danger").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const card = e.target.closest(".watchlist-item");
      const id = parseInt(card.dataset.watchlistId, 10);

      if (!confirm("Remove this stock from watchlist?")) return;

      try {
        await removeFromWatchlist(id);
        setFeedback("Stock removed from watchlist.");
        await refreshWatchlist();
      } catch (err) {
        if (err.message.toLowerCase().includes("not found")) {
          setFeedback("Watchlist item was already removed. Refreshing list.");
          await refreshWatchlist();
          return;
        }
        setFeedback(`Error: ${err.message}`, true);
      }
    });
  });
}

function setFeedback(message, isError = false) {
  const feedback = document.querySelector("#watchlist-feedback");
  if (!feedback) return;
  feedback.textContent = message;
  feedback.className = isError ? "error" : "muted";
}

function bindAddForm() {
  const form = document.querySelector("#watchlist-form");
  const symbolInput = document.querySelector("#watchlist-symbol");
  if (!form || !symbolInput) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const symbol = symbolInput.value.trim().toUpperCase();
    if (!symbol) {
      setFeedback("Enter a stock symbol.", true);
      return;
    }

    try {
      await addToWatchlist(symbol);
      symbolInput.value = "";
      setFeedback(`${symbol} added to watchlist.`);
      await refreshWatchlist();
    } catch (err) {
      setFeedback(`Error: ${err.message}`, true);
    }
  });
}

async function refreshWatchlist() {
  const data = await fetchWatchlist();
  renderWatchlist(data.items);
}

/**
 * Initialize watchlist page - fetch data and render.
 */
export async function initWatchlist() {
  bindAddForm();
  try {
    await refreshWatchlist();
  } catch (err) {
    const root = document.querySelector("#watchlist-root");
    if (root) {
      root.innerHTML = `<p class="error">Error loading watchlist: ${err.message}</p>`;
    }
    setFeedback(`Error: ${err.message}`, true);
  }
}
