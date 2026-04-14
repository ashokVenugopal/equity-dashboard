"use client";

import { useState, useCallback } from "react";
import { getFundFlowDetailed } from "@/lib/api";
import { PageHeader } from "@/components/shared/PageHeader";
import { FlowBarChart, type FlowBarData } from "@/components/charts/FlowBarChart";
import { useCachedData } from "@/lib/cache";

const TIMEFRAMES = [
  { key: "daily", label: "PAST MONTH" },
  { key: "monthly", label: "MONTHLY" },
  { key: "yearly", label: "YEARLY" },
] as const;

const VIEWS = [
  { key: "summary", label: "SUMMARY" },
  { key: "cash_provisional", label: "CASH PROVISIONAL" },
  { key: "fii_cash", label: "FII CASH" },
  { key: "fii_fo", label: "FII F&O" },
  { key: "mf_cash", label: "MF CASH" },
  { key: "mf_fo", label: "MF F&O" },
] as const;

type TimeframeKey = typeof TIMEFRAMES[number]["key"];
type ViewKey = typeof VIEWS[number]["key"];

// Column definitions per view
const VIEW_COLUMNS: Record<string, { key: string; label: string; isNet?: boolean }[]> = {
  cash_provisional: [
    { key: "flow_date", label: "DATE" },
    { key: "fii_cash_buy", label: "FII GROSS PURCHASE" },
    { key: "fii_cash_sell", label: "FII GROSS SALES" },
    { key: "fii_cash_net", label: "FII NET PURCHASE / SALES", isNet: true },
    { key: "dii_cash_buy", label: "DII GROSS PURCHASE" },
    { key: "dii_cash_sell", label: "DII GROSS SALES" },
    { key: "dii_cash_net", label: "DII NET PURCHASE / SALES", isNet: true },
  ],
  summary: [
    { key: "flow_date", label: "DATE" },
    { key: "fii_equity_net", label: "FII EQUITY", isNet: true },
    { key: "fii_debt_net", label: "FII DEBT", isNet: true },
    { key: "fii_derivatives_net", label: "FII DERIVATIVES", isNet: true },
    { key: "fii_total_net", label: "FII TOTAL", isNet: true },
    { key: "mf_equity_net", label: "MF EQUITY", isNet: true },
    { key: "mf_debt_net", label: "MF DEBT", isNet: true },
    { key: "mf_derivatives_net", label: "MF DERIVATIVES", isNet: true },
    { key: "mf_total_net", label: "MF TOTAL", isNet: true },
  ],
  fii_cash: [
    { key: "flow_date", label: "DATE" },
    { key: "fii_equity_buy", label: "FII EQUITY GROSS PURCHASE" },
    { key: "fii_equity_sell", label: "FII EQUITY GROSS SALES" },
    { key: "fii_equity_net", label: "FII EQUITY NET", isNet: true },
    { key: "fii_debt_net", label: "FII DEBT NET", isNet: true },
    { key: "fii_debt_sell", label: "FII DEBT GROSS SALES" },
    { key: "fii_debt_buy", label: "FII DEBT GROSS PURCHASE" },
  ],
  fii_fo: [
    { key: "flow_date", label: "DATE" },
    { key: "fii_index_futures_buy", label: "FII FUTURES GROSS PURCHASE" },
    { key: "fii_index_futures_sell", label: "FII FUTURES GROSS SALES" },
    { key: "fii_index_futures_net", label: "FII FUTURES NET", isNet: true },
    { key: "fii_index_options_net", label: "FII OPTIONS NET", isNet: true },
    { key: "fii_index_options_sell", label: "FII OPTIONS GROSS SALES" },
    { key: "fii_index_options_buy", label: "FII OPTIONS GROSS PURCHASE" },
  ],
  mf_cash: [
    { key: "flow_date", label: "DATE" },
    { key: "dii_equity_buy", label: "MF EQUITY GROSS PURCHASE" },
    { key: "dii_equity_sell", label: "MF EQUITY GROSS SALES" },
    { key: "dii_equity_net", label: "MF EQUITY NET", isNet: true },
    { key: "dii_debt_net", label: "MF DEBT NET", isNet: true },
    { key: "dii_debt_sell", label: "MF DEBT GROSS SALES" },
    { key: "dii_debt_buy", label: "MF DEBT GROSS PURCHASE" },
  ],
  mf_fo: [
    { key: "flow_date", label: "DATE" },
    { key: "dii_index_futures_buy", label: "MF FUTURES GROSS PURCHASE" },
    { key: "dii_index_futures_sell", label: "MF FUTURES GROSS SALES" },
    { key: "dii_index_futures_net", label: "MF FUTURES NET", isNet: true },
    { key: "dii_index_options_net", label: "MF OPTIONS NET", isNet: true },
    { key: "dii_index_options_sell", label: "MF OPTIONS GROSS SALES" },
    { key: "dii_index_options_buy", label: "MF OPTIONS GROSS PURCHASE" },
  ],
};

export default function FundFlowDetailPage() {
  const [timeframe, setTimeframe] = useState<TimeframeKey>("daily");
  const [view, setView] = useState<ViewKey>("cash_provisional");
  const [foSub, setFoSub] = useState<"index" | "stock">("index");

  const limit = timeframe === "daily" ? 60 : timeframe === "monthly" ? 36 : 20;
  const cacheKey = `fundflow-detail-${timeframe}-${view}-${foSub}`;

  const fetcher = useCallback(
    () => getFundFlowDetailed(timeframe, view, (view === "fii_fo" || view === "mf_fo") ? foSub : undefined, limit),
    [timeframe, view, foSub, limit],
  );
  const { data, loading, loadedAt, refresh } = useCachedData(cacheKey, fetcher, 5 * 60 * 1000);

  const columns = VIEW_COLUMNS[view] || VIEW_COLUMNS.cash_provisional;

  return (
    <div className="space-y-4">
      <PageHeader title="FII & DII Trading Activity" loadedAt={loadedAt} loading={loading} onRefresh={refresh} dataType="flow" />

      {/* Timeframe tabs */}
      <div className="flex justify-center gap-2">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf.key}
            onClick={() => setTimeframe(tf.key)}
            className={`text-xs px-4 py-1.5 rounded font-bold transition-colors ${
              timeframe === tf.key
                ? "bg-accent text-background"
                : "text-muted hover:text-foreground"
            }`}
          >
            {tf.label}
          </button>
        ))}
      </div>

      {/* View tabs */}
      <div className="flex justify-center gap-4 border-b border-border pb-2">
        {VIEWS.map((v) => (
          <button
            key={v.key}
            onClick={() => setView(v.key)}
            className={`text-[10px] font-bold uppercase tracking-wider transition-colors ${
              view === v.key
                ? "text-accent border-b-2 border-accent pb-0.5"
                : "text-muted hover:text-foreground"
            }`}
          >
            {v.label}
          </button>
        ))}
      </div>

      {/* F&O sub-tabs */}
      {(view === "fii_fo" || view === "mf_fo") && (
        <div className="flex justify-center gap-2">
          {(["index", "stock"] as const).map((sub) => (
            <button
              key={sub}
              onClick={() => setFoSub(sub)}
              className={`text-[10px] px-3 py-1 rounded font-bold transition-colors ${
                foSub === sub
                  ? "bg-accent text-background"
                  : "text-muted border border-border hover:text-foreground"
              }`}
            >
              {sub.toUpperCase()}
            </button>
          ))}
        </div>
      )}

      {/* FII / DII Bar Chart */}
      {data && data.rows.length > 0 && (
        <FlowBarChart
          data={detailToFlowBarData(data.rows, view)}
        />
      )}

      {/* Color-coded table */}
      {data ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse font-mono text-xs">
            <thead>
              <tr className="border-b border-border">
                {columns.map((col) => (
                  <th key={col.key} className="px-3 py-2 text-[10px] text-muted font-medium text-right first:text-left whitespace-nowrap uppercase">
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* Aggregation rows */}
              {data.aggregations.map((row, i) => (
                <tr key={`agg-${i}`} className="border-b-2 border-border font-bold bg-surface">
                  {columns.map((col) => {
                    const val = row[col.key];
                    return (
                      <td key={col.key} className={`px-3 py-2.5 text-right first:text-left whitespace-nowrap ${col.isNet ? netCellClass(val as number | null) : ""}`}>
                        {col.key === "flow_date" ? String(val) : formatVal(val as number | null)}
                      </td>
                    );
                  })}
                </tr>
              ))}
              {/* Data rows */}
              {data.rows.map((row, i) => (
                <tr key={i} className="border-b border-border/30 hover:bg-surface-hover transition-colors">
                  {columns.map((col) => {
                    const val = row[col.key];
                    return (
                      <td key={col.key} className={`px-3 py-1.5 text-right first:text-left whitespace-nowrap ${col.isNet ? netCellClass(val as number | null) : ""}`}>
                        {col.key === "flow_date" ? String(val) : formatVal(val as number | null)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : loading ? (
        <div className="text-muted text-xs text-center py-8">Loading...</div>
      ) : null}
    </div>
  );
}

// Map view → which columns represent FII net and DII/MF net for the bar chart
const VIEW_NET_KEYS: Record<string, { fii: string; dii: string }> = {
  cash_provisional: { fii: "fii_cash_net", dii: "dii_cash_net" },
  summary: { fii: "fii_equity_net", dii: "mf_equity_net" },
  fii_cash: { fii: "fii_equity_net", dii: "fii_debt_net" },
  fii_fo: { fii: "fii_index_futures_net", dii: "fii_index_options_net" },
  mf_cash: { fii: "dii_equity_net", dii: "dii_debt_net" },
  mf_fo: { fii: "dii_index_futures_net", dii: "dii_index_options_net" },
};

function detailToFlowBarData(rows: Record<string, unknown>[], view: string): FlowBarData[] {
  const keys = VIEW_NET_KEYS[view] || VIEW_NET_KEYS.cash_provisional;
  return [...rows].reverse().map((row) => ({
    time: String(row.flow_date),
    fii_net: (row[keys.fii] as number | null) ?? null,
    dii_net: (row[keys.dii] as number | null) ?? null,
  }));
}

function formatVal(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toLocaleString("en-IN", { maximumFractionDigits: 1 });
}

function netCellClass(v: number | null | undefined): string {
  if (v == null) return "";
  if (v > 5000) return "bg-positive/30 text-positive font-bold";
  if (v > 1000) return "bg-positive/20 text-positive";
  if (v > 0) return "bg-positive/10 text-positive";
  if (v > -1000) return "bg-negative/10 text-negative";
  if (v > -5000) return "bg-negative/20 text-negative";
  return "bg-negative/30 text-negative font-bold";
}
