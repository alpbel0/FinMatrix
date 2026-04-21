export function formatRatio(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  return Number(value).toFixed(2);
}

export function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  const normalized = Math.abs(value) <= 1 ? value * 100 : value;
  return `${normalized.toFixed(1)}%`;
}

export function formatLargeNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "N/A";
  const numeric = Number(value);
  if (Math.abs(numeric) >= 1_000_000_000) return `\u20BA${(numeric / 1_000_000_000).toFixed(1)}B`;
  if (Math.abs(numeric) >= 1_000_000) return `\u20BA${(numeric / 1_000_000).toFixed(1)}M`;
  return `\u20BA${numeric.toFixed(0)}`;
}
