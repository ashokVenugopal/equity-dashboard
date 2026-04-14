"use client";

import { useState, useMemo, useEffect, useRef } from "react";
import Link from "next/link";
import { createChart, ColorType, LineSeries } from "lightweight-charts";

interface ThisViewRow {
  symbol: string;
  name: string;
  close: number | null;
  change_pct: number | null;
  volume: number | null;
  market_cap: number | null;
  high_52w: number | null;
  low_52w: number | null;
  range_pct: number | null;
  sparkline: { t: string; c: number }[];
}

interface ThisViewTableProps {
  rows: ThisViewRow[];
}

type SortDir = "asc" | "desc";

export function ThisViewTable({ rows }: ThisViewTableProps) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    return [...rows].sort((a, b) => {
      const aVal = a[sortKey as keyof ThisViewRow];
      const bVal = b[sortKey as keyof ThisViewRow];
      if (aVal == null) return 1;
      if (bVal == null) return -1;
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDir === "asc" ? aVal - bVal : bVal - aVal;
      }
      return sortDir === "asc"
        ? String(aVal).localeCompare(String(bVal))
        : String(bVal).localeCompare(String(aVal));
    });
  }, [rows, sortKey, sortDir]);

  function handleSort(key: string) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const fmt = (v: number | null, digits = 2) =>
    v != null ? v.toLocaleString("en-IN", { maximumFractionDigits: digits }) : "—";

  const fmtVol = (v: number | null) => {
    if (v == null) return "—";
    if (v >= 1e7) return `${(v / 1e7).toFixed(1)}Cr`;
    if (v >= 1e5) return `${(v / 1e5).toFixed(1)}L`;
    if (v >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
    return String(v);
  };

  const fmtMcap = (v: number | null) => {
    if (v == null) return "—";
    if (v >= 1e5) return `${(v / 1e5).toFixed(0)}L Cr`;
    if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K Cr`;
    return `${v.toFixed(0)} Cr`;
  };

  const COLS: { key: string; label: string; width: string }[] = [
    { key: "symbol", label: "Symbol", width: "w-20" },
    { key: "name", label: "Company", width: "w-36" },
    { key: "sparkline", label: "3M Chart", width: "w-28" },
    { key: "close", label: "LTP", width: "w-20" },
    { key: "change_pct", label: "Chg %", width: "w-16" },
    { key: "market_cap", label: "MCap", width: "w-20" },
    { key: "volume", label: "Volume", width: "w-16" },
    { key: "range_52w", label: "52W Range", width: "w-44" },
  ];

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse font-mono text-xs">
        <thead>
          <tr className="border-b border-border">
            {COLS.map((col) => (
              <th
                key={col.key}
                onClick={() => col.key !== "sparkline" && col.key !== "range_52w" && handleSort(col.key)}
                className={`
                  px-2 py-1.5 font-medium text-muted whitespace-nowrap
                  ${col.key !== "sparkline" && col.key !== "range_52w" ? "cursor-pointer hover:text-foreground" : ""}
                  ${col.key === "symbol" || col.key === "name" ? "text-left" : "text-right"}
                  ${col.key === "range_52w" ? "text-center" : ""}
                `}
              >
                {col.label}
                {sortKey === col.key && (
                  <span className="ml-1 text-accent">{sortDir === "asc" ? "▲" : "▼"}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr
              key={row.symbol}
              className="border-b border-border/50 hover:bg-surface-hover transition-colors"
            >
              {/* Symbol */}
              <td className="px-2 py-1.5 text-left">
                <Link href={`/company/${row.symbol}`} className="text-accent hover:underline">
                  {row.symbol}
                </Link>
              </td>

              {/* Company name */}
              <td className="px-2 py-1.5 text-left text-muted truncate max-w-[160px]" title={row.name}>
                {row.name}
              </td>

              {/* 3M Sparkline */}
              <td className="px-1 py-0.5">
                <MiniSparkline data={row.sparkline} />
              </td>

              {/* LTP */}
              <td className="px-2 py-1.5 text-right tabular-nums">{fmt(row.close)}</td>

              {/* Change % */}
              <td className={`px-2 py-1.5 text-right tabular-nums font-bold ${
                row.change_pct == null ? "text-muted" :
                row.change_pct >= 0 ? "text-positive" : "text-negative"
              }`}>
                {row.change_pct != null
                  ? `${row.change_pct >= 0 ? "+" : ""}${row.change_pct.toFixed(2)}%`
                  : "—"}
              </td>

              {/* Market Cap */}
              <td className="px-2 py-1.5 text-right tabular-nums text-muted">{fmtMcap(row.market_cap)}</td>

              {/* Volume */}
              <td className="px-2 py-1.5 text-right tabular-nums text-muted">{fmtVol(row.volume)}</td>

              {/* 52W Range Bar */}
              <td className="px-2 py-1.5">
                <RangeBar
                  low={row.low_52w}
                  high={row.high_52w}
                  current={row.close}
                  pct={row.range_pct}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {sorted.length === 0 && (
        <div className="text-center text-muted py-8 text-xs">No data</div>
      )}
    </div>
  );
}

function MiniSparkline({ data }: { data: { t: string; c: number }[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || data.length < 2) return;

    const chart = createChart(containerRef.current, {
      width: 100,
      height: 28,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "transparent",
      },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      crosshair: { vertLine: { visible: false }, horzLine: { visible: false } },
      handleScroll: false,
      handleScale: false,
    });

    const isUp = data[data.length - 1].c >= data[0].c;
    const series = chart.addSeries(LineSeries, {
      color: isUp ? "#00c853" : "#ff5252",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });
    series.setData(data.map((d) => ({ time: d.t, value: d.c })));
    chart.timeScale().fitContent();

    return () => { chart.remove(); };
  }, [data]);

  if (data.length < 2) {
    return <div className="w-[100px] h-[28px] flex items-center justify-center text-muted text-[9px]">—</div>;
  }

  // Tooltip: 3M return summary
  const first = data[0].c;
  const last = data[data.length - 1].c;
  const ret = first > 0 ? ((last - first) / first * 100).toFixed(2) : "?";
  const title = `3M: ${data[0].t} → ${data[data.length - 1].t}\n${first.toLocaleString("en-IN")} → ${last.toLocaleString("en-IN")} (${Number(ret) >= 0 ? "+" : ""}${ret}%)`;

  return <div ref={containerRef} className="w-[100px] h-[28px]" title={title} />;
}

function RangeBar({
  low,
  high,
  current,
  pct,
}: {
  low: number | null;
  high: number | null;
  current: number | null;
  pct: number | null;
}) {
  if (low == null || high == null || pct == null) {
    return <span className="text-muted text-[9px]">—</span>;
  }

  const fmt = (v: number) => v.toLocaleString("en-IN", { maximumFractionDigits: 0 });

  return (
    <div className="flex items-center gap-1.5 min-w-[160px]">
      <span className="text-[9px] text-muted tabular-nums w-12 text-right">{fmt(low)}</span>
      <div className="relative flex-1 h-1.5 bg-border rounded-full">
        {/* Gradient bar */}
        <div
          className="absolute inset-0 rounded-full overflow-hidden"
          style={{
            background: "linear-gradient(to right, var(--negative), #444 50%, var(--positive))",
          }}
        />
        {/* Position indicator */}
        <div
          className="absolute top-[-2px] w-2 h-2 rounded-full bg-foreground border border-background"
          style={{
            left: `${Math.max(0, Math.min(100, pct))}%`,
            transform: "translateX(-50%)",
          }}
        />
      </div>
      <span className="text-[9px] text-muted tabular-nums w-12 text-left">{fmt(high)}</span>
    </div>
  );
}
