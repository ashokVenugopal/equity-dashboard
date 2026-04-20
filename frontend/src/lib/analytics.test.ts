import { describe, it, expect } from "vitest";
import {
  computeFIIStreak,
  computeRelativeStrength,
  computeLevelDistance,
  matchGlobalCues,
  computeCandleScale,
} from "./analytics";

// ═══════════════════════════════════════════════════════════════════════
// computeFIIStreak
// ═══════════════════════════════════════════════════════════════════════

describe("computeFIIStreak", () => {
  it("returns null for empty flows", () => {
    expect(computeFIIStreak([])).toBeNull();
  });

  it("returns null when the most recent flow has null fii_net", () => {
    expect(computeFIIStreak([{ fii_net: null }, { fii_net: 100 }])).toBeNull();
  });

  it("counts a single-day buy streak", () => {
    expect(computeFIIStreak([{ fii_net: 500 }])).toEqual({ count: 1, direction: "buy" });
  });

  it("counts a single-day sell streak", () => {
    expect(computeFIIStreak([{ fii_net: -1000 }])).toEqual({ count: 1, direction: "sell" });
  });

  it("counts consecutive buying days", () => {
    const flows = [{ fii_net: 100 }, { fii_net: 200 }, { fii_net: 50 }];
    expect(computeFIIStreak(flows)).toEqual({ count: 3, direction: "buy" });
  });

  it("counts consecutive selling days (matches CNBC context: 4-day selling streak)", () => {
    const flows = [{ fii_net: -1983 }, { fii_net: -500 }, { fii_net: -1200 }, { fii_net: -800 }, { fii_net: 300 }];
    expect(computeFIIStreak(flows)).toEqual({ count: 4, direction: "sell" });
  });

  it("stops at first direction change", () => {
    const flows = [{ fii_net: 100 }, { fii_net: 200 }, { fii_net: -300 }, { fii_net: 400 }];
    expect(computeFIIStreak(flows)).toEqual({ count: 2, direction: "buy" });
  });

  it("treats net === 0 as buy (non-negative)", () => {
    const flows = [{ fii_net: 0 }, { fii_net: 100 }, { fii_net: -50 }];
    expect(computeFIIStreak(flows)).toEqual({ count: 2, direction: "buy" });
  });

  it("breaks streak at intermediate null fii_net", () => {
    const flows = [{ fii_net: 100 }, { fii_net: 200 }, { fii_net: null }, { fii_net: 300 }];
    expect(computeFIIStreak(flows)).toEqual({ count: 2, direction: "buy" });
  });

  it("treats undefined fii_net like null", () => {
    const flows = [{ fii_net: -100 }, { fii_net: undefined }];
    expect(computeFIIStreak(flows)).toEqual({ count: 1, direction: "sell" });
  });

  it("all-same-direction flows produce streak == length", () => {
    const flows = Array.from({ length: 10 }, () => ({ fii_net: -50 }));
    expect(computeFIIStreak(flows)).toEqual({ count: 10, direction: "sell" });
  });
});

// ═══════════════════════════════════════════════════════════════════════
// computeRelativeStrength
// ═══════════════════════════════════════════════════════════════════════

describe("computeRelativeStrength", () => {
  it("returns simple difference when both inputs present", () => {
    expect(computeRelativeStrength(5.2, 2.0)).toBeCloseTo(3.2, 10);
  });

  it("returns negative when sector underperforms benchmark", () => {
    expect(computeRelativeStrength(-1.5, 3.0)).toBeCloseTo(-4.5, 10);
  });

  it("returns 0 when sector matches benchmark exactly", () => {
    expect(computeRelativeStrength(4.2, 4.2)).toBe(0);
  });

  it("returns null when sector is null", () => {
    expect(computeRelativeStrength(null, 2.0)).toBeNull();
  });

  it("returns null when benchmark is null", () => {
    expect(computeRelativeStrength(5.0, null)).toBeNull();
  });

  it("returns null when both are null", () => {
    expect(computeRelativeStrength(null, null)).toBeNull();
  });

  it("treats undefined like null", () => {
    expect(computeRelativeStrength(undefined, 2.0)).toBeNull();
    expect(computeRelativeStrength(2.0, undefined)).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════
// computeLevelDistance
// ═══════════════════════════════════════════════════════════════════════

describe("computeLevelDistance", () => {
  it("returns positive distance and above=true when close > level", () => {
    expect(computeLevelDistance(110, 100)).toEqual({ distance: 10, above: true });
  });

  it("returns negative distance and above=false when close < level", () => {
    expect(computeLevelDistance(95, 100)).toEqual({ distance: -5, above: false });
  });

  it("returns 0 distance and above=false when close equals level", () => {
    // above is strictly close > level, so equality means above=false
    expect(computeLevelDistance(100, 100)).toEqual({ distance: 0, above: false });
  });

  it("returns null when close is null", () => {
    expect(computeLevelDistance(null, 100)).toBeNull();
  });

  it("returns null when level is null", () => {
    expect(computeLevelDistance(100, null)).toBeNull();
  });

  it("returns null when level is zero (avoids divide-by-zero)", () => {
    expect(computeLevelDistance(100, 0)).toBeNull();
  });

  it("handles small negative distance for 52W high context", () => {
    // Nifty at 26300, 52W high 26400 → about -0.38%
    const d = computeLevelDistance(26300, 26400);
    expect(d).not.toBeNull();
    expect(d!.distance).toBeCloseTo(-0.3787, 3);
    expect(d!.above).toBe(false);
  });

  it("handles large positive distance for 52W low context", () => {
    // Nifty at 26300, 52W low 21000 → about +25.24%
    const d = computeLevelDistance(26300, 21000);
    expect(d).not.toBeNull();
    expect(d!.distance).toBeCloseTo(25.238, 2);
    expect(d!.above).toBe(true);
  });

  it("treats undefined like null", () => {
    expect(computeLevelDistance(undefined, 100)).toBeNull();
    expect(computeLevelDistance(100, undefined)).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════
// matchGlobalCues
// ═══════════════════════════════════════════════════════════════════════

describe("matchGlobalCues", () => {
  const sample = {
    index: [
      { name: "Dow Jones", symbol: "DJI", close: 42000, open: 41800 },
      { name: "Nasdaq", symbol: "IXIC", close: 18000, open: 17900 },
      { name: "S&P 500", symbol: "GSPC", close: 5700, open: 5680 },
    ],
    forex: [
      { name: "USD/INR", symbol: "USDINR", close: 83.5, open: 83.3 },
      { name: "Dollar Index", symbol: "DXY", close: 106.2, open: 106.0 },
    ],
    commodity: [
      { name: "Brent Crude", symbol: "BRENTUSD", close: 72, open: 71 },
    ],
  };

  it("returns items in the order of keys × priority symbols", () => {
    const items = matchGlobalCues(sample, {
      index: ["DJI", "IXIC"],
      forex: ["DXY"],
    });
    expect(items.map((i) => i.name)).toEqual(["Dow Jones", "Nasdaq", "Dollar Index"]);
  });

  it("passes through close/open values", () => {
    const items = matchGlobalCues(sample, { index: ["DJI"] });
    expect(items[0]).toEqual({ name: "Dow Jones", close: 42000, open: 41800 });
  });

  it("supports substring matching (e.g. GIFTNIFTY matches 'GIFTNIFTY-FEB')", () => {
    const groups = {
      index: [{ name: "Gift Nifty", symbol: "GIFTNIFTY-FEB", close: 26350, open: 26300 }],
    };
    const items = matchGlobalCues(groups, { index: ["GIFTNIFTY"] });
    expect(items).toHaveLength(1);
    expect(items[0].name).toBe("Gift Nifty");
  });

  it("skips missing symbols without crashing", () => {
    // minItems:1 disables fallback so we observe only priority-path behavior
    const items = matchGlobalCues(sample, { index: ["MISSING", "DJI"] }, { minItems: 1 });
    expect(items.map((i) => i.name)).toEqual(["Dow Jones"]);
  });

  it("returns empty array when groups are empty and no fallback triggered", () => {
    const items = matchGlobalCues({}, { index: ["DJI"] });
    expect(items).toEqual([]);
  });

  it("triggers fallback when matches are below minItems (default 3)", () => {
    // Only 1 priority match found → fallback pulls in top-2 per group
    const items = matchGlobalCues(sample, { index: ["DJI"] });
    // 1 priority + 2 from index + 2 from forex + 1 from commodity, capped by dedupe & maxItems
    expect(items.length).toBeGreaterThanOrEqual(3);
    expect(items.map((i) => i.name)).toContain("Dow Jones");
  });

  it("does not trigger fallback when priority matches meet minItems", () => {
    const items = matchGlobalCues(sample, {
      index: ["DJI", "IXIC", "GSPC"],
    });
    expect(items.map((i) => i.name)).toEqual(["Dow Jones", "Nasdaq", "S&P 500"]);
  });

  it("dedupes by name across priority + fallback", () => {
    const items = matchGlobalCues(sample, { index: ["DJI"] });
    const names = items.map((i) => i.name);
    expect(new Set(names).size).toBe(names.length);
  });

  it("respects maxItems cap during fallback", () => {
    const items = matchGlobalCues(sample, { index: ["DJI"] }, { minItems: 100, maxItems: 4 });
    expect(items.length).toBeLessThanOrEqual(4);
  });

  it("handles missing group (undefined in record) gracefully", () => {
    // Requested forex group is absent from the record. With fallback disabled, returns [].
    const partial = { index: sample.index };
    const items = matchGlobalCues(partial, { forex: ["DXY"] }, { minItems: 0 });
    expect(items).toEqual([]);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// computeCandleScale
// ═══════════════════════════════════════════════════════════════════════

describe("computeCandleScale", () => {
  it("returns null when all values are null/undefined", () => {
    expect(computeCandleScale([null, undefined, null])).toBeNull();
  });

  it("returns null for empty array", () => {
    expect(computeCandleScale([])).toBeNull();
  });

  it("computes min/max/padded range for a typical set", () => {
    const s = computeCandleScale([100, 110, 120], 0.1);
    expect(s).not.toBeNull();
    expect(s!.minVal).toBe(100);
    expect(s!.maxVal).toBe(120);
    expect(s!.yMax).toBeCloseTo(122, 10); // 120 + 20 * 0.1
    expect(s!.yRange).toBeCloseTo(24, 10); // (120 - 100) + 2 * 2
  });

  it("uses default padding of 0.08 when unspecified", () => {
    const s = computeCandleScale([100, 200]);
    expect(s!.yMax).toBeCloseTo(208, 10); // 200 + 100 * 0.08
    expect(s!.yRange).toBeCloseTo(116, 10); // 100 + 2 * 8
  });

  it("filters null and undefined values", () => {
    const s = computeCandleScale([null, 100, undefined, 200]);
    expect(s).not.toBeNull();
    expect(s!.minVal).toBe(100);
    expect(s!.maxVal).toBe(200);
  });

  it("handles single value: min == max, yRange falls back to 1", () => {
    const s = computeCandleScale([100]);
    expect(s!.minVal).toBe(100);
    expect(s!.maxVal).toBe(100);
    // padding is 0, (max-min+2*padding) is 0 → falls back to 1
    expect(s!.yRange).toBe(1);
  });

  it("handles all-equal values without divide-by-zero", () => {
    const s = computeCandleScale([50, 50, 50, 50]);
    expect(s!.yRange).toBe(1);
    expect(s!.minVal).toBe(50);
    expect(s!.maxVal).toBe(50);
  });

  it("handles Nifty-scale values", () => {
    // Matches real Anuj/CNBC page: year range 21000..26400, with DMA/current interspersed
    const s = computeCandleScale([26300, 26400, 21000, 25000, 24500, 26350, null]);
    expect(s!.minVal).toBe(21000);
    expect(s!.maxVal).toBe(26400);
    expect(s!.yMax).toBeCloseTo(26832, 0); // 26400 + 5400 * 0.08
    expect(s!.yRange).toBeCloseTo(6264, 0); // 5400 + 2 * 432
  });

  it("supports custom padding fraction (0 = tight)", () => {
    const s = computeCandleScale([100, 200], 0);
    expect(s!.yMax).toBe(200);
    expect(s!.yRange).toBe(100);
  });
});
