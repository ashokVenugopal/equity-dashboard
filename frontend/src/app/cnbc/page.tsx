"use client";

import { useCallback, useState, useRef } from "react";
import {
  getFundFlowSummary,
  getFundFlowDaily,
  getDerivativesPCR,
  getDerivativesFIIPositioning,
  getDerivativesOIChanges,
  getGlobalOverview,
  getMarketBreadth,
  getSectorPerformance,
  getIndexDetailStats,
  getIndexDetailOverview,
  type IndexStats,
  type GlobalInstrument,
  type Breadth,
  type FIIPositioning,
  type PCRRow,
  type SectorPerformanceRow,
} from "@/lib/api";
import { PageHeader } from "@/components/shared/PageHeader";
import { FlowBarChart, type FlowBarData } from "@/components/charts/FlowBarChart";
import { useCachedData } from "@/lib/cache";

// ── Helpers ──

const fmt = (v: number | null | undefined, digits = 2) =>
  v != null ? v.toLocaleString("en-IN", { maximumFractionDigits: digits }) : "—";

const fmtCr = (v: number | null | undefined) =>
  v != null ? `${v >= 0 ? "+" : ""}${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr` : "—";

const cls = (v: number | null | undefined) =>
  v == null ? "text-muted" : v >= 0 ? "text-positive" : "text-negative";

const clsBold = (v: number | null | undefined) =>
  v == null ? "text-muted" : v >= 0 ? "text-positive font-bold" : "text-negative font-bold";

const fmtPct = (v: number | null | undefined) =>
  v != null ? `${v >= 0 ? "+" : ""}${v.toFixed(2)}%` : "—";

// ── Types ──

interface CNBCData {
  flowSummary: Record<string, unknown>;
  flowDaily: { flows: Record<string, unknown>[] };
  niftyStats: IndexStats;
  niftyOverview: Record<string, unknown>;
  bankNiftyStats: IndexStats;
  bankNiftyOverview: Record<string, unknown>;
  pcr: PCRRow[];
  fiiPos: FIIPositioning[];
  niftyOI: Record<string, unknown>[];
  bankNiftyOI: Record<string, unknown>[];
  globalGroups: Record<string, GlobalInstrument[]>;
  breadth: Breadth[];
  sectorPerf: SectorPerformanceRow[];
}

// ── Page ──

export default function CNBCPage() {
  const fetcher = useCallback(async () => {
    const [
      flowSummary, flowDaily,
      niftyStats, niftyOverview, bankNiftyStats, bankNiftyOverview,
      pcrData, posData,
      niftyOI, bankNiftyOI,
      globalData, breadthData, sectorData,
    ] = await Promise.all([
      getFundFlowSummary(),
      getFundFlowDaily("CASH", 30),
      getIndexDetailStats("nifty-50"),
      getIndexDetailOverview("nifty-50"),
      getIndexDetailStats("nifty-bank"),
      getIndexDetailOverview("nifty-bank"),
      getDerivativesPCR("NIFTY", 5),
      getDerivativesFIIPositioning(10),
      getDerivativesOIChanges("NIFTY"),
      getDerivativesOIChanges("BANKNIFTY"),
      getGlobalOverview(),
      getMarketBreadth(5),
      getSectorPerformance("sector"),
    ]);
    return {
      flowSummary,
      flowDaily,
      niftyStats,
      niftyOverview,
      bankNiftyStats,
      bankNiftyOverview,
      pcr: pcrData.pcr_data,
      fiiPos: posData.positioning,
      niftyOI: niftyOI.oi_data,
      bankNiftyOI: bankNiftyOI.oi_data,
      globalGroups: globalData.groups,
      breadth: breadthData.breadth,
      sectorPerf: sectorData.performance,
    } as CNBCData;
  }, []);

  const { data, loading, loadedAt, refresh, error } = useCachedData("cnbc-bazaar", fetcher, 5 * 60 * 1000);

  if (error && !data) {
    return <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">{error}. Ensure the backend is running.</div>;
  }
  if (!data) {
    return <div className="text-muted text-xs py-8 text-center">Loading Morning Bazaar...</div>;
  }

  return (
    <div className="space-y-4">
      <PageHeader title="CNBC Morning Bazaar" loadedAt={loadedAt} loading={loading} onRefresh={refresh} />

      <CashFlowsSection summary={data.flowSummary} daily={data.flowDaily} />

      <FIIPositioningSection positioning={data.fiiPos} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <PCRSection pcr={data.pcr} />
        <SeriesOISection niftyOI={data.niftyOI} bankNiftyOI={data.bankNiftyOI} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <IndexSnapshotCard label="NIFTY 50" overview={data.niftyOverview} stats={data.niftyStats} />
        <IndexSnapshotCard label="NIFTY BANK" overview={data.bankNiftyOverview} stats={data.bankNiftyStats} />
      </div>

      <GlobalCuesSection groups={data.globalGroups} />

      <SectorPerformanceSection performance={data.sectorPerf} />

      <BreadthSection breadth={data.breadth} />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// 1. CASH MARKET FLOWS
// ═══════════════════════════════════════════════════════════════════════

function CashFlowsSection({ summary, daily }: { summary: Record<string, unknown>; daily: { flows: Record<string, unknown>[] } }) {
  const latest = (summary.latest as Record<string, unknown>[]) || [];
  const mtd = (summary.mtd as Record<string, unknown>[]) || [];
  const ytd = (summary.ytd as Record<string, unknown>[]) || [];
  const fiiNet = (latest.find((r) => r.participant_type === "FII")?.net_value as number | null) ?? null;
  const diiNet = (latest.find((r) => r.participant_type === "DII")?.net_value as number | null) ?? null;
  const netInstl = fiiNet != null && diiNet != null ? fiiNet + diiNet : null;
  const fiiMtd = (mtd.find((r) => r.participant_type === "FII")?.net_value as number | null) ?? null;
  const diiMtd = (mtd.find((r) => r.participant_type === "DII")?.net_value as number | null) ?? null;
  const fiiYtd = (ytd.find((r) => r.participant_type === "FII")?.net_value as number | null) ?? null;
  const diiYtd = (ytd.find((r) => r.participant_type === "DII")?.net_value as number | null) ?? null;

  // Activity bars (like Trendlyne FII/DII Activity)
  const maxAbs = Math.max(Math.abs(fiiNet || 0), Math.abs(diiNet || 0), 1);

  const barData: FlowBarData[] = [...daily.flows].reverse().map((r) => ({
    time: String(r.flow_date),
    fii_net: r.fii_net as number | null,
    dii_net: r.dii_net as number | null,
  }));

  return (
    <section className="border border-border rounded bg-surface p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium">Cash Market Flows — FII / DII</h2>
        <span className="text-[10px] text-muted">{summary.latest_date as string || ""}</span>
      </div>

      {/* Activity bars */}
      <div className="space-y-2 mb-4">
        <ActivityBar label="FII" value={fiiNet} maxAbs={maxAbs} />
        <ActivityBar label="DII" value={diiNet} maxAbs={maxAbs} />
      </div>

      {/* Net Instl */}
      <div className="flex items-center gap-2 mb-4 text-xs font-mono">
        <span className="text-muted">Net Institutional:</span>
        <span className={`font-bold ${cls(netInstl)}`}>{fmtCr(netInstl)}</span>
      </div>

      {/* Period summaries with net */}
      <div className="grid grid-cols-3 gap-3 mb-4 text-xs font-mono">
        <PeriodFlowCard label="Latest" fii={fiiNet} dii={diiNet} />
        <PeriodFlowCard label="MTD" fii={fiiMtd} dii={diiMtd} />
        <PeriodFlowCard label="YTD" fii={fiiYtd} dii={diiYtd} />
      </div>

      {barData.length > 0 && <FlowBarChart data={barData} height={180} />}
    </section>
  );
}

function ActivityBar({ label, value, maxAbs }: { label: string; value: number | null; maxAbs: number }) {
  if (value == null) return null;
  const pct = Math.min(Math.abs(value) / maxAbs * 80, 80); // max 80% width
  const isPos = value >= 0;

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs font-mono text-muted w-8">{label}</span>
      <div className="flex-1 h-5 bg-border/30 rounded-full overflow-hidden relative">
        <div
          className={`h-full rounded-full transition-all ${isPos ? "bg-[#2196F3]" : "bg-negative"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs font-mono font-bold w-28 text-right ${isPos ? "text-positive" : "text-negative"}`}>
        {value >= 0 ? "+" : ""}{fmt(value, 2)} Cr
      </span>
    </div>
  );
}

function PeriodFlowCard({ label, fii, dii }: { label: string; fii: number | null; dii: number | null }) {
  const net = fii != null && dii != null ? fii + dii : null;
  return (
    <div className="border border-border/50 rounded p-2">
      <div className="text-[9px] text-muted uppercase mb-1">{label}</div>
      <div className="flex justify-between gap-2">
        <div>
          <div className="text-[8px] text-muted">FII</div>
          <div className={`text-xs font-bold ${cls(fii)}`}>{fmtCr(fii)}</div>
        </div>
        <div>
          <div className="text-[8px] text-muted">DII</div>
          <div className={`text-xs font-bold ${cls(dii)}`}>{fmtCr(dii)}</div>
        </div>
        <div>
          <div className="text-[8px] text-muted">Net</div>
          <div className={`text-xs font-bold ${cls(net)}`}>{fmtCr(net)}</div>
        </div>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════
// 2. FII DERIVATIVES POSITIONING
// ═══════════════════════════════════════════════════════════════════════

function FIIPositioningSection({ positioning }: { positioning: FIIPositioning[] }) {
  if (!positioning || positioning.length === 0) {
    return (
      <section className="border border-border rounded bg-surface p-4">
        <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium mb-2">FII Derivatives Positioning</h2>
        <p className="text-muted text-xs">No positioning data. Run: <code className="text-accent">python -m pipeline.cli download-fo-participant</code></p>
      </section>
    );
  }

  const fiiRows = positioning.filter((p) => p.participant_type === "FII");
  const dates = [...new Set(fiiRows.map((r) => r.trade_date))].sort().reverse();
  const latestDate = dates[0];
  const prevDate = dates[1];
  const latest = fiiRows.filter((r) => r.trade_date === latestDate);
  const prev = fiiRows.filter((r) => r.trade_date === prevDate);
  const futuresLatest = latest.find((r) => r.instrument_category === "INDEX_FUTURES");
  const futuresPrev = prev.find((r) => r.instrument_category === "INDEX_FUTURES");
  const optionsLatest = latest.find((r) => r.instrument_category === "INDEX_OPTIONS");

  return (
    <section className="border border-border rounded bg-surface p-4">
      <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium mb-3">FII Derivatives Positioning</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div>
          <div className="text-[10px] text-muted mb-2">INDEX FUTURES — FIIs ({latestDate})</div>
          {futuresLatest && (
            <>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-positive text-sm font-bold font-mono">Long {fmt(futuresLatest.long_pct, 1)}%</span>
                <span className="text-negative text-sm font-bold font-mono">Short {fmt(futuresLatest.short_pct, 1)}%</span>
              </div>
              <div className="flex h-3 rounded overflow-hidden mb-2">
                <div className="bg-positive" style={{ width: `${futuresLatest.long_pct ?? 50}%` }} />
                <div className="bg-negative" style={{ width: `${futuresLatest.short_pct ?? 50}%` }} />
              </div>
              {futuresPrev && (
                <div className="text-[10px] text-muted">
                  vs {prevDate}: Long {fmt(futuresPrev.long_pct, 1)}% / Short {fmt(futuresPrev.short_pct, 1)}%
                </div>
              )}
              {(futuresLatest.short_pct ?? 0) > 70 && (
                <div className="mt-2 text-[10px] text-negative font-bold">EXTREME SHORT POSITIONING</div>
              )}
            </>
          )}
        </div>
        <div>
          <div className="text-[10px] text-muted mb-2">INDEX OPTIONS — FIIs</div>
          {optionsLatest ? (
            <div className="grid grid-cols-2 gap-2 text-xs font-mono">
              <div><span className="text-[10px] text-muted block">Long</span><span>{fmt(optionsLatest.long_contracts, 0)}</span></div>
              <div><span className="text-[10px] text-muted block">Short</span><span>{fmt(optionsLatest.short_contracts, 0)}</span></div>
            </div>
          ) : <span className="text-muted text-xs">No options data</span>}
        </div>
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// 3. NIFTY OPTIONS CUES
// ═══════════════════════════════════════════════════════════════════════

function PCRSection({ pcr }: { pcr: PCRRow[] }) {
  if (!pcr || pcr.length === 0) {
    return (
      <section className="border border-border rounded bg-surface p-4">
        <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium mb-2">Nifty Options Cues</h2>
        <p className="text-muted text-xs">No PCR data. Run: <code className="text-accent">python -m pipeline.cli download-options-chain</code></p>
      </section>
    );
  }
  const latest = pcr[0];
  const prev = pcr[1];

  return (
    <section className="border border-border rounded bg-surface p-4">
      <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium mb-3">Nifty Options Cues</h2>
      <div className="flex items-baseline gap-2 mb-3">
        <span className="text-[10px] text-muted">PCR</span>
        <span className={`text-xl font-bold font-mono ${
          (latest.pcr ?? 0) > 1 ? "text-positive" : (latest.pcr ?? 0) < 0.7 ? "text-negative" : "text-foreground"
        }`}>{fmt(latest.pcr)}</span>
        {prev && <span className="text-muted text-xs font-mono">vs {fmt(prev.pcr)}</span>}
        {(latest.pcr ?? 0) > 1 && <span className="text-[9px] text-positive border border-positive/30 rounded px-1">BULLISH</span>}
        {(latest.pcr ?? 0) < 0.7 && <span className="text-[9px] text-negative border border-negative/30 rounded px-1">BEARISH</span>}
      </div>
      <table className="w-full text-xs font-mono">
        <thead><tr className="text-[10px] text-muted border-b border-border">
          <th className="text-left py-1">Expiry</th><th className="text-right py-1">Put OI</th>
          <th className="text-right py-1">Call OI</th><th className="text-right py-1">PCR</th>
        </tr></thead>
        <tbody>
          {pcr.slice(0, 3).map((r, i) => (
            <tr key={i} className="border-b border-border/30">
              <td className="py-1">{r.expiry_date}</td>
              <td className="text-right tabular-nums">{fmt(r.put_oi, 0)}</td>
              <td className="text-right tabular-nums">{fmt(r.call_oi, 0)}</td>
              <td className={`text-right tabular-nums font-bold ${(r.pcr ?? 0) > 1 ? "text-positive" : (r.pcr ?? 0) < 0.7 ? "text-negative" : ""}`}>{fmt(r.pcr)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// 4. SERIES OI
// ═══════════════════════════════════════════════════════════════════════

function SeriesOISection({ niftyOI, bankNiftyOI }: { niftyOI: Record<string, unknown>[]; bankNiftyOI: Record<string, unknown>[] }) {
  const hasData = (niftyOI && niftyOI.length > 0) || (bankNiftyOI && bankNiftyOI.length > 0);
  return (
    <section className="border border-border rounded bg-surface p-4">
      <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium mb-3">Open Interest — Current Series</h2>
      {hasData ? (
        <div className="space-y-3">
          <OICard label="NIFTY" data={niftyOI} />
          <OICard label="BANK NIFTY" data={bankNiftyOI} />
        </div>
      ) : (
        <p className="text-muted text-xs">No OI data. Run: <code className="text-accent">python -m pipeline.cli download-options-chain</code></p>
      )}
    </section>
  );
}

function OICard({ label, data }: { label: string; data: Record<string, unknown>[] }) {
  const latest = data?.[0];
  if (!latest) return <div className="text-muted text-xs">{label}: No data</div>;
  return (
    <div>
      <div className="text-xs font-bold text-foreground mb-1">{label}</div>
      <div className="grid grid-cols-3 gap-2 text-xs font-mono">
        <div><span className="text-[9px] text-muted block">Futures OI</span>{fmt(latest.futures_oi as number, 0)}</div>
        <div><span className="text-[9px] text-muted block">Options OI</span>{fmt(latest.options_oi as number, 0)}</div>
        <div><span className="text-[9px] text-muted block">Volume</span>{fmt(latest.total_volume as number, 0)}</div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// 5. INDEX SNAPSHOT (with OHLC ranges)
// ═══════════════════════════════════════════════════════════════════════

function IndexSnapshotCard({ label, overview, stats }: {
  label: string; overview: Record<string, unknown>; stats: IndexStats;
}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const price = overview.price as any;
  const tech = stats.technicals;
  const sr = stats.support_resistance;
  const ranges = stats.price_ranges || {};

  return (
    <section className="border border-border rounded bg-surface p-4">
      <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium mb-2">{label}</h2>

      {price ? (
        <>
          <div className="flex items-baseline gap-3 mb-3">
            <span className="text-xl font-bold font-mono">{fmt(price.close)}</span>
            <span className={`text-sm font-mono ${clsBold(price.change)}`}>
              {fmtPct(price.change_pct)}
            </span>
            <span className="text-[10px] text-muted">{price.trade_date}</span>
          </div>

          {/* Previous day OHLC */}
          <div className="grid grid-cols-4 gap-2 text-[10px] font-mono mb-3">
            <div><span className="text-muted block">Open</span>{fmt(price.open)}</div>
            <div><span className="text-muted block">High</span>{fmt(price.high)}</div>
            <div><span className="text-muted block">Low</span>{fmt(price.low)}</div>
            <div><span className="text-muted block">Close</span>{fmt(price.close)}</div>
          </div>

          {/* Period Range Candlesticks + SMA lines */}
          <PeriodCandleChart
            ranges={[
              { label: "Day", high: price.high, low: price.low, open: price.open, close: price.close },
              { label: "1W", high: ranges.week_high, low: ranges.week_low, open: ranges.week_open, close: price.close },
              { label: "1M", high: ranges.month_high, low: ranges.month_low, open: ranges.month_open, close: price.close },
              { label: "MTD", high: ranges.this_month_high, low: ranges.this_month_low, open: ranges.this_month_open, close: price.close },
              { label: "1Y", high: ranges.year_high, low: ranges.year_low, open: ranges.year_open, close: price.close },
              { label: "YTD", high: ranges.ytd_high, low: ranges.ytd_low, open: ranges.ytd_open, close: price.close },
            ]}
            currentPrice={price.close}
            smaLines={[
              { label: "SMA 50", value: tech.dma_50, color: "#FFD700" },
              { label: "SMA 200", value: tech.dma_200, color: "#FF6B6B" },
            ]}
          />

          {/* RSI */}
          <div className="flex items-center gap-4 text-[10px] font-mono mb-3">
            <span className="text-muted">RSI (14):</span>
            <span className={`font-bold ${
              (tech.rsi_14 ?? 50) > 70 ? "text-negative" : (tech.rsi_14 ?? 50) < 30 ? "text-positive" : "text-foreground"
            }`}>
              {tech.rsi_14 != null ? fmt(tech.rsi_14) : "—"}
              {tech.rsi_14 != null && (
                <span className="text-[9px] text-muted ml-1">
                  {tech.rsi_14 > 70 ? "(Overbought)" : tech.rsi_14 < 30 ? "(Oversold)" : "(Neutral)"}
                </span>
              )}
            </span>
          </div>

          {/* S&R levels */}
          {sr.pivot != null && (
            <div className="grid grid-cols-7 gap-1 text-[9px] font-mono text-center">
              {[
                { l: "S3", v: sr.s3, c: "text-negative" },
                { l: "S2", v: sr.s2, c: "text-negative" },
                { l: "S1", v: sr.s1, c: "text-negative" },
                { l: "Pivot", v: sr.pivot, c: "text-accent" },
                { l: "R1", v: sr.r1, c: "text-positive" },
                { l: "R2", v: sr.r2, c: "text-positive" },
                { l: "R3", v: sr.r3, c: "text-positive" },
              ].map(({ l, v, c }) => (
                <div key={l}><div className={`${c} font-medium`}>{l}</div><div>{v != null ? fmt(v, 0) : "—"}</div></div>
              ))}
            </div>
          )}
        </>
      ) : (
        <span className="text-muted text-xs">No price data available</span>
      )}
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// 6. GLOBAL MARKET CUES (with % change)
// ═══════════════════════════════════════════════════════════════════════

function GlobalCuesSection({ groups }: { groups: Record<string, GlobalInstrument[]> }) {
  const order = [
    { key: "index", label: "WALL STREET / GLOBAL INDICES" },
    { key: "commodity", label: "COMMODITIES" },
    { key: "forex", label: "CURRENCY" },
    { key: "bond", label: "BOND YIELDS" },
  ];

  return (
    <section className="border border-border rounded bg-surface p-4">
      <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium mb-3">Global Market Cues</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {order.map(({ key, label }) => {
          const instruments = groups[key];
          if (!instruments || instruments.length === 0) return null;
          return (
            <div key={key}>
              <div className="text-[9px] text-muted uppercase tracking-wider mb-1.5 font-medium">{label}</div>
              <table className="w-full text-xs font-mono">
                <tbody>
                  {instruments.map((inst) => {
                    // Compute change% from open if available
                    const changePct = inst.open && inst.close && inst.open !== 0
                      ? ((inst.close - inst.open) / inst.open * 100)
                      : null;
                    return (
                      <tr key={inst.symbol} className="border-b border-border/20">
                        <td className="py-1 text-muted pr-2 max-w-[140px] truncate" title={inst.name}>{inst.name}</td>
                        <td className="py-1 text-right tabular-nums">{fmt(inst.close)}</td>
                        <td className={`py-1 text-right tabular-nums w-16 ${cls(changePct)}`}>
                          {changePct != null ? fmtPct(changePct) : ""}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// 7. SECTOR PERFORMANCE
// ═══════════════════════════════════════════════════════════════════════

function SectorPerformanceSection({ performance }: { performance: SectorPerformanceRow[] }) {
  if (!performance || performance.length === 0) return null;
  const timeframes = ["1w", "4w", "13w", "26w", "52w"].filter(
    (tf) => performance.some((r) => r[tf] != null)
  );

  return (
    <section className="border border-border rounded bg-surface p-4">
      <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium mb-3">Mapping the Moves — Sector Performance</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead><tr className="text-[10px] text-muted border-b border-border">
            <th className="text-left py-1">Sector</th>
            {timeframes.map((tf) => <th key={tf} className="text-right py-1">{tf.replace("w", "W")}</th>)}
          </tr></thead>
          <tbody>
            {performance.map((row) => (
              <tr key={row.classification_name} className="border-b border-border/30 hover:bg-surface-hover">
                <td className="py-1 pr-4 whitespace-nowrap">{row.classification_name}</td>
                {timeframes.map((tf) => {
                  const val = row[tf] as number | null;
                  return (
                    <td key={tf} className={`py-1 text-right tabular-nums ${clsBold(val)}`}>
                      {val != null ? `${val >= 0 ? "+" : ""}${val.toFixed(1)}%` : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// 8. MARKET BREADTH (with activity bars)
// ═══════════════════════════════════════════════════════════════════════

function BreadthSection({ breadth }: { breadth: Breadth[] }) {
  const latest = breadth[0];
  if (!latest) return null;

  return (
    <section className="border border-border rounded bg-surface p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium">Market Breadth</h2>
        <span className="text-[10px] text-muted">{latest.trade_date}</span>
      </div>

      {/* A/D Ratio + New 52W stats */}
      <div className="flex items-center gap-6 mb-4 text-xs font-mono">
        <div>
          <span className="text-[9px] text-muted block">A/D Ratio</span>
          <span className={`text-lg font-bold ${(latest.advance_decline_ratio ?? 0) >= 1 ? "text-[#2196F3]" : "text-negative"}`}>
            {latest.advance_decline_ratio?.toFixed(2)}
          </span>
        </div>
        <div className="border-l border-border pl-4">
          <span className="text-[9px] text-muted block">Stocks at New 52W High</span>
          <span className="text-lg font-bold text-[#2196F3]">{latest.new_52w_highs}</span>
        </div>
        <div>
          <span className="text-[9px] text-muted block">Stocks at New 52W Low</span>
          <span className="text-lg font-bold text-negative">{latest.new_52w_lows}</span>
        </div>
      </div>

      {/* Header row */}
      <div className="flex items-center gap-3 text-[10px] font-mono text-muted mb-1">
        <span className="w-20">Date</span>
        <span className="w-10 text-right">Adv</span>
        <div className="flex-1" />
        <span className="w-10">Dec</span>
        <span className="w-10 text-right">A/D</span>
      </div>

      {/* All days with inline activity bars (latest first) */}
      <div className="space-y-2">
        {breadth.map((b) => {
          const t = b.advances + b.declines + b.unchanged;
          const aPct = t > 0 ? (b.advances / t * 100) : 50;
          const dPct = t > 0 ? (b.declines / t * 100) : 50;
          return (
            <div key={b.trade_date} className="flex items-center gap-3 text-xs font-mono">
              <span className="text-muted w-20">{b.trade_date}</span>
              <span className="text-[#2196F3] w-10 text-right">{b.advances}</span>
              <div className="flex-1 flex h-3 rounded overflow-hidden bg-border/20">
                <div className="bg-[#2196F3]" style={{ width: `${aPct}%` }} />
                <div className="bg-negative" style={{ width: `${dPct}%` }} />
              </div>
              <span className="text-negative w-10">{b.declines}</span>
              <span className={`w-10 text-right ${(b.advance_decline_ratio ?? 0) >= 1 ? "text-[#2196F3]" : "text-negative"}`}>
                {b.advance_decline_ratio?.toFixed(1)}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// PERIOD CANDLESTICK CHART
// ═══════════════════════════════════════════════════════════════════════

interface PeriodRange {
  label: string;
  high: number | null;
  low: number | null;
  open?: number | null;
  close?: number | null;
}

interface SMALine {
  label: string;
  value: number | null;
  color: string;
}

function PeriodCandleChart({ ranges, currentPrice, smaLines }: {
  ranges: PeriodRange[];
  currentPrice: number | null;
  smaLines: SMALine[];
}) {
  const [hoverY, setHoverY] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const allValues = [
    ...ranges.flatMap((r) => [r.high, r.low, r.open, r.close]),
    ...smaLines.map((s) => s.value),
    currentPrice,
  ].filter((v): v is number => v != null);

  if (allValues.length === 0) return null;

  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues);
  const padding = (maxVal - minVal) * 0.08;
  const yMax = maxVal + padding;
  const yRange = (maxVal - minVal + padding * 2) || 1;

  const chartH = 200;
  const labelH = 20;
  const totalH = chartH + labelH;
  const W = 400;
  const yPx = (v: number) => ((yMax - v) / yRange) * chartH;
  const pxToVal = (py: number) => yMax - (py / chartH) * yRange;

  const valid = ranges.filter((r) => r.high != null && r.low != null);

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const scaleY = totalH / rect.height;
    const y = (e.clientY - rect.top) * scaleY;
    if (y >= 0 && y <= chartH) setHoverY(y);
    else setHoverY(null);
  }

  return (
    <div className="mb-3 overflow-hidden">
      <svg
        ref={svgRef}
        width="100%"
        viewBox={`0 0 ${W} ${totalH}`}
        className="font-mono cursor-crosshair"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverY(null)}
      >
        {/* SMA horizontal lines */}
        {smaLines.map((sma, i) => sma.value != null && (
          <g key={sma.label}>
            <line x1="0" x2={W} y1={yPx(sma.value)} y2={yPx(sma.value)}
              stroke={sma.color} strokeWidth="0.8" strokeDasharray="4 3" opacity="0.7" />
            <text x={i % 2 === 0 ? W - 5 : 5} y={yPx(sma.value) - 4}
              fill={sma.color} fontSize="8" textAnchor={i % 2 === 0 ? "end" : "start"}>
              {sma.label} {fmt(sma.value, 0)}
            </text>
          </g>
        ))}

        {/* Current price line */}
        {currentPrice != null && (
          <g>
            <line x1="0" x2={W} y1={yPx(currentPrice)} y2={yPx(currentPrice)}
              stroke="#888" strokeWidth="0.5" strokeDasharray="2 2" />
            <text x="5" y={yPx(currentPrice) - 4} fill="#888" fontSize="7">CMP {fmt(currentPrice, 0)}</text>
          </g>
        )}

        {/* Candlesticks / Range bars */}
        {valid.map((r, i) => {
          const cx = (i + 0.5) * (W / valid.length);
          const high = r.high!;
          const low = r.low!;
          const hasOHLC = r.open != null && r.close != null;

          if (hasOHLC) {
            const open = r.open!;
            const close = r.close!;
            const isUp = close >= open;
            const bodyTop = yPx(Math.max(open, close));
            const bodyBot = yPx(Math.min(open, close));
            const bodyH = Math.max(bodyBot - bodyTop, 4);
            const color = isUp ? "#00c853" : "#ff5252";

            return (
              <g key={r.label}>
                <line x1={cx} x2={cx} y1={yPx(high)} y2={bodyTop} stroke={color} strokeWidth="2" />
                <line x1={cx} x2={cx} y1={bodyBot} y2={yPx(low)} stroke={color} strokeWidth="2" />
                <rect x={cx - 14} y={bodyTop} width="28" height={bodyH} fill={color} rx="1" />
                <text x={cx} y={chartH + 14} textAnchor="middle" fill="#888" fontSize="9">{r.label}</text>
              </g>
            );
          } else {
            return (
              <g key={r.label}>
                <line x1={cx} x2={cx} y1={yPx(high)} y2={yPx(low)} stroke="#555" strokeWidth="2" />
                <line x1={cx - 6} x2={cx + 6} y1={yPx(high)} y2={yPx(high)} stroke="#555" strokeWidth="1.5" />
                <line x1={cx - 6} x2={cx + 6} y1={yPx(low)} y2={yPx(low)} stroke="#555" strokeWidth="1.5" />
                {currentPrice != null && currentPrice >= low && currentPrice <= high && (
                  <circle cx={cx} cy={yPx(currentPrice)} r="4" fill="#00d4aa" />
                )}
                <text x={cx} y={chartH + 14} textAnchor="middle" fill="#888" fontSize="9">{r.label}</text>
              </g>
            );
          }
        })}

        {/* Hover crosshair + price label */}
        {hoverY != null && (
          <g>
            <line x1="0" x2={W} y1={hoverY} y2={hoverY}
              stroke="#00d4aa" strokeWidth="0.5" strokeDasharray="3 2" opacity="0.8" />
            <rect x={W - 65} y={hoverY - 8} width="62" height="15" rx="2" fill="#1a1a1a" stroke="#00d4aa" strokeWidth="0.5" />
            <text x={W - 34} y={hoverY + 3} fill="#00d4aa" fontSize="8" textAnchor="middle">
              {fmt(pxToVal(hoverY), 0)}
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}
