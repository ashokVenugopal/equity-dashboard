"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createCustomIndex,
  deleteCustomIndex,
  getCustomIndexSeries,
  getCustomIndices,
  getIndexHistoryBasket,
  getIndexHistoryCatalog,
  getIndexHistorySeries,
  getIndexHistoryStats,
  getMacroSeries,
  getVolumeProfile,
  updateCustomIndex,
  type CustomIndex,
  type IndexCatalog,
  type IndexStatsRow,
  type RangeHL,
} from "@/lib/api";
import { MultiLineChart, type ChartLevelLine, type OverlayLine } from "@/components/charts/MultiLineChart";
import { PageHeader } from "@/components/shared/PageHeader";

/*
 * Index History page: overlay up to 4 instruments plus one basket —
 * either a classification group (sector/theme/niche/business group) or
 * a user-defined custom index (editable below the controls). All series
 * rebased to 100. Click the chart twice to measure % change between two
 * dates (anchor A → finish B).
 */

const LINE_COLORS = ["#2196F3", "#FFD700", "#AB47BC", "#26A69A", "#FF7043"];
const BASKET_COLOR = "#FF7043";
const RANGES = ["1y", "3y", "5y", "max"] as const;

const fmt = (v: number | null | undefined, digits = 2) =>
  v != null ? v.toLocaleString("en-IN", { maximumFractionDigits: digits }) : "—";

const pctCls = (v: number) => (v >= 0 ? "text-positive" : "text-negative");

const DEFAULT_SYMBOLS = ["NIFTY50", "BANKNIFTY"];

export default function IndicesPage() {
  const [catalog, setCatalog] = useState<IndexCatalog | null>(null);
  const [customs, setCustoms] = useState<CustomIndex[]>([]);
  const [symbols, setSymbols] = useState<string[]>(DEFAULT_SYMBOLS);
  const [basketKey, setBasketKey] = useState<string>("");
  const [range, setRange] = useState<(typeof RANGES)[number]>("3y");
  const [lines, setLines] = useState<OverlayLine[]>([]);
  const [stats, setStats] = useState<IndexStatsRow[]>([]);
  const [pickerInput, setPickerInput] = useState("");
  const [showPe, setShowPe] = useState(false);
  const [seriesBases, setSeriesBases] = useState<Record<string, number>>({});
  const [levelLines, setLevelLines] = useState<ChartLevelLine[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // ── Manage custom indices ──
  const [manageOpen, setManageOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null); // null = create
  const [editName, setEditName] = useState("");
  const [editSymbols, setEditSymbols] = useState<string[]>([]);
  const [editPicker, setEditPicker] = useState("");
  const [manageError, setManageError] = useState<string | null>(null);

  const refreshCustoms = useCallback(
    () => getCustomIndices().then((d) => setCustoms(d.custom_indices)).catch(() => {}),
    [],
  );

  useEffect(() => {
    getIndexHistoryCatalog().then(setCatalog).catch(() => setCatalog(null));
    refreshCustoms();
  }, [refreshCustoms]);

  const load = useCallback(async () => {
    if (symbols.length === 0 && !basketKey) return;
    setLoading(true);
    setError(null);
    setLevelLines([]);
    try {
      const jobs: Promise<void>[] = [];
      const symbolLines: OverlayLine[] = [];
      let basketLine: OverlayLine | null = null;

      if (symbols.length > 0) {
        jobs.push(
          getIndexHistorySeries(symbols, range).then((d) => {
            const bases: Record<string, number> = {};
            d.series.forEach((s, i) => {
              if (s.base) bases[s.symbol] = s.base;
              symbolLines.push({
                label: s.symbol,
                color: LINE_COLORS[i % LINE_COLORS.length],
                points: s.points,
              });
            });
            setSeriesBases(bases);
          }),
        );
        jobs.push(getIndexHistoryStats(symbols).then((d) => setStats(d.stats)));
      } else {
        setStats([]);
      }

      if (basketKey.startsWith("custom:")) {
        const id = Number(basketKey.slice(7));
        jobs.push(
          getCustomIndexSeries(id, range).then((d) => {
            basketLine = {
              label: `${d.name} (custom, ${d.members_used})`,
              color: BASKET_COLOR,
              points: d.points,
            };
          }),
        );
      } else if (basketKey.startsWith("cls:")) {
        const [, ctype, ...rest] = basketKey.split(":");
        jobs.push(
          getIndexHistoryBasket(ctype, rest.join(":"), range).then((d) => {
            basketLine = {
              label: `${rest.join(":")} (eq-wt, ${d.members_used})`,
              color: BASKET_COLOR,
              points: d.points,
            };
          }),
        );
      }

      let peLine: OverlayLine | null = null;
      if (showPe) {
        const startByRange: Record<string, string> = {
          "1y": new Date(Date.now() - 400 * 864e5).toISOString().slice(0, 10),
          "3y": new Date(Date.now() - 1130 * 864e5).toISOString().slice(0, 10),
          "5y": new Date(Date.now() - 1860 * 864e5).toISOString().slice(0, 10),
          max: "2015-01-01",
        };
        jobs.push(
          getMacroSeries(["NIFTY50_PE"], "none", startByRange[range]).then((d) => {
            const pts = d.series[0]?.points ?? [];
            if (pts.length > 0) {
              peLine = { label: "NIFTY PE (left)", color: "#e8e4dc", points: pts, scale: "left" };
            }
          }),
        );
      }

      await Promise.all(jobs);
      const assembled = basketLine ? [...symbolLines, basketLine] : symbolLines;
      setLines(peLine ? [...assembled, peLine] : assembled);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [symbols, basketKey, range, showPe]);

  useEffect(() => {
    load();
  }, [load]);

  const allSymbols = useMemo(() => {
    if (!catalog) return [];
    return Object.entries(catalog.instruments).flatMap(([type, list]) =>
      list.map((i) => ({ ...i, type })),
    );
  }, [catalog]);

  const stockSymbols = useMemo(
    () => (catalog?.instruments.stock ?? []).map((i) => i.symbol),
    [catalog],
  );

  const onMeasureChange = useCallback(
    async (from: string | null, to: string | null) => {
      if (!from || !to) {
        setLevelLines([]);
        return;
      }
      // Volume profiles only make sense for real instruments (symbol
      // lines) — baskets are synthetic and the PE overlay is a ratio.
      const eligible = symbols.filter((sym) => seriesBases[sym]);
      const results = await Promise.all(
        eligible.map((sym) =>
          getVolumeProfile(sym, from, to).catch(() => null)),
      );
      const lines: ChartLevelLine[] = [];
      results.forEach((vp, i) => {
        const sym = eligible[i];
        const base = seriesBases[sym];
        if (!vp || !vp.available || vp.vah == null || vp.val == null || !base) return;
        const color = LINE_COLORS[symbols.indexOf(sym) % LINE_COLORS.length];
        // Convert absolute price levels into this series' rebased units.
        lines.push(
          { seriesLabel: sym, value: (vp.vah / base) * 100, label: `VAH ${sym} ${vp.vah}`, color },
          { seriesLabel: sym, value: (vp.val / base) * 100, label: `VAL ${sym} ${vp.val}`, color },
        );
      });
      setLevelLines(lines);
    },
    [symbols, seriesBases],
  );

  const addSymbol = (sym: string) => {
    const s = sym.trim().toUpperCase();
    if (!s || symbols.includes(s) || symbols.length >= 4) return;
    if (!allSymbols.some((i) => i.symbol === s)) return;
    setSymbols([...symbols, s]);
    setPickerInput("");
  };

  const startEdit = (ci: CustomIndex | null) => {
    setEditId(ci?.id ?? null);
    setEditName(ci?.name ?? "");
    setEditSymbols(ci?.symbols ?? []);
    setEditPicker("");
    setManageError(null);
    setManageOpen(true);
  };

  const saveCustom = async () => {
    setManageError(null);
    try {
      if (editId == null) {
        const created = await createCustomIndex(editName, editSymbols);
        setBasketKey(`custom:${created.id}`);
      } else {
        await updateCustomIndex(editId, editName, editSymbols);
      }
      await refreshCustoms();
      setEditId(null);
      setEditName("");
      setEditSymbols([]);
      load();
    } catch (e) {
      setManageError(String(e));
    }
  };

  const removeCustom = async (id: number) => {
    await deleteCustomIndex(id).catch(() => {});
    if (basketKey === `custom:${id}`) setBasketKey("");
    refreshCustoms();
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

          <span className="text-muted text-[10px] ml-2">basket:</span>
          <select
            value={basketKey}
            onChange={(e) => setBasketKey(e.target.value)}
            className="bg-background border border-border rounded px-2 py-0.5 text-[11px] font-mono max-w-56"
          >
            <option value="">none</option>
            {customs.length > 0 && (
              <optgroup label="custom indices">
                {customs.map((c) => (
                  <option key={c.id} value={`custom:${c.id}`}>
                    {c.name} ({c.symbols.length})
                  </option>
                ))}
              </optgroup>
            )}
            <optgroup label="classification groups">
              {catalog?.baskets.map((b) => (
                <option
                  key={`${b.classification_type}:${b.classification_name}`}
                  value={`cls:${b.classification_type}:${b.classification_name}`}
                >
                  {b.classification_name} ({b.classification_type}, {b.members})
                </option>
              ))}
            </optgroup>
          </select>
          <button
            className="text-[11px] text-accent border border-border rounded px-2 py-0.5"
            onClick={() => (manageOpen ? setManageOpen(false) : startEdit(null))}
          >
            {manageOpen ? "close manage" : "manage custom"}
          </button>

          <button
            className={`text-[11px] px-2 py-0.5 rounded border ml-2 ${
              showPe ? "border-accent text-accent" : "border-border text-muted"
            }`}
            onClick={() => setShowPe(!showPe)}
            title="Overlay NIFTY 50 PE on the left axis (niftyindices.com, 2015→)"
          >
            NIFTY PE
          </button>

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
          All series rebased to 100 at the start of the window · click the chart twice to
          measure % change between two dates.
        </p>
      </section>

      {/* Manage custom indices */}
      {manageOpen && (
        <section className="border border-border rounded bg-surface p-3 space-y-3">
          <h2 className="text-[11px] text-muted uppercase tracking-wider font-medium">
            Custom indices
          </h2>

          {customs.length > 0 && (
            <ul className="space-y-1">
              {customs.map((c) => (
                <li key={c.id} className="flex items-center gap-2 text-[11px] font-mono">
                  <span className="text-foreground">{c.name}</span>
                  <span className="text-muted truncate max-w-96">{c.symbols.join(", ")}</span>
                  <button className="text-accent border border-border rounded px-1.5"
                          onClick={() => startEdit(c)}>
                    edit
                  </button>
                  <button className="text-negative border border-border rounded px-1.5"
                          onClick={() => removeCustom(c.id)}>
                    delete
                  </button>
                </li>
              ))}
            </ul>
          )}

          {/* Create / edit form */}
          <div className="border-t border-border/50 pt-2 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] text-muted">{editId == null ? "new:" : `editing #${editId}:`}</span>
              <input
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                placeholder="index name…"
                className="bg-background border border-border rounded px-2 py-0.5 text-[11px] font-mono w-48"
              />
              {editSymbols.map((s) => (
                <span key={s} className="flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded border border-border text-foreground">
                  {s}
                  <button className="text-muted hover:text-negative"
                          onClick={() => setEditSymbols(editSymbols.filter((x) => x !== s))}>
                    ×
                  </button>
                </span>
              ))}
              <input
                list="stock-options"
                value={editPicker}
                onChange={(e) => setEditPicker(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key !== "Enter") return;
                  const s = editPicker.trim().toUpperCase();
                  if (s && stockSymbols.includes(s) && !editSymbols.includes(s)) {
                    setEditSymbols([...editSymbols, s]);
                    setEditPicker("");
                  }
                }}
                placeholder="add stock…"
                className="bg-background border border-border rounded px-2 py-0.5 text-[11px] font-mono w-36"
              />
              <datalist id="stock-options">
                {stockSymbols.map((s) => <option key={s} value={s} />)}
              </datalist>
              <button
                className="text-[11px] text-positive border border-border rounded px-2 py-0.5 disabled:opacity-40"
                disabled={!editName.trim() || editSymbols.length < 2}
                onClick={saveCustom}
              >
                {editId == null ? "create" : "save"}
              </button>
              {editId != null && (
                <button className="text-[11px] text-muted border border-border rounded px-2 py-0.5"
                        onClick={() => startEdit(null)}>
                  new instead
                </button>
              )}
            </div>
            <p className="text-[10px] text-muted">2–50 stocks, equal-weighted, rebased to 100.</p>
            {manageError && <p className="text-[10px] text-negative">{manageError}</p>}
          </div>
        </section>
      )}

      {error && (
        <div className="text-negative text-xs border border-negative/30 rounded p-2 bg-negative/5">{error}</div>
      )}

      {/* Overlay chart with measure mode */}
      <section className="border border-border rounded bg-surface p-3">
        <MultiLineChart
          lines={lines}
          height={360}
          levelLines={levelLines}
          onMeasureChange={onMeasureChange}
        />
        {levelLines.length > 0 && (
          <p className="text-[10px] text-muted mt-1">
            VAH/VAL: 70% value area between A and B, from daily bars (volume spread
            across each day&apos;s range) — an approximation, not intraday volume-at-price.
          </p>
        )}
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
