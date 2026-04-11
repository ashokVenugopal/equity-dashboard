/**
 * Cell formatting rules — mirrors backend/core/formatting.py.
 * Single source of truth for how values appear in the dashboard.
 */

const MONEY_DISPLAY = "Cr";

const MONEY_COLS = new Set([
  "value", "metric_value", "market_cap", "sales", "net_profit",
  "borrowings", "buy_value", "sell_value", "net_value", "enterprise_value",
  "operating_profit", "total_assets", "total_liabilities",
]);

const PRICE_COLS = new Set([
  "open", "high", "low", "close", "adj_close", "current_price", "last_price", "eps",
]);

const PCT_COLS = new Set([
  "npm", "opm", "roe", "roce", "change_pct", "daily_change_pct",
  "dividend_yield", "avg_return_pct", "median_return_pct", "oi_change_pct",
  "long_pct", "short_pct",
]);

const RATIO_COLS = new Set([
  "debt_to_equity", "price_to_earning", "price_to_book", "ev_ebitda",
  "current_ratio", "quick_ratio", "interest_coverage", "rsi_14",
  "volume_ratio", "pcr", "advance_decline_ratio",
]);

const VOLUME_COLS = new Set([
  "volume", "delivery_qty", "volume_avg_20d",
  "long_contracts", "short_contracts", "open_interest",
  "advances", "declines", "unchanged", "new_52w_highs", "new_52w_lows",
]);

export function formatCell(col: string, val: unknown): string {
  if (val === null || val === undefined) return "—";
  if (typeof val !== "number") return String(val);

  if (MONEY_COLS.has(col)) return `${val.toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 })} ${MONEY_DISPLAY}`;
  if (PRICE_COLS.has(col)) return val.toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 2 });
  if (PCT_COLS.has(col)) return `${val.toFixed(2)}%`;
  if (RATIO_COLS.has(col)) return val.toFixed(4);
  if (VOLUME_COLS.has(col)) return Math.round(val).toLocaleString("en-IN");

  return val.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

export function formatChange(val: number | null): { text: string; className: string } {
  if (val === null || val === undefined) return { text: "—", className: "text-muted" };
  const sign = val >= 0 ? "+" : "";
  return {
    text: `${sign}${val.toFixed(2)}`,
    className: val >= 0 ? "text-positive" : "text-negative",
  };
}

export function formatChangePct(val: number | null): { text: string; className: string } {
  if (val === null || val === undefined) return { text: "—", className: "text-muted" };
  const sign = val >= 0 ? "+" : "";
  return {
    text: `${sign}${val.toFixed(2)}%`,
    className: val >= 0 ? "text-positive" : "text-negative",
  };
}
