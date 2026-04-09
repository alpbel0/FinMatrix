/** @module news
 *  News feed page functionality - displays KAP-based news feed with category filters.
 */
import { apiFetch } from "./api.js";

/**
 * Fetch news feed from API.
 * @param {string} [category="all"] - Filter by category: "all", "financial", "activity", "kap"
 * @param {number|null} [stockId=null] - Filter by stock ID
 * @param {number} [limit=50] - Max items to return
 * @param {number} [offset=0] - Pagination offset
 * @returns {Promise<{items: Array, total: number, unread_count: number}>}
 */
export async function fetchNews(category = "all", stockId = null, limit = 50, offset = 0) {
  const params = new URLSearchParams();
  if (category && category !== "all") params.set("category", category);
  if (stockId) params.set("stock_id", stockId);
  params.set("limit", limit);
  params.set("offset", offset);

  return apiFetch(`/api/news?${params.toString()}`);
}

/**
 * Fetch single news item detail.
 * @param {number} id - News item ID
 * @returns {Promise<Object>}
 */
export async function fetchNewsItem(id) {
  return apiFetch(`/api/news/${id}`);
}

/**
 * Mark news item as read/unread.
 * @param {number} id - News item ID
 * @param {boolean} [isRead=true] - Read status
 * @returns {Promise<Object>}
 */
export async function markNewsRead(id, isRead = true) {
  return apiFetch(`/api/news/${id}/read`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_read: isRead }),
  });
}

/**
 * Get human-readable label for category.
 * @param {string} category - Category string
 * @returns {string}
 */
export function getCategoryLabel(category) {
  const labels = {
    financial: "Financial Reports",
    activity: "Activity Reports",
    kap: "KAP Disclosures",
  };
  return labels[category] || category;
}

/**
 * Get CSS class for category badge.
 * @param {string} category - Category string
 * @returns {string}
 */
export function getCategoryBadgeClass(category) {
  const classes = {
    financial: "badge-financial",
    activity: "badge-activity",
    kap: "badge-kap",
  };
  return classes[category] || "badge-default";
}

/**
 * Render news feed to the DOM.
 * @param {{items: Array, total: number, unread_count: number}} data - News feed data
 * @param {string} [activeCategory="all"] - Currently active category filter
 */
export function renderNewsFeed(data, activeCategory = "all") {
  const root = document.querySelector("#news-root");
  if (!root) return;

  if (!data || !data.items || data.items.length === 0) {
    root.innerHTML = `
      <div class="empty-state">
        <p class="muted">No news available.</p>
      </div>
    `;
    return;
  }

  // Render unread badge
  const unreadBadge =
    data.unread_count > 0
      ? `<span class="badge unread-badge">${data.unread_count} unread</span>`
      : "";

  // Render category filters
  const filterHtml = `
    <div class="news-filters">
      <button class="button secondary filter-btn ${activeCategory === "all" ? "active" : ""}" data-category="all">All</button>
      <button class="button secondary filter-btn ${activeCategory === "financial" ? "active" : ""}" data-category="financial">Financial</button>
      <button class="button secondary filter-btn ${activeCategory === "activity" ? "active" : ""}" data-category="activity">Activity</button>
      <button class="button secondary filter-btn ${activeCategory === "kap" ? "active" : ""}" data-category="kap">KAP</button>
      ${unreadBadge}
    </div>
  `;

  const itemsHtml = data.items
    .map((item) => {
      const dateStr = new Date(item.created_at).toLocaleDateString("tr-TR", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });

      return `
        <div class="card news-item ${item.is_read ? "read" : "unread"}" data-news-id="${item.id}">
          <div class="badge ${getCategoryBadgeClass(item.category)}">${getCategoryLabel(item.category)}</div>
          <h3>${item.title}</h3>
          <p class="muted">${item.symbol || "General"} | ${dateStr}</p>
          ${item.excerpt ? `<p>${item.excerpt.substring(0, 150)}${item.excerpt.length > 150 ? "..." : ""}</p>` : ""}
          <div class="news-actions">
            ${item.source_url ? `<a href="${item.source_url}" target="_blank" rel="noopener" class="link">View Source</a>` : ""}
            <button class="button secondary mark-read-btn" type="button">
              ${item.is_read ? "Mark Unread" : "Mark Read"}
            </button>
          </div>
        </div>
      `;
    })
    .join("");

  root.innerHTML = filterHtml + itemsHtml;

  // Bind filter handlers
  root.querySelectorAll(".filter-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const category = e.target.dataset.category;
      root.querySelectorAll(".filter-btn").forEach((b) => b.classList.remove("active"));
      e.target.classList.add("active");

      try {
        const newData = await fetchNews(category);
        renderNewsFeed(newData, category);
      } catch (err) {
        alert(`Error: ${err.message}`);
      }
    });
  });

  // Bind mark read handlers
  root.querySelectorAll(".mark-read-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const card = e.target.closest(".news-item");
      const id = parseInt(card.dataset.news_id, 10);
      const currentRead = card.classList.contains("read");

      try {
        await markNewsRead(id, !currentRead);
        card.classList.toggle("read");
        card.classList.toggle("unread");
        e.target.textContent = currentRead ? "Mark Read" : "Mark Unread";
      } catch (err) {
        alert(`Error: ${err.message}`);
      }
    });
  });
}

/**
 * Initialize news page - fetch data and render.
 */
export async function initNews() {
  try {
    const data = await fetchNews("all");
    renderNewsFeed(data, "all");
  } catch (err) {
    const root = document.querySelector("#news-root");
    if (root) {
      root.innerHTML = `<p class="error">Error loading news: ${err.message}</p>`;
    }
  }
}