export function getMetricToneClass(value) {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return "";
  }
  return value > 0 ? "text-success" : "text-danger";
}

export function getMetricSourceLabel(source) {
  if (!source) return "";
  if (source === "calculated") return "Calculated";
  if (source.startsWith("provider:")) return `Provider: ${source.slice("provider:".length)}`;
  if (source.startsWith("historical_fallback:")) return `Fallback: ${source.slice("historical_fallback:".length)}`;
  return source;
}
