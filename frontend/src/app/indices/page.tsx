"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getIndexHistoryBasket,
  getIndexHistoryCatalog,
  getIndexHistorySeries,
  getIndexHistoryStats,
  type IndexCatalog,
  type IndexStatsRow,
  type RangeHL,
} from "@/lib/api";
import { MultiLineChart, type OverlayLine } from "@/components/charts/MultiLineChart";
import { PageHeader } from "@/components/shared/PageHeader";

/*
 * Index History page: overlay up to 4 instruments (standard indices,
 * global instruments, stocks for pair comparison) plus optional custom
 * baskets (equal-weight classification groups), normalized to 100.
 * Stats table shows 52W / 3Y / all-time high-low with distance.
 */

const LINE_COLORS = ["#2196F3", "#FFD700", "#AB47BC", "#26A69A", "#FF7043"];
const RANGES = ["1y", "3y", "5y", "max"] as const;

const fmt = (v: number | null | undefined, digits = 2) =>
  v != null ? v.toLocaleString("en-IN", { maximumFractionDigits: digits }) : "—";

const pctCls = (v: number) => (v >= 0 ? "text-positive" : "text-negative");

const DEFAULT_SYMBOLS = ["NIFTY50", "BANKNIFTY"];

export default function IndicesPage() {
  const [catalog, setCatalog] = useState<IndexCatalog | null>(null);
  const [symbols, setSymbols] = useState<string[]>(DEFAULT_SYMBOLS);
  const [basketKey, setBasketKey] = useState<string>("");
  const [range, setRange] = useState<(typeof RANGES)[number]>("3y");
  const [lines, setLines] = useState<OverlayLine[]>([]);
  const [stats, setStats] = useState<IndexStatsRow[]>([]);
  const [pickerInput, setPickerInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getIndexHistoryCatalog().then(setCatalog).catch(() => setCatalog(null));
  }, []);

  const load = useCallback(async () => {
    if (symbols.length === 0 && !basketKey) return;
    setLoading(true);
    setError(null);
    try {
      const jobs: Promise<void>[] = [];
      const nextLines: OverlayLine[] = [];

      if (symbols.length > 0) {
        jobs.push(
          getIndexHistorySeries(symbols, range).then((d) => {
            d.series.forEach((s, i) => {
              nextLines.push({
                label: s.symbol,
                color: LINE_COLORS[i % LINE_COLORS.length],
                points: s.points,
              });
            });
          }),
        );
        jobs.push(getIndexHistoryStats(symbols).then((d) => setStats(d.stats)));
      } else {
        setStats([]);
      }

      if (basketKey) {
        const [ctype, ...rest] = basketKey.split(":");
        jobs.push(
          getIndexHistoryBasket(ctype, rest.join(":"), range).then((d) => {
            nextLines.push({
              label: `${rest.join(":")} (eq-wt, ${d.members_used})`,
              color: LINE_COLORS[4],
              points: d.points,
            });
          }),
        );
      }

      await Promise.all(jobs);
      // Keep insertion order stable: symbols first, basket last
      setLines(nextLines);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [symbols, basketKey, range]);

  useEffect(() => {
    load();
  }, [load]);

  const allSymbols = useMemo(() => {
    if (!catalog) return [];
    return Object.entries(catalog.instruments).flatMap(([type, list]) =>
      list.map((i) => ({ ...i, type })),
    );
  }, [catalog]);

  const addSymbol = (sym: string) => {
    const s = sym.trim().toUpperCase();
    if (!s || symbols.includes(s) || symbols.length >= 4) return;
    if (!allSymbols.some((i) => i.symbol === s)) return;
    setSymbols([...symbols, s]);
    setPickerInput("");
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Index History" loadedAt={null} loading={loading} onRefresh={load} />

      {/* Controls */}
      <section className="border border-border rounded bg-surface p-3 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          {symbols.map((s, i) => (
            <span
              key={s}
              className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded border border-border"
              style={{ color: LINE_COLORS[i % LINE_COLORS.length] }}
            >
              {s}
              <button
                className="text-muted hover:text-negative ml-1"
                onClick={() => setSymbols(symbols.filter((x) => x !== s))}
              >
                ×
              </button>
            </span>
          ))}
          {symbols.length < 4 && (
            <>
              <input
                list="instrument-options"
                value={pickerInput}
                onChange={(e) => setPickerInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && addSymbol(pickerInput)}
                placeholder="add symbol…"
                className="bg-background border border-border rounded px-2 py-0.5 text-[11px] font-mono w-40"
              />
              <datalist id="instrument-options">
                {allSymbols.map((i) => (
                  <option key={`${i.type}:${i.symbol}`} value={i.symbol}>
                    {i.name} ({i.type})
                  </option>
                ))}
              </datalist>
              <button
                className="text-[11px] text-accent border border-border rounded px-2 py-0.5"
                onClick={() => addSymbol(pickerInput)}
              >
                add
              </button>
            </>
          )}

          <span className="text-muted text-[10px] ml-2">custom basket:</span>
          <select
            value={basketKey}
            onChange={(e) => setBasketKey(e.target.value)}
            className="bg-background border border-border rounded px-2 py-0.5 text-[11px] font-mono max-w-56"
          >
            <option value="">none</option>
            {catalog?.baskets.map((b) => (
              <option
                key={`${b.classification_type}:${b.classification_name}`}
                value={`${b.classification_type}:${b.classification_name}`}
              >
                {b.classification_name} ({b.classification_type}, {b.members})
              </option>
            ))}
          </select>

          <div className="flex gap-1 ml-auto">
            {RANGES.map((r) => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`text-[11px] px-2 py-0.5 rounded border ${
                  range === r ? "border-accent text-accent" : "border-border text-muted"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
        <p className="text-[10px] text-muted">
          All series rebased to 100 at the start of the window — relative performance, not price.
        </p>
      </section>

      {error && (
        <div className="text-negative text-xs border border-negative/30 rounded p-2 bg-negative/5">{error}</div>
      )}

      {/* Overlay chart */}
      <section className="border border-border rounded bg-surface p-3">
        <MultiLineChart lines={lines} height={360} />
      </section>

      {/* Stats table */}
      {stats.length > 0 && (
        <section className="border border-border rounded bg-surface p-3">
          <h2 className="text-[11px] text-muted uppercase tracking-wider font-medium mb-2">
            Range stats
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse font-mono text-[11px]">
              <thead>
                <tr className="border-b border-border text-muted">
                  <th className="text-left py-1 pr-3 font-medium">Symbol</th>
                  <th className="text-right py-1 px-3 font-medium">Last</th>
                  <th className="text-right py-1 px-3 font-medium">52W H / L</th>
                  <th className="text-right py-1 px-3 font-medium">off 52W-H</th>
                  <th className="text-right py-1 px-3 font-medium">3Y H / L</th>
                  <th className="text-right py-1 px-3 font-medium">off 3Y-H</th>
                  <th className="text-right py-1 px-3 font-medium">ATH / ATL</th>
                  <th className="text-right py-1 px-3 font-medium">off ATH</th>
                  <th className="text-right py-1 pl-3 font-medium">since</th>
                </tr>
              </thead>
              <tbody>
                {stats.map((s) => {
                  const hl = (r?: RangeHL) =>
                    r ? `${fmt(r.high, 0)} / ${fmt(r.low, 0)}` : "—";
                  return (
                    <tr key={s.symbol} className="border-b border-border/30">
                      <td className="py-1 pr-3">{s.symbol}</td>
                      {s.available ? (
                        <>
                          <td className="text-right py-1 px-3">{fmt(s.last)}</td>
                          <td className="text-right py-1 px-3">{hl(s.w52)}</td>
                          <td className={`text-right py-1 px-3 ${pctCls(s.w52!.off_high_pct)}`}>
                            {s.w52!.off_high_pct.toFixed(1)}%
                          </td>
                          <td className="text-right py-1 px-3">{hl(s.y3)}</td>
                          <td className={`text-right py-1 px-3 ${pctCls(s.y3!.off_high_pct)}`}>
                            {s.y3!.off_high_pct.toFixed(1)}%
                          </td>
                          <td className="text-right py-1 px-3">{hl(s.alltime)}</td>
                          <td className={`text-right py-1 px-3 ${pctCls(s.alltime!.off_high_pct)}`}>
                            {s.alltime!.off_high_pct.toFixed(1)}%
                          </td>
                          <td className="text-right py-1 pl-3 text-muted">{s.first_date}</td>
                        </>
                      ) : (
                        <td colSpan={8} className="py-1 px-3 text-muted">no data</td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="text-[10px] text-muted mt-1">
            ATH/ATL bounded by stored history (see “since”) — not exchange all-time records.
          </p>
        </section>
      )}
    </div>
  );
}
