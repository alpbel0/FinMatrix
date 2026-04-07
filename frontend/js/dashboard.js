document.addEventListener("DOMContentLoaded", () => {
  window.FinMatrixAuth?.requireAuth();
  const root = document.querySelector("#dashboard-root");
  if (!root) return;
  const data = window.FinMatrixAPI.mockData.dashboard;
  root.innerHTML = `
    <div class="card">
      <span class="badge">${data.symbol}</span>
      <h2>${data.companyName}</h2>
      <p class="muted">Mock dashboard shell for Week 1.</p>
    </div>
    <div class="grid three">
      ${data.metrics.map((metric) => `<div class="card"><p class="muted">${metric.label}</p><div class="metric">${metric.value}</div></div>`).join("")}
    </div>
    <div class="grid two">
      <div class="card"><h3>Price Chart</h3><div class="loading-state">Chart area placeholder</div></div>
      <div class="card"><h3>Related KAP Filings</h3>${data.filings.map((f) => `<p><strong>${f.title}</strong><br><span class="muted">${f.date}</span></p>`).join("")}</div>
    </div>
  `;
});
