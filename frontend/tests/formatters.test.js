import { describe, expect, it } from "vitest";

import { formatLargeNumber, formatPercent, formatRatio } from "../js/utils/formatters.js";
import { getMetricSourceLabel, getMetricToneClass } from "../js/utils/metricPresentation.js";


describe("formatters", () => {
  it("formats large TL values with compact suffixes", () => {
    expect(formatLargeNumber(1_250_500_000)).toBe("\u20BA1.3B");
    expect(formatLargeNumber(2_500_000)).toBe("\u20BA2.5M");
  });

  it("formats ratio and percent values", () => {
    expect(formatRatio(5.678)).toBe("5.68");
    expect(formatPercent(0.245)).toBe("24.5%");
  });

  it("returns N/A for missing values", () => {
    expect(formatRatio(null)).toBe("N/A");
    expect(formatPercent(undefined)).toBe("N/A");
    expect(formatLargeNumber(Number.NaN)).toBe("N/A");
  });
});


describe("metric presentation helpers", () => {
  it("maps positive and negative values to tone classes", () => {
    expect(getMetricToneClass(10)).toBe("text-success");
    expect(getMetricToneClass(-3)).toBe("text-danger");
    expect(getMetricToneClass(0)).toBe("");
  });

  it("renders source labels for provider, calculated and fallback values", () => {
    expect(getMetricSourceLabel("calculated")).toBe("Calculated");
    expect(getMetricSourceLabel("provider:borsapy")).toBe("Provider: borsapy");
    expect(getMetricSourceLabel("historical_fallback:2026-04-20")).toBe("Fallback: 2026-04-20");
  });
});
