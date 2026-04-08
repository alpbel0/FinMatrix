import { apiFetch } from "./api.js";

/**
 * Get list of stocks with optional search filter.
 * @param {string} search - Symbol substring filter
 * @returns {Promise<{stocks: Array, total: number}>}
 */
export async function getStocks(search = "") {
  const params = new URLSearchParams();
  if (search) params.set("search", search);
  const query = params.toString() ? `?${params.toString()}` : "";
  return apiFetch(`/api/stocks${query}`);
}

/**
 * Get detailed info for a single stock.
 * @param {string} symbol - Stock symbol (e.g., "THYAO")
 * @returns {Promise<{symbol: string, company_name: string|null, sector: string|null, exchange: string, is_active: boolean}>}
 */
export async function getStockDetail(symbol) {
  return apiFetch(`/api/stocks/${symbol.toUpperCase()}`);
}

/**
 * Get price history for a stock.
 * @param {string} symbol - Stock symbol
 * @param {string|null} startDate - ISO date string (YYYY-MM-DD)
 * @param {string|null} endDate - ISO date string (YYYY-MM-DD)
 * @returns {Promise<{symbol: string, prices: Array<{date: string, open: number|null, high: number|null, low: number|null, close: number|null, volume: number|null}>, count: number}>}
 */
export async function getPriceHistory(symbol, startDate = null, endDate = null) {
  const params = new URLSearchParams();
  if (startDate) params.set("start_date", startDate);
  if (endDate) params.set("end_date", endDate);
  const query = params.toString() ? `?${params.toString()}` : "";
  return apiFetch(`/api/stocks/${symbol.toUpperCase()}/prices${query}`);
}