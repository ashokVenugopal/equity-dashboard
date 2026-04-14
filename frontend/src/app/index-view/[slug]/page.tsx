"use client";

import { useState, useCallback, useEffect } from "react";
import { getIndexDetailOverview, getIndexDetailTable, getIndexDetailStats, getInstrumentPriceHistory } from "@/lib/api";
import type { IndexStats } from "@/lib/api";
import { DataTable } from "@/components/tables/DataTable";
import { ThisViewTable } from "@/components/index/ThisViewTable";
import { PriceChart } from "@/components/charts/PriceChart";
import { PerformanceCards } from "@/components/index/PerformanceCards";
import { TechnicalPanels } from "@/components/index/TechnicalPanels";
import { PageHeader } from "@/components/shared/PageHeader";
import { useCachedData } from "@/lib/cache";
import { useParams } from "next/navigation";
import { formatChange, formatChangePct } from "@/lib/formatters";

const VIEWS = [
  { key: "this_view", label: "This View" },
  { key: "technicals", label: "Technicals" },
  { key: "support_resistance", label: "S&R" },
  { key: "price_volume", label: "Price & Volume" },
  { key: "fundamentals", label: "Fundamentals" },
  { key: "shareholding", label: "Shareholding" },
  { key: "relative", label: "Relative Perf" },
] as const;

type ViewKey = typeof VIEWS[number]["key"];

const VIEW_COLUMNS: Record<ViewKey, { key: string; label: string; align?: "left" | "right" }[]> = {
  this_view: [], // Uses custom ThisViewTable component
  technicals: [
    { key: "symbol", label: "Symbol" },
    { key: "name", label: "Company" },
    { key: "close", label: "LTP", align: "right" },
    { key: "dma_50", label: "SMA 50", align: "right" },
    { key: "dma_200", label: "SMA 200", align: "right" },
    { key: "rsi_14", label: "RSI", align: "right" },
    { key: "high_52w", label: "52W High", align: "right" },
    { key: "low_52w", label: "52W Low", align: "right" },
    { key: "dist_from_high", label: "From High %", align: "right" },
    { key: "volume_ratio", label: "Vol Ratio", align: "right" },
  ],
  support_resistance: [
    { key: "symbol", label: "Symbol" },
    { key: "name", label: "Company" },
    { key: "close", label: "LTP", align: "right" },
    { key: "pivot", label: "Pivot", align: "right" },
    { key: "r1", label: "R1", align: "right" },
    { key: "r1_diff_pct", label: "R1 Diff %", align: "right" },
    { key: "r2", label: "R2", align: "right" },
    { key: "r3", label: "R3", align: "right" },
    { key: "s1", label: "S1", align: "right" },
    { key: "s1_diff_pct", label: "S1 Diff %", align: "right" },
    { key: "s2", label: "S2", align: "right" },
    { key: "s3", label: "S3", align: "right" },
  ],
  price_volume: [
    { key: "symbol", label: "Symbol" },
    { key: "name", label: "Company" },
    { key: "close", label: "LTP", align: "right" },
    { key: "volume", label: "Volume", align: "right" },
    { key: "day_high", label: "Day H", align: "right" },
    { key: "day_low", label: "Day L", align: "right" },
    { key: "week_high", label: "Week H", align: "right" },
    { key: "week_low", label: "Week L", align: "right" },
    { key: "month_high", label: "Month H", align: "right" },
    { key: "month_low", label: "Month L", align: "right" },
    { key: "year_high", label: "Year H", align: "right" },
    { key: "year_low", label: "Year L", align: "right" },
  ],
  fundamentals: [
    { key: "symbol", label: "Symbol" },
    { key: "name", label: "Company" },
    { key: "market_cap", label: "MCap (Cr)", align: "right" },
    { key: "pe", label: "PE", align: "right" },
    { key: "peg", label: "PEG", align: "right" },
    { key: "pb", label: "P/B", align: "right" },
    { key: "eps", label: "EPS", align: "right" },
    { key: "npm", label: "NPM %", align: "right" },
    { key: "roe", label: "ROE %", align: "right" },
  ],
  shareholding: [
    { key: "symbol", label: "Symbol" },
    { key: "name", label: "Company" },
    { key: "promoters", label: "Promoter %", align: "right" },
    { key: "fii", label: "FII %", align: "right" },
    { key: "dii", label: "DII %", align: "right" },
    { key: "public", label: "Public %", align: "right" },
  ],
  relative: [
    { key: "symbol", label: "Symbol" },
    { key: "name", label: "Company" },
    { key: "close", label: "LTP", align: "right" },
    { key: "return_1w", label: "1W %", align: "right" },
    { key: "return_1m", label: "1M %", align: "right" },
    { key: "return_3m", label: "3M %", align: "right" },
    { key: "return_6m", label: "6M %", align: "right" },
    { key: "return_1y", label: "1Y %", align: "right" },
  ],
};

export default function IndexViewPage() {
  const params = useParams();
  const slug = params.slug as string;
  const [view, setView] = useState<ViewKey>("this_view");

  // Overview data (cached)
  const overviewFetcher = useCallback(() => getIndexDetailOverview(slug), [slug]);
  const overview = useCachedData(`idx-${slug}-overview`, overviewFetcher, 5 * 60 * 1000);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const ov = overview.data as any;
  const price = ov?.price;
  const indexName: string = ov?.index_name || slug;
  const constituentCount: number = ov?.constituent_count || 0;
  const instrumentSymbol: string = ov?.instrument?.symbol || "";

  // Table data (cached per view)
  const tableFetcher = useCallback(() => getIndexDetailTable(slug, view), [slug, view]);
  const table = useCachedData(`idx-${slug}-table-${view}`, tableFetcher, 5 * 60 * 1000);

  // Price chart data
  const chartFetcher = useCallback(async () => {
    if (!instrumentSymbol) return { symbol: "", prices: [], count: 0 };
    return getInstrumentPriceHistory(instrumentSymbol, { limit: 180 });
  }, [instrumentSymbol]);
  const chart = useCachedData(`idx-${slug}-chart-${instrumentSymbol}`, chartFetcher, 10 * 60 * 1000);

  // Index stats (performance cards, technicals, S&R)
  const statsFetcher = useCallback(() => getIndexDetailStats(slug), [slug]);
  const stats = useCachedData(`idx-${slug}-stats`, statsFetcher, 5 * 60 * 1000);
  const statsData = stats.data as IndexStats | null;

  return (
    <div className="space-y-6">
      <PageHeader
        title={indexName}
        loadedAt={overview.loadedAt}
        loading={overview.loading || table.loading}
        onRefresh={() => { overview.refresh(); table.refresh(); }}
      />

      {/* Index price header */}
      {price && (
        <div className="border border-border rounded bg-surface p-4">
          <div className="flex items-baseline gap-4">
            <span className="text-2xl font-bold font-mono">
              {price.close?.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
            </span>
            <span className={`text-sm font-mono font-bold ${(price.change ?? 0) >= 0 ? "text-positive" : "text-negative"}`}>
              {formatChange(price.change).text}
              {" "}({formatChangePct(price.change_pct).text})
            </span>
            <span className="text-xs text-muted">{price.trade_date}</span>
            <span className="text-xs text-muted ml-auto">{constituentCount} stocks</span>
          </div>
          <div className="flex gap-6 mt-2 text-xs text-muted font-mono">
            <span>O: {price.open?.toLocaleString("en-IN")}</span>
            <span>H: {price.high?.toLocaleString("en-IN")}</span>
            <span>L: {price.low?.toLocaleString("en-IN")}</span>
          </div>
        </div>
      )}

      {/* Price chart */}
      {chart.data && chart.data.prices && chart.data.prices.length > 0 && (
        <PriceChart data={chart.data.prices} height={250} />
      )}

      {/* Performance cards with distribution bars */}
      {statsData?.performance && statsData.performance.length > 0 && (
        <PerformanceCards items={statsData.performance} />
      )}

      {/* Technical indicators + S&R panels */}
      {statsData && (
        <TechnicalPanels
          technicals={statsData.technicals}
          supportResistance={statsData.support_resistance}
          currentPrice={price?.close}
        />
      )}

      {/* View tabs */}
      <div className="flex gap-4 border-b border-border pb-2">
        {VIEWS.map((v) => (
          <button
            key={v.key}
            onClick={() => setView(v.key)}
            className={`text-xs font-bold uppercase tracking-wider transition-colors ${
              view === v.key
                ? "text-accent border-b-2 border-accent pb-0.5"
                : "text-muted hover:text-foreground"
            }`}
          >
            {v.label}
          </button>
        ))}
      </div>

      {/* Table */}
      {table.data ? (
        view === "this_view" ? (
          <ThisViewTable rows={table.data.rows as never} />
        ) : (
          <DataTable columns={VIEW_COLUMNS[view]} rows={table.data.rows} />
        )
      ) : table.loading ? (
        <div className="text-muted text-xs text-center py-8">Loading {view}...</div>
      ) : table.error ? (
        <div className="text-negative text-xs">{table.error}</div>
      ) : null}
    </div>
  );
}
