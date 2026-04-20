/**
 * Pure analytics helpers — level/streak/distance calculations shared across dashboard pages.
 * No React, no DOM. Deterministic. Null-safe at boundaries.
 */

// ── FII streak ──

export type StreakDirection = "buy" | "sell";

export interface Streak {
  count: number;
  direction: StreakDirection;
}

/**
 * Count consecutive days of same-direction FII flow starting from the most recent entry.
 * Flows must be ordered most-recent-first. A day with net === 0 counts as "buy" (non-negative).
 * Returns null when there are no flows.
 */
export function computeFIIStreak(
  flows: ReadonlyArray<{ fii_net: number | null | undefined }>,
): Streak | null {
  if (flows.length === 0) return null;
  const first = flows[0].fii_net;
  if (first == null) return null;
  const direction: StreakDirection = first >= 0 ? "buy" : "sell";
  let count = 0;
  for (const f of flows) {
    if (f.fii_net == null) break;
    const dir: StreakDirection = f.fii_net >= 0 ? "buy" : "sell";
    if (dir !== direction) break;
    count++;
  }
  return { count, direction };
}

// ── Relative strength ──

/**
 * Sector return minus benchmark return. Returns null if either input is null.
 */
export function computeRelativeStrength(
  sectorPct: number | null | undefined,
  benchmarkPct: number | null | undefined,
): number | null {
  if (sectorPct == null || benchmarkPct == null) return null;
  return sectorPct - benchmarkPct;
}

// ── DMA / reference-level distance ──

export interface LevelDistance {
  distance: number;
  above: boolean;
}

/**
 * Percent distance of `close` from a reference level. `above` is true when close > level.
 * Returns null when either input is null/zero (division would be undefined).
 */
export function computeLevelDistance(
  close: number | null | undefined,
  level: number | null | undefined,
): LevelDistance | null {
  if (close == null || level == null || level === 0) return null;
  const distance = ((close - level) / level) * 100;
  return { distance, above: close > level };
}

// ── Global cues matching ──

export interface GlobalCueInstrument {
  name: string;
  symbol: string;
  close: number | null;
  open: number | null;
}

export interface GlobalCueItem {
  name: string;
  close: number | null;
  open: number | null;
}

/**
 * Pick instruments matching a per-type priority symbol list.
 * Fallback: if fewer than `minItems` match, top up with the first few instruments per group,
 * stopping when `maxItems` is reached. Dedupes by name.
 */
export function matchGlobalCues(
  groups: Record<string, ReadonlyArray<GlobalCueInstrument>>,
  keySymbols: Record<string, ReadonlyArray<string>>,
  options: { minItems?: number; maxItems?: number } = {},
): GlobalCueItem[] {
  const minItems = options.minItems ?? 3;
  const maxItems = options.maxItems ?? 8;
  const items: GlobalCueItem[] = [];

  for (const [type, symbols] of Object.entries(keySymbols)) {
    const instruments = groups[type] || [];
    for (const sym of symbols) {
      const inst = instruments.find((i) => i.symbol === sym || i.symbol.includes(sym));
      if (inst && !items.find((x) => x.name === inst.name)) {
        items.push({ name: inst.name, close: inst.close, open: inst.open });
      }
    }
  }

  if (items.length < minItems) {
    for (const instruments of Object.values(groups)) {
      for (const inst of (instruments || []).slice(0, 2)) {
        if (!items.find((x) => x.name === inst.name)) {
          items.push({ name: inst.name, close: inst.close, open: inst.open });
        }
        if (items.length >= maxItems) return items;
      }
      if (items.length >= maxItems) return items;
    }
  }

  return items;
}

// ── Candle-chart scale ──

export interface CandleScale {
  minVal: number;
  maxVal: number;
  yMax: number;
  yRange: number;
}

/**
 * Compute min/max/padded range for SVG Y-axis scaling over a set of values.
 * Returns null when no non-null values exist (caller should render nothing).
 * `yRange` is guaranteed >= 1 to avoid division-by-zero when all values are equal.
 */
export function computeCandleScale(
  values: ReadonlyArray<number | null | undefined>,
  paddingFraction = 0.08,
): CandleScale | null {
  const valid = values.filter((v): v is number => v != null);
  if (valid.length === 0) return null;
  const minVal = Math.min(...valid);
  const maxVal = Math.max(...valid);
  const padding = (maxVal - minVal) * paddingFraction;
  const yMax = maxVal + padding;
  const yRange = maxVal - minVal + padding * 2 || 1;
  return { minVal, maxVal, yMax, yRange };
}
