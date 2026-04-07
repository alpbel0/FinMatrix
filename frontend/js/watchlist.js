import { mockData } from "./api.js";

export function renderWatchlist() {
  const root = document.querySelector("#watchlist-root");
  if (!root) return;

  root.innerHTML = mockData.watchlist.map((item) => `
    <div class="card">
      <div class="badge">${item.symbol}</div>
      <h3>${item.price}</h3>
      <p class="muted">Daily change: ${item.change}</p>
      <button class="button secondary" type="button">Notifications</button>
    </div>
  `).join("");
}
