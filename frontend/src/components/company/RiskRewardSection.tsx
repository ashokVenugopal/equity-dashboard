"use client";

import { useState } from "react";
import type { AttributionRow, CompanyRiskReward, RiskGauge } from "@/lib/api";

/*
 * Risk / Reward section for the company page:
 *   - Altitude gauges: where the CURRENT PE / EV-EBITDA sits within its
 *     1-year floor→peak range (OCF/PAT: within its ~10-FY range).
 *   - Hovering a gauge shows a trend sparkline popover.
 *   - Attribution table: price change per window decomposed into
 *     earnings-driven vs multiple-driven (log-space shares).
 */

const fmtX = (v: number | null | undefined, digits = 1) =>
  v != null ? `${v.toFixed(digits)}×` : "—";

const fmtPct = (v: number | null | undefined) =>
  v != null ? `${v >= 0 ? "+" : ""}${v.toFixed(1)}%` : "—";

const pctCls = (v: number | null | undefined) =>
  v == null ? "text-muted" : v >= 0 ? "text-positive" : "text-negative";

/** Inline SVG sparkline for the hover popover — no chart lib needed. */
function TrendSparkline({ trend }: { trend: RiskGauge["trend"] }) {
  const W = 240;
  const H = 64;
  const PAD = 4;
  if (trend.length < 2) return null;
  const values = trend.map((t) => t.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = trend.map((t, i) => {
    const x = PAD + (i / (trend.length - 1)) * (W - 2 * PAD);
    const y = PAD + (1 - (t.value - min) / span) * (H - 2 * PAD);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <svg width={W} height={H} className="block">
      <polyline
        points={pts.join(" ")}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="1.5"
      />
      {/* Current-value marker */}
      <circle
        cx={pts[pts.length - 1].split(",")[0]}
        cy={pts[pts.length - 1].split(",")[1]}
        r="2.5"
        fill="var(--accent)"
      />
    </svg>
  );
}

/**
 * One altitude gauge, mirroring the reference visual:
 *   floor 20×  ────────────────|────  peak 75×
 *                    PE 59× = 71% altitude
 * For valuation multiples high altitude = expensive (red); for quality
 * ratios like OCF/PAT high altitude = strong (green) — `higherIsBetter`.
 */
function RangeGauge({
  label,
  unit,
  gauge,
  higherIsBetter = false,
  rangeNote,
}: {
  label: string;
  unit?: string;
  gauge: RiskGauge | null;
  higherIsBetter?: boolean;
  rangeNote: string;
}) {
  const [hover, setHover] = useState(false);

  if (!gauge) {
    return (
      <div>
        <div className="text-[11px] text-muted uppercase tracking-wider mb-1">{label}</div>
        <p className="text-muted text-xs">Insufficient data.</p>
      </div>
    );
  }

  const alt = gauge.altitude_pct;
  const hot = higherIsBetter ? alt < 35 : alt > 65;
  const cool = higherIsBetter ? alt > 65 : alt < 35;
  const markerColor = hot ? "var(--negative)" : cool ? "var(--positive)" : "var(--accent)";
  const fmt = unit === "x" ? fmtX : (v: number) => v.toFixed(2);

  return (
    <div
      className="relative"
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      <div className="flex items-baseline justify-between mb-1">
        <div className="text-[11px] text-muted uppercase tracking-wider">{label}</div>
        <div className="text-[10px] text-muted">{rangeNote}</div>
      </div>

      <div className="flex items-baseline justify-between text-[11px] font-mono mb-1">
        <span className="text-muted">floor {fmt(gauge.floor)}</span>
        <span className="text-muted">peak {fmt(gauge.peak)}</span>
      </div>

      {/* Track */}
      <div className="relative h-3 rounded-full bg-surface-hover overflow-visible mb-1">
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{
            width: `${alt}%`,
            background: `color-mix(in srgb, ${markerColor} 25%, transparent)`,
          }}
        />
        {/* Marker */}
        <div
          className="absolute top-[-3px] bottom-[-3px] w-[2.5px] rounded"
          style={{ left: `calc(${alt}% - 1px)`, background: markerColor }}
        />
      </div>

      <div className="text-[12px] font-mono">
        <span style={{ color: markerColor }} className="font-bold">
          {label.split(" ")[0]} {fmt(gauge.current)}
        </span>
        <span className="text-muted"> = {alt.toFixed(0)}% altitude</span>
        <span className="text-[10px] text-muted ml-2">as of {gauge.current_date}</span>
      </div>

      {/* Hover popover with trend sparkline */}
      {hover && gauge.trend.length >= 2 && (
        <div className="absolute z-20 left-0 top-full mt-1 border border-border rounded bg-surface/95 backdrop-blur-sm p-2 shadow-lg">
          <div className="text-[10px] text-muted mb-1">
            {label} trend · {gauge.trend[0].date} → {gauge.trend[gauge.trend.length - 1].date}
          </div>
          <TrendSparkline trend={gauge.trend} />
        </div>
      )}
    </div>
  );
}

/** Split bar showing earnings-vs-multiple share of a price move. */
function AttributionSplitBar({ row }: { row: AttributionRow }) {
  if (row.earnings_share_pct == null || row.multiple_share_pct == null) {
    return <span className="text-[10px] text-muted">n/a</span>;
  }
  // Shares can exceed 0..100 when earnings and multiple pulled in opposite
  // directions; clamp the visual, keep exact numbers in the cells.
  const e = Math.max(0, Math.min(100, row.earnings_share_pct));
  return (
    <div
      className="flex h-2.5 w-24 rounded-sm overflow-hidden"
      title={`fundamentals ${fmtPct(row.earnings_share_pct)} / multiple ${fmtPct(row.multiple_share_pct)}`}
    >
      <div className="bg-accent/80" style={{ width: `${e}%` }} />
      <div className="bg-muted/40" style={{ width: `${100 - e}%` }} />
    </div>
  );
}

function AttributionTable({ rows }: { rows: AttributionRow[] }) {
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <div className="text-[11px] text-muted uppercase tracking-wider">
          Price change — earnings vs multiple
        </div>
        <div className="flex gap-3 text-[10px] text-muted">
          <span className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-sm bg-accent/80" />
            fundamentals
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-sm bg-muted/40" />
            multiple
          </span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse font-mono text-[11px]">
          <thead>
            <tr className="border-b border-border text-muted">
              <th className="text-left py-1 pr-3 font-medium">Window</th>
              <th className="text-right py-1 px-3 font-medium">Price Δ</th>
              <th className="text-right py-1 px-3 font-medium">Earnings Δ</th>
              <th className="text-right py-1 px-3 font-medium">Multiple Δ</th>
              <th className="text-left py-1 pl-3 font-medium">Driven by</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.window} className="border-b border-border/30">
                <td className="py-1 pr-3 text-muted">
                  {r.window}
                  {r.eps_source === "annual" && (
                    <span className="text-[9px] ml-1" title="EPS from annual statements (TTM history too short)">
                      (FY EPS)
                    </span>
                  )}
                </td>
                {r.available ? (
                  <>
                    <td className={`text-right py-1 px-3 ${pctCls(r.price_change_pct)}`}>
                      {fmtPct(r.price_change_pct)}
                    </td>
                    <td className={`text-right py-1 px-3 ${pctCls(r.earnings_change_pct)}`}>
                      {fmtPct(r.earnings_change_pct)}
                    </td>
                    <td className={`text-right py-1 px-3 ${pctCls(r.multiple_change_pct)}`}>
                      {fmtPct(r.multiple_change_pct)}
                    </td>
                    <td className="py-1 pl-3">
                      <AttributionSplitBar row={r} />
                    </td>
                  </>
                ) : (
                  <td colSpan={4} className="py-1 px-3 text-muted text-[10px]">
                    insufficient history
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function RiskRewardSection({ data }: { data: CompanyRiskReward | null }) {
  if (!data) {
    return (
      <section id="risk_reward" className="snap-section">
        <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">
          Risk / Reward
        </h2>
        <p className="text-muted text-xs">
          No risk/reward data — needs quarterly EPS and daily price history.
        </p>
      </section>
    );
  }

  return (
    <section id="risk_reward" className="snap-section">
      <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">
        Risk / Reward
      </h2>
      <div className="border border-border rounded bg-surface p-4 space-y-5">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <RangeGauge label="P/E (TTM)" unit="x" gauge={data.pe} rangeNote="1y range" />
          <RangeGauge label="EV/EBITDA (TTM)" unit="x" gauge={data.ev_ebitda} rangeNote="1y range" />
          <RangeGauge
            label="OCF/PAT"
            gauge={data.ocf_pat}
            higherIsBetter
            rangeNote="10-FY range (annual)"
          />
        </div>
        <AttributionTable rows={data.attribution} />
      </div>
    </section>
  );
}
