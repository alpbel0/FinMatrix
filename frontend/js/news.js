/** @module news
 *  News feed page functionality - displays KAP-based news feed with category filters.
 */
import { apiFetch } from "./api.js";

/**
 * Fetch news feed from API.
 * @param {string} [category="all"] - Filter by category: "all", "financial_activity", "kap_disclosures"
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
    financial_activity: "Financial & Activity",
    kap_disclosures: "KAP Disclosures",
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
    financial_activity: "badge-financial",
    kap_disclosures: "badge-kap",
  };
  return classes[category] || "badge-default";
}

export function getDocumentHint(item) {
  if (item.filing_type === "DG") return "Text Only";
  if (item.filing_type === "FR" || item.filing_type === "FAR") return "Priority PDF";
  return "";
}

/**
 * Render news feed to the DOM.
 * @param {{items: Array, total: number, unread_count: number}} data - News feed data
 * @param {string} [activeCategory="all"] - Currently active category filter
 */
export function renderNewsFeed(data, activeCategory = "all") {
  const root = document.querySelector("#news-root");
  if (!root) return;

  const items = data && data.items ? data.items : [];
  const unreadCount = data && data.unread_count ? data.unread_count : 0;

  const unreadBadge = document.getElementById("unread-badge");
  if (unreadBadge) {
    if (unreadCount > 0) {
      unreadBadge.textContent = `${unreadCount} unread`;
      unreadBadge.style.display = "inline-flex";
    } else {
      unreadBadge.style.display = "none";
    }
  }

  const newsCount = document.getElementById("news-count");
  if (newsCount) {
    newsCount.textContent = items.length;
  }

  if (!data || !data.items || data.items.length === 0) {
    root.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📰</div>
        <p class="text-muted">No news available.</p>
      </div>
    `;
    return;
  }

  const itemsHtml = items
    .map((item) => {
      const dateStr = new Date(item.created_at).toLocaleDateString("tr-TR", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
      const documentHint = getDocumentHint(item);
      const categoryBadgeClass = item.category === "financial_activity" ? "success" : "accent";

      return `
        <div class="news-card ${item.is_read ? "" : "unread"}" data-news-id="${item.id}">
          <div class="news-date">${dateStr}</div>
          <div class="news-content">
            <div class="flex gap-2" style="align-items: center; flex-wrap: wrap; margin-bottom: var(--space-2);">
              <span class="badge badge-${categoryBadgeClass}">${getCategoryLabel(item.category)}</span>
              ${item.filing_type ? `<span class="badge badge-default">${item.filing_type}</span>` : ""}
              ${documentHint ? `<span class="badge badge-default">${documentHint}</span>` : ""}
            </div>
            <h3 class="news-title">${item.title}</h3>
            <p class="news-excerpt">${item.excerpt || ""}</p>
            <div class="flex-between mt-4" style="font-size: var(--font-size-xs);">
              <span class="text-muted">${item.symbol || "General"}</span>
              <div class="flex gap-2">
                ${item.source_url ? `<a href="${item.source_url}" target="_blank" rel="noopener" class="text-accent">View Source →</a>` : ""}
                <button class="btn btn-ghost mark-read-btn" type="button" style="padding: var(--space-1) var(--space-2);">
                  ${item.is_read ? "Mark Unread" : "Mark Read"}
                </button>
              </div>
            </div>
          </div>
        </div>
      `;
    })
    .join("");

  root.innerHTML = itemsHtml;

  // Bind filter handlers (on tabs in page header)
  document.querySelectorAll(".tabs .tab").forEach((btn) => {
    btn.onclick = async (e) => {
      const category = e.target.dataset.category;
      document.querySelectorAll(".tabs .tab").forEach((b) => b.classList.remove("active"));
      e.target.classList.add("active");

      try {
        const newData = await fetchNews(category);
        renderNewsFeed(newData, category);
      } catch (err) {
        alert(`Error: ${err.message}`);
      }
    };
  });

  // Bind mark read handlers
  root.querySelectorAll(".mark-read-btn").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      const card = e.target.closest(".news-card");
      const id = parseInt(card.dataset.newsId, 10);
      const isUnread = card.classList.contains("unread");

      try {
        await markNewsRead(id, isUnread);
        const refreshedData = await fetchNews(activeCategory);
        renderNewsFeed(refreshedData, activeCategory);
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
