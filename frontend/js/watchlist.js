document.addEventListener("DOMContentLoaded", () => {
  window.FinMatrixAuth?.requireAuth();
  const root = document.querySelector("#watchlist-root");
  if (!root) return;
  root.innerHTML = window.FinMatrixAPI.mockData.watchlist.map((item) => `
    <div class="card">
      <div class="badge">${item.symbol}</div>
      <h3>${item.price}</h3>
      <p class="muted">Daily change: ${item.change}</p>
      <button class="button secondary" type="button">Notifications</button>
    </div>
  `).join("");
});
