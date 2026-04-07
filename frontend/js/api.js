const API_BASE_URL = "http://localhost:8000";

const mockData = {
  dashboard: {
    symbol: "THYAO",
    companyName: "Turk Hava Yollari",
    metrics: [
      { label: "Market Cap", value: "₺431B" },
      { label: "P/E", value: "4.8" },
      { label: "Net Profit", value: "₺163B" },
      { label: "ROE", value: "28.4%" }
    ],
    prices: ["1D", "1W", "3M", "6M", "1Y", "5Y"],
    filings: [
      { title: "2025 Annual Report", date: "2026-03-12" },
      { title: "Investor Presentation", date: "2026-02-28" }
    ]
  },
  watchlist: [
    { symbol: "THYAO", price: "319.25", change: "+2.1%" },
    { symbol: "ASELS", price: "124.40", change: "+0.8%" },
    { symbol: "GARAN", price: "142.90", change: "-0.3%" }
  ],
  chat: [
    {
      role: "assistant",
      content: "THYAO ve ASELS icin temel karsilastirma alani burada gosterilecek.",
      sources: ["KAP Annual Report", "Market Data Snapshot"]
    }
  ]
};

function getToken() {
  return localStorage.getItem("finmatrix_token");
}

async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) throw new Error(`API error: ${response.status}`);
  return response.json();
}

window.FinMatrixAPI = { API_BASE_URL, mockData, apiFetch };
