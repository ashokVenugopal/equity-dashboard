"use client";

import { useCallback, useState, useRef } from "react";
import {
  getFundFlowSummary,
  getFundFlowDaily,
  getDerivativesFIIPositioning,
  getGlobalOverview,
  getMarketBreadth,
  getSectorPerformance,
  getIndexDetailStats,
  getIndexDetailOverview,
  type IndexStats,
  type GlobalInstrument,
  type Breadth,
  type FIIPositioning,
  type SectorPerformanceRow,
} from "@/lib/api";
import { PageHeader } from "@/components/shared/PageHeader";
import { ParticipantPositioningPanel } from "@/components/derivatives/ParticipantPositioningPanel";
import { useCachedData } from "@/lib/cache";
import {
  computeFIIStreak,
  computeRelativeStrength,
  computeLevelDistance,
  matchGlobalCues,
  computeCandleScale,
} from "@/lib/analytics";

// ── Helpers ──

const fmt = (v: number | null | undefined, digits = 2) =>
  v != null ? v.toLocaleString("en-IN", { maximumFractionDigits: digits }) : "—";

const fmtPct = (v: number | null | undefined) =>
  v != null ? `${v >= 0 ? "+" : ""}${v.toFixed(2)}%` : "—";

const cls = (v: number | null | undefined) =>
  v == null ? "text-muted" : v >= 0 ? "text-positive" : "text-negative";

const clsBold = (v: number | null | undefined) =>
  v == null ? "text-muted" : v >= 0 ? "text-positive font-bold" : "text-negative font-bold";

// ── Types ──

interface AnujData {
  flowSummary: Record<string, unknown>;
  flowDaily: { flows: Record<string, unknown>[] };
  niftyStats: IndexStats;
  niftyOverview: Record<string, unknown>;
  bankNiftyStats: IndexStats;
  bankNiftyOverview: Record<string, unknown>;
  fiiPos: FIIPositioning[];
  globalGroups: Record<string, GlobalInstrument[]>;
  breadth: Breadth[];
  sectorPerf: SectorPerformanceRow[];
}

// ── Page ──

export default function AnujPage() {
  const fetcher = useCallback(async () => {
    const [
      flowSummary, flowDaily,
      niftyStats, niftyOverview, bankNiftyStats, bankNiftyOverview,
      posData, globalData, breadthData, sectorData,
    ] = await Promise.all([
      getFundFlowSummary(),
      getFundFlowDaily("CASH", 10),
      getIndexDetailStats("nifty-50"),
      getIndexDetailOverview("nifty-50"),
      getIndexDetailStats("nifty-bank"),
      getIndexDetailOverview("nifty-bank"),
      // 40 rows = 5 trade dates × 2 participants × 4 instrument categories.
      // Covers the 5-day history panel for both FII and CLIENT.
      getDerivativesFIIPositioning(40, ["FII", "CLIENT"]),
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
      fiiPos: posData.positioning,
      globalGroups: globalData.groups,
      breadth: breadthData.breadth,
      sectorPerf: sectorData.performance,
    } as AnujData;
  }, []);

  const { data, loading, loadedAt, refresh, error } = useCachedData("anuj-setup", fetcher, 5 * 60 * 1000);

  if (error && !data) {
    return <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">{error}</div>;
  }
  if (!data) {
    return <div className="text-muted text-xs py-8 text-center">Loading Trade Setup...</div>;
  }

  return (
    <div className="space-y-4">
      <PageHeader title="Anuj Singhal — Trade Setup" loadedAt={loadedAt} loading={loading} onRefresh={refresh} />

      {/* 1. Global Cues Strip */}
      <GlobalCuesStrip groups={data.globalGroups} />

      {/* 2. FII Activity Snapshot */}
      <FIISnapshotStrip summary={data.flowSummary} daily={data.flowDaily} />

      {/* 3 & 4. Nifty + Bank Nifty Technical Levels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TechnicalLevelsPanel label="NIFTY 50" overview={data.niftyOverview} stats={data.niftyStats} />
        <TechnicalLevelsPanel label="NIFTY BANK" overview={data.bankNiftyOverview} stats={data.bankNiftyStats} />
      </div>

      {/* 5. Market Breadth */}
      <BreadthPanel breadth={data.breadth} />

      {/* 6. Sector Rotation */}
      <SectorRotationPanel performance={data.sectorPerf} niftyStats={data.niftyStats} />

      {/* 7. FII vs Client Derivatives Positioning */}
      <ParticipantPositioningPanel positioning={data.fiiPos} />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// 1. GLOBAL CUES — Compact Strip
// ═══════════════════════════════════════════════════════════════════════

const KEY_GLOBALS: Record<string, string[]> = {
  index: ["DJI", "IXIC", "GSPC", "GIFTNIFTY"],
  commodity: ["BRENTUSD", "GOLDUSD"],
  forex: ["USDINR", "DXY"],
};

function GlobalCuesStrip({ groups }: { groups: Record<string, GlobalInstrument[]> }) {
  const items = matchGlobalCues(groups, KEY_GLOBALS);

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => {
        const changePct = item.open && item.close && item.open !== 0
          ? ((item.close - item.open) / item.open * 100) : null;
        return (
          <div key={item.name} className="border border-border/50 rounded px-2 py-1 text-[10px] font-mono flex items-center gap-1.5">
            <span className="text-muted">{item.name.split(" ").slice(0, 2).join(" ")}</span>
            <span className="text-foreground">{fmt(item.close, 1)}</span>
            {changePct != null && (
              <span className={cls(changePct)}>{changePct >= 0 ? "+" : ""}{changePct.toFixed(1)}%</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// 2. FII SNAPSHOT — One-liner with streak
// ═══════════════════════════════════════════════════════════════════════

function FIISnapshotStrip({ summary, daily }: { summary: Record<string, unknown>; daily: { flows: Record<string, unknown>[] } }) {
  const latest = (summary.latest as Record<string, unknown>[]) || [];
  const fiiNet = (latest.find((r) => r.participant_type === "FII")?.net_value as number | null) ?? null;
  const diiNet = (latest.find((r) => r.participant_type === "DII")?.net_value as number | null) ?? null;

  const flows = (daily.flows || []) as { fii_net: number | null }[];
  const streak = computeFIIStreak(flows);
  const streakLabel = streak && streak.count > 1
    ? `${streak.count} consecutive ${streak.direction === "buy" ? "buying" : "selling"} days`
    : "";

  return (
    <div className="border border-border rounded bg-surface px-4 py-2 flex items-center gap-6 text-xs font-mono">
      <div className="flex items-center gap-2">
        <span className="text-muted">FII:</span>
        <span className={`font-bold ${cls(fiiNet)}`}>
          {fiiNet != null ? `${fiiNet >= 0 ? "+" : ""}${fmt(fiiNet, 0)} Cr` : "—"}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-muted">DII:</span>
        <span className={`font-bold ${cls(diiNet)}`}>
          {diiNet != null ? `${diiNet >= 0 ? "+" : ""}${fmt(diiNet, 0)} Cr` : "—"}
        </span>
      </div>
      {streakLabel && (
        <span className={`text-[10px] ${streak?.direction === "buy" ? "text-positive" : "text-negative"}`}>
          ({streakLabel})
        </span>
      )}
      <span className="text-muted ml-auto text-[10px]">{summary.latest_date as string || ""}</span>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// 3 & 4. TECHNICAL LEVELS PANEL (Nifty / Bank Nifty)
// ═══════════════════════════════════════════════════════════════════════

function TechnicalLevelsPanel({ label, overview, stats }: {
  label: string; overview: Record<string, unknown>; stats: IndexStats;
}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const price = overview.price as any;
  const tech = stats.technicals;
  const sr = stats.support_resistance;
  const ranges = stats.price_ranges || {};

  if (!price) {
    return (
      <section className="border border-border rounded bg-surface p-4">
        <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium">{label}</h2>
        <span className="text-muted text-xs">No data</span>
      </section>
    );
  }

  const close = price.close as number;

  // DMA levels with distance %
  const dmaLevels = [
    { label: "20 DMA", value: tech.dma_30 },  // dma_30 is closest we have to 20
    { label: "50 DMA", value: tech.dma_50 },
    { label: "100 DMA", value: tech.dma_100 },
    { label: "200 DMA", value: tech.dma_200 },
  ];

  // 52W extremes
  const high52w = ranges.year_high as number | null;
  const low52w = ranges.year_low as number | null;
  const distHigh = computeLevelDistance(close, high52w)?.distance ?? null;
  const distLow = computeLevelDistance(close, low52w)?.distance ?? null;

  return (
    <section className="border border-border rounded bg-surface p-4">
      <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium mb-2">{label}</h2>

      {/* Price + change */}
      <div className="flex items-baseline gap-3 mb-3">
        <span className="text-xl font-bold font-mono">{fmt(close)}</span>
        <span className={`text-sm font-mono ${clsBold(price.change)}`}>{fmtPct(price.change_pct)}</span>
        <span className="text-[10px] text-muted">{price.trade_date}</span>
      </div>

      {/* DMA Reference Levels — THE KEY SECTION */}
      <div className="mb-3">
        <div className="text-[9px] text-muted uppercase tracking-wider mb-1">DMA Positions</div>
        <div className="space-y-1">
          {dmaLevels.map((dma) => {
            const d = computeLevelDistance(close, dma.value);
            if (!d) return null;
            const { distance: dist, above } = d;
            return (
              <div key={dma.label} className="flex items-center gap-2 text-xs font-mono">
                <span className="text-muted w-16">{dma.label}</span>
                <span className="text-foreground w-16 text-right">{fmt(dma.value, 0)}</span>
                <span className={`w-12 text-right font-bold ${above ? "text-positive" : "text-negative"}`}>
                  {dist >= 0 ? "+" : ""}{dist.toFixed(1)}%
                </span>
                <div className="flex-1 h-1.5 bg-border/30 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${above ? "bg-positive" : "bg-negative"}`}
                    style={{ width: `${Math.min(Math.abs(dist) * 5, 100)}%` }}
                  />
                </div>
                <span className={`text-[9px] ${above ? "text-positive" : "text-negative"}`}>
                  {above ? "Above" : "Below"}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* 52W Distance */}
      <div className="grid grid-cols-2 gap-3 mb-3 text-xs font-mono">
        <div className="border border-border/30 rounded p-1.5">
          <div className="text-[9px] text-muted">52W High</div>
          <div className="text-foreground">{fmt(high52w, 0)}</div>
          <div className={`text-[10px] font-bold ${cls(distHigh)}`}>{distHigh != null ? `${distHigh.toFixed(1)}% away` : "—"}</div>
        </div>
        <div className="border border-border/30 rounded p-1.5">
          <div className="text-[9px] text-muted">52W Low</div>
          <div className="text-foreground">{fmt(low52w, 0)}</div>
          <div className={`text-[10px] font-bold ${cls(distLow)}`}>{distLow != null ? `+${distLow.toFixed(1)}% above` : "—"}</div>
        </div>
      </div>

      {/* Period Candlestick Chart */}
      <PeriodCandleChart
        ranges={[
          { label: "Day", high: price.high, low: price.low, open: price.open, close: price.close },
          { label: "1W", high: ranges.week_high, low: ranges.week_low, open: ranges.week_open, close: price.close },
          { label: "1M", high: ranges.month_high, low: ranges.month_low, open: ranges.month_open, close: price.close },
          { label: "MTD", high: ranges.this_month_high, low: ranges.this_month_low, open: ranges.this_month_open, close: price.close },
          { label: "1Y", high: ranges.year_high, low: ranges.year_low, open: ranges.year_open, close: price.close },
          { label: "YTD", high: ranges.ytd_high, low: ranges.ytd_low, open: ranges.ytd_open, close: price.close },
        ]}
        currentPrice={close}
        smaLines={[
          { label: "50 DMA", value: tech.dma_50, color: "#FFD700" },
          { label: "200 DMA", value: tech.dma_200, color: "#FF6B6B" },
        ]}
      />

      {/* RSI */}
      <div className="flex items-center gap-3 text-[10px] font-mono mb-3">
        <span className="text-muted">RSI (14):</span>
        <span className={`font-bold ${(tech.rsi_14 ?? 50) > 70 ? "text-negative" : (tech.rsi_14 ?? 50) < 30 ? "text-positive" : "text-foreground"}`}>
          {tech.rsi_14 != null ? fmt(tech.rsi_14) : "—"}
        </span>
        {tech.rsi_14 != null && (
          <span className="text-muted">{tech.rsi_14 > 70 ? "Overbought" : tech.rsi_14 < 30 ? "Oversold" : "Neutral"}</span>
        )}
      </div>

      {/* S&R Levels */}
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
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// 5. MARKET BREADTH
// ═══════════════════════════════════════════════════════════════════════

function BreadthPanel({ breadth }: { breadth: Breadth[] }) {
  const latest = breadth[0];
  if (!latest) return null;

  return (
    <section className="border border-border rounded bg-surface p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium">Market Breadth</h2>
        <span className="text-[10px] text-muted">{latest.trade_date}</span>
      </div>

      {/* Summary stats */}
      <div className="flex items-center gap-6 mb-3 text-xs font-mono">
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

      {/* Activity bars — all days */}
      <div className="flex items-center gap-3 text-[10px] font-mono text-muted mb-1">
        <span className="w-20">Date</span><span className="w-10 text-right">Adv</span>
        <div className="flex-1" /><span className="w-10">Dec</span><span className="w-10 text-right">A/D</span>
      </div>
      <div className="space-y-1.5">
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
// 6. SECTOR ROTATION — Relative Strength vs Nifty
// ═══════════════════════════════════════════════════════════════════════

function SectorRotationPanel({ performance, niftyStats }: {
  performance: SectorPerformanceRow[];
  niftyStats: IndexStats;
}) {
  if (!performance || performance.length === 0) return null;

  // Get Nifty's 1M return for relative comparison
  const nifty1m = niftyStats.performance.find((p) => p.key === "1m")?.change_pct ?? null;

  // Always render these columns — missing data renders as '—' rather than hiding the column
  const timeframes = ["1d", "1w", "4w", "13w", "52w"];
  const tfLabels: Record<string, string> = { "1d": "1D", "1w": "1W", "4w": "1M", "13w": "3M", "26w": "6M", "52w": "1Y" };
  const showNiftyCompare = nifty1m != null;

  return (
    <section className="border border-border rounded bg-surface p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-[10px] text-muted uppercase tracking-wider font-medium">Sector Rotation — Relative Strength</h2>
        {showNiftyCompare && (
          <span className="text-[10px] text-muted font-mono">Nifty 1M: <span className={cls(nifty1m)}>{fmtPct(nifty1m)}</span></span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead>
            <tr className="text-[10px] text-muted border-b border-border">
              <th className="text-left py-1">Sector</th>
              {timeframes.flatMap((tf) => {
                const header = <th key={tf} className="text-right py-1">{tfLabels[tf] ?? tf}</th>;
                if (tf === "4w" && showNiftyCompare) {
                  return [header, <th key="vs" className="text-right py-1 text-accent/70">vs Nifty 1M</th>];
                }
                return [header];
              })}
            </tr>
          </thead>
          <tbody>
            {performance.map((row) => {
              const sector1m = row["4w"] as number | null;
              const relative = computeRelativeStrength(sector1m, nifty1m);
              return (
                <tr key={row.classification_name} className="border-b border-border/30 hover:bg-surface-hover">
                  <td className="py-1 pr-4 whitespace-nowrap">{row.classification_name}</td>
                  {timeframes.flatMap((tf) => {
                    const val = row[tf] as number | null;
                    const cell = (
                      <td key={tf} className={`py-1 text-right tabular-nums ${clsBold(val)}`}>
                        {val != null ? `${val >= 0 ? "+" : ""}${val.toFixed(1)}%` : "—"}
                      </td>
                    );
                    if (tf === "4w" && showNiftyCompare) {
                      return [
                        cell,
                        <td key="vs" className={`py-1 text-right tabular-nums ${clsBold(relative)}`}>
                          {relative != null ? `${relative >= 0 ? "+" : ""}${relative.toFixed(1)}%` : "—"}
                        </td>,
                      ];
                    }
                    return [cell];
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}


// ═══════════════════════════════════════════════════════════════════════
// PERIOD CANDLESTICK CHART (copied from CNBC — same component)
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

  const scale = computeCandleScale([
    ...ranges.flatMap((r) => [r.high, r.low, r.open, r.close]),
    ...smaLines.map((s) => s.value),
    currentPrice,
  ]);

  if (!scale) return null;

  const { yMax, yRange } = scale;

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
      <svg ref={svgRef} width="100%" viewBox={`0 0 ${W} ${totalH}`} className="font-mono cursor-crosshair"
        onMouseMove={handleMouseMove} onMouseLeave={() => setHoverY(null)}>
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
        {currentPrice != null && (
          <g>
            <line x1="0" x2={W} y1={yPx(currentPrice)} y2={yPx(currentPrice)}
              stroke="#888" strokeWidth="0.5" strokeDasharray="2 2" />
            <text x="5" y={yPx(currentPrice) - 4} fill="#888" fontSize="7">CMP {fmt(currentPrice, 0)}</text>
          </g>
        )}
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
