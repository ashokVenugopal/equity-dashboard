"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
  createSeriesMarkers,
} from "lightweight-charts";
import { OHLCVTooltip } from "./ChartTooltip";
import { loadState, saveState } from "@/lib/persist";
import type { PriceBar, VolumeProfile } from "@/lib/api";

/** Volume profile for an A→B window, rendered as horizontal bars anchored
 * at B extending left (session-profile style), plus VAH/POC/VAL lines. */
export interface ChartProfile extends VolumeProfile {
  from: string;
  to: string;
}

interface PriceChartProps {
  data: PriceBar[];
  height?: number;
  showVolume?: boolean;
  /** Volume profile of the measured window (drawn when available). */
  profile?: ChartProfile | null;
  /** Two-click measurement: called with (from, to) when both anchors set. */
  onMeasureChange?: (from: string | null, to: string | null) => void;
  /** When set, A/B anchors and snap grain survive navigation
   * (sessionStorage under this key, e.g. the symbol/slug). */
  persistKey?: string;
}

const VA_FILL = "rgba(33, 150, 243, 0.45)";     // value-area bins
const OUT_FILL = "rgba(141, 163, 90, 0.35)";    // outside value area
const POC_FILL = "rgba(232, 228, 220, 0.60)";   // highest-volume bin
const LINE_COLORS = { vah: "#FFD700", poc: "#e8e4dc", val: "#26A69A" };

const fmtVol = new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 });

/** Large readable rendering of the measured window's profile — every
 * bin at fixed height with price labels, for close inspection. */
function ExpandedProfile({ profile, onClose }: { profile: ChartProfile; onClose: () => void }) {
  const bins = [...(profile.bins ?? [])].reverse();  // highest price on top
  const maxVol = Math.max(...bins.map((b) => b.volume), 1);
  const total = bins.reduce((s, b) => s + b.volume, 0);
  return (
    <div className="border border-border rounded bg-surface p-3 mt-2">
      <div className="flex items-center gap-3 text-[10px] font-mono mb-2">
        <span className="text-accent">volume profile — {profile.from} → {profile.to}</span>
        <span className="text-[#FFD700]">VAH {profile.vah}</span>
        <span className="text-foreground">POC {profile.poc}</span>
        <span className="text-[#26A69A]">VAL {profile.val}</span>
        <span className="text-muted">Σ vol {fmtVol.format(total)}</span>
        <button className="border border-border rounded px-1.5 text-muted hover:text-negative ml-auto"
                onClick={onClose}>
          close
        </button>
      </div>
      <div>
        {bins.map((b, i) => {
          const isPoc = b.volume === maxVol;
          return (
            <div key={i} className="flex items-center gap-2" style={{ height: 9 }}
                 title={`${b.price_low.toFixed(1)} – ${b.price_high.toFixed(1)} · vol ${fmtVol.format(b.volume)}${isPoc ? " · POC" : ""}`}>
              <span className="w-16 shrink-0 text-right text-[8px] text-muted font-mono leading-none">
                {i % 5 === 0 ? b.price_high.toFixed(0) : ""}
              </span>
              <div className="flex-1" style={{ height: 8 }}>
                <div className="h-full rounded-r-[1px]" style={{
                  width: `${Math.max((b.volume / maxVol) * 100, b.volume ? 0.5 : 0)}%`,
                  backgroundColor: isPoc ? POC_FILL : b.in_va ? VA_FILL : OUT_FILL,
                }} />
              </div>
              <span className="w-14 shrink-0 text-[8px] text-muted/70 font-mono leading-none">
                {isPoc ? `POC ${fmtVol.format(b.volume)}` : ""}
              </span>
            </div>
          );
        })}
      </div>
      <p className="text-[9px] text-muted mt-2">
        profile from daily bars (approximation, not intraday volume-at-price) · hover a bar for its price band
      </p>
    </div>
  );
}

/** Snap-mode grains: fixed lookback window in days, anchored at the
 * latest bar. Daily bars, so 1D is not offered. */
const SNAP_GRAINS: { label: string; days: number }[] = [
  { label: "1W", days: 7 },
  { label: "1M", days: 30 },
  { label: "3M", days: 91 },
  { label: "6M", days: 182 },
  { label: "1Y", days: 365 },
];

export function PriceChart({
  data, height = 350, showVolume = true,
  profile = null, onMeasureChange, persistKey,
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const [chartState, setChartState] = useState<{
    chart: IChartApi;
    candleSeries: ISeriesApi<"Candlestick">;
    volumeSeries: ISeriesApi<"Histogram"> | null;
  } | null>(null);
  const [anchors, setAnchors] = useState<string[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [snapGrain, setSnapGrainRaw] = useState<string | null>(null);
  const setSnapGrain = useCallback((g: string | null) => {
    setSnapGrainRaw(g);
    if (persistKey) saveState(`snap:${persistKey}`, g);
  }, [persistKey]);
  useEffect(() => {
    if (persistKey) setSnapGrainRaw(loadState<string | null>(`snap:${persistKey}`, null));
  }, [persistKey]);
  const markersApiRef = useRef<ReturnType<typeof createSeriesMarkers<Time>> | null>(null);
  const activeLevelsRef = useRef<ReturnType<ISeriesApi<"Candlestick">["createPriceLine"]>[]>([]);
  const profileRef = useRef<ChartProfile | null>(profile);
  profileRef.current = profile;
  // Charts already torn down. Effects can fire once more with a stale
  // chartState after data changes — calling into a removed chart throws
  // "Object is disposed", so every imperative call checks this first.
  const deadChartsRef = useRef(new WeakSet<IChartApi>());
  const isDead = useCallback(
    (c: IChartApi | undefined | null) => !c || deadChartsRef.current.has(c), []);

  /** Paint the volume-profile histogram onto the overlay canvas. */
  const drawProfile = useCallback(() => {
    const canvas = overlayRef.current;
    const cs = chartState?.candleSeries;
    const chart = chartState?.chart;
    if (!canvas || !cs || !chart || isDead(chart)) return;
    const p = profileRef.current;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    if (!p || !p.available || !p.bins?.length) return;

    const ts = chart.timeScale();
    const xTo = ts.timeToCoordinate(p.to as Time);
    // If the measured window is off-screen (e.g. snapped to a recent
    // range), keep the profile visible anchored at the right edge — its
    // price levels still matter against the current price.
    const xR = xTo ?? w;
    // Bar length is a fraction of the canvas, not of the A-B span — a
    // narrow window still gets a readable histogram.
    const maxLen = Math.max(70, Math.min(w * 0.22, 260));

    // Adaptive re-binning: merge adjacent bins until each bar is >= ~5px
    // tall at the current zoom, so a narrow A-B price range doesn't
    // collapse into sub-pixel slivers.
    let bins = p.bins;
    const yHi = cs.priceToCoordinate(bins[bins.length - 1].price_high);
    const yLo = cs.priceToCoordinate(bins[0].price_low);
    if (yHi != null && yLo != null) {
      const pxPerBin = Math.abs(yLo - yHi) / bins.length;
      const factor = Math.max(1, Math.ceil(5 / Math.max(pxPerBin, 0.01)));
      if (factor > 1) {
        const merged: typeof bins = [];
        for (let i = 0; i < bins.length; i += factor) {
          const chunk = bins.slice(i, i + factor);
          merged.push({
            price_low: chunk[0].price_low,
            price_high: chunk[chunk.length - 1].price_high,
            volume: chunk.reduce((s, b) => s + b.volume, 0),
            in_va: chunk.some((b) => b.in_va),
          });
        }
        bins = merged;
      }
    }
    const maxVol = Math.max(...bins.map((b) => b.volume), 1);

    for (const bin of bins) {
      if (!bin.volume) continue;
      const yTop = cs.priceToCoordinate(bin.price_high);
      const yBot = cs.priceToCoordinate(bin.price_low);
      if (yTop == null || yBot == null) continue;
      const len = (bin.volume / maxVol) * maxLen;
      ctx.fillStyle = bin.volume === maxVol ? POC_FILL
        : bin.in_va ? VA_FILL : OUT_FILL;
      // Right-anchored, growing left — classic session-profile rendering,
      // with a 1px gap between bars for definition.
      ctx.fillRect(xR - len, yTop, len, Math.max(1, yBot - yTop - 1));
    }
  }, [chartState, isDead]);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#0a0a0a" },
        textColor: "#666",
        fontSize: 11,
        fontFamily: "monospace",
      },
      grid: {
        vertLines: { color: "#1a1a1a" },
        horzLines: { color: "#1a1a1a" },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
      },
      timeScale: {
        borderColor: "#2a2a2a",
        timeVisible: false,
      },
      rightPriceScale: {
        borderColor: "#2a2a2a",
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#00c853",
      downColor: "#ff5252",
      borderUpColor: "#00c853",
      borderDownColor: "#ff5252",
      wickUpColor: "#00c853",
      wickDownColor: "#ff5252",
    });

    candleSeries.setData(
      data.map((d) => ({
        time: d.trade_date,
        open: d.open ?? d.close,
        high: d.high ?? d.close,
        low: d.low ?? d.close,
        close: d.close,
      }))
    );

    let volumeSeries: ISeriesApi<"Histogram"> | null = null;
    if (showVolume) {
      volumeSeries = chart.addSeries(HistogramSeries, {
        color: "#2a2a2a",
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      });
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });
      volumeSeries.setData(
        data
          .filter((d) => d.volume != null)
          .map((d) => ({
            time: d.trade_date,
            value: d.volume!,
            color: d.close >= (d.open ?? d.close) ? "#00c85340" : "#ff525240",
          }))
      );
    }

    chart.timeScale().fitContent();
    markersApiRef.current = createSeriesMarkers(candleSeries, []);
    chart.subscribeClick((param) => {
      if (!param.time) return;
      const iso = String(param.time);
      setAnchors((prev) => (prev.length >= 2 ? [iso] : [...prev, iso]));
    });
    // Restore persisted A/B anchors (dropping any outside this data set)
    const restored = persistKey ? loadState<string[]>(`ab:${persistKey}`, []) : [];
    const dates = new Set(data.map((d) => d.trade_date));
    setAnchors(restored.filter((a) => dates.has(a)).slice(0, 2));

    setChartState({ chart, candleSeries, volumeSeries });

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      setChartState(null);
      markersApiRef.current = null;
      activeLevelsRef.current = [];
      deadChartsRef.current.add(chart);
      chart.remove();
    };
  }, [data, height, showVolume, persistKey]);

  // Snap mode: lock the visible range to a fixed grain anchored at the
  // latest bar, and freeze scroll/scale so screenshots are repeatable.
  useEffect(() => {
    const chart = chartState?.chart;
    if (!chart || isDead(chart) || data.length === 0) return;
    const grain = SNAP_GRAINS.find((g) => g.label === snapGrain);
    try {
      if (grain) {
        const to = data[data.length - 1].trade_date;
        const fromDate = new Date(to);
        fromDate.setDate(fromDate.getDate() - grain.days);
        const firstBar = data[0].trade_date;
        const from = fromDate.toISOString().slice(0, 10);
        chart.applyOptions({ handleScroll: false, handleScale: false });
        chart.timeScale().setVisibleRange({
          from: (from < firstBar ? firstBar : from) as Time,
          to: to as Time,
        });
      } else {
        chart.applyOptions({ handleScroll: true, handleScale: true });
      }
    } catch { /* chart disposed mid-effect — next chartState re-applies */ }
  }, [snapGrain, chartState, data, isDead]);

  // A/B markers + parent notification
  useEffect(() => {
    const markersApi = markersApiRef.current;
    if (markersApi) {
      const sorted = [...anchors].sort();
      const markers: SeriesMarker<Time>[] = sorted.map((iso, i) => ({
        time: iso as Time,
        position: "aboveBar",
        color: i === 0 ? "#FFD700" : "#26A69A",
        shape: "arrowDown",
        text: i === 0 ? "A" : "B",
      }));
      try { markersApi.setMarkers(markers); } catch { /* chart disposed */ }
    }
    if (persistKey) saveState(`ab:${persistKey}`, anchors);
    if (onMeasureChange) {
      if (anchors.length < 2) onMeasureChange(anchors[0] ?? null, null);
      else {
        const [from, to] = [...anchors].sort();
        onMeasureChange(from, to);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anchors]);

  // VAH/POC/VAL price lines + histogram redraw wiring
  useEffect(() => {
    const cs = chartState?.candleSeries;
    const chart = chartState?.chart;
    if (!cs || !chart || isDead(chart)) return;
    for (const handle of activeLevelsRef.current) {
      try { cs.removePriceLine(handle); } catch { /* chart may be gone */ }
    }
    activeLevelsRef.current = [];
    if (profile?.available && profile.vah != null) {
      const lines: [number, string, string][] = [
        [profile.vah, `VAH ${profile.vah}`, LINE_COLORS.vah],
        [profile.poc!, `POC ${profile.poc}`, LINE_COLORS.poc],
        [profile.val!, `VAL ${profile.val}`, LINE_COLORS.val],
      ];
      try {
        for (const [price, title, color] of lines) {
          activeLevelsRef.current.push(cs.createPriceLine({
            price, color, lineWidth: 1, lineStyle: 2,
            axisLabelVisible: true, title,
          }));
        }
      } catch { /* chart disposed mid-effect */ }
    }
    drawProfile();
    const ts = chart.timeScale();
    const onRange = () => drawProfile();
    ts.subscribeVisibleTimeRangeChange(onRange);
    window.addEventListener("resize", onRange);
    return () => {
      try { ts.unsubscribeVisibleTimeRangeChange(onRange); } catch { /* chart gone */ }
      window.removeEventListener("resize", onRange);
    };
  }, [profile, chartState, drawProfile, isDead]);

  if (data.length === 0) {
    return <div className="text-muted text-xs text-center py-8">No price data available</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-end gap-1 mb-1 text-[10px] font-mono">
        <span className={snapGrain ? "text-accent" : "text-muted"}>
          snap{snapGrain ? " · range locked" : ""}
        </span>
        <button
          className={`border rounded px-1.5 py-0.5 ${
            snapGrain === null ? "border-accent text-accent" : "border-border text-muted hover:text-foreground"
          }`}
          onClick={() => setSnapGrain(null)}
        >
          off
        </button>
        {SNAP_GRAINS.map((g) => (
          <button
            key={g.label}
            className={`border rounded px-1.5 py-0.5 ${
              snapGrain === g.label ? "border-accent text-accent" : "border-border text-muted hover:text-foreground"
            }`}
            onClick={() => setSnapGrain(g.label)}
          >
            {g.label}
          </button>
        ))}
      </div>
      <div ref={wrapperRef} className="relative w-full">
        <div ref={containerRef} className="w-full" />
        <canvas
          ref={overlayRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ zIndex: 2 }}
        />
        {chartState && (
          <OHLCVTooltip
            chart={chartState.chart}
            containerRef={wrapperRef}
            candleSeries={chartState.candleSeries}
            volumeSeries={chartState.volumeSeries}
          />
        )}
      </div>
      {onMeasureChange && (
        <div className="text-[10px] text-muted mt-1 min-h-4 font-mono">
          {anchors.length === 0 && "click the chart twice to mark A → B and draw the window's volume profile"}
          {anchors.length === 1 && `anchor A = ${anchors[0]} — click a second point`}
          {anchors.length === 2 && (
            <span className="flex items-center gap-2">
              <button className="border border-border rounded px-1.5 hover:text-negative"
                      onClick={() => setAnchors([])}>
                clear A/B
              </button>
              {profile?.available && (
                <>
                  <button className="border border-border rounded px-1.5 hover:text-accent"
                          onClick={() => setExpanded((e) => !e)}>
                    {expanded ? "collapse profile" : "expand profile"}
                  </button>
                  <span>
                    VAH {profile.vah} · POC {profile.poc} · VAL {profile.val} — profile from
                    daily bars (approximation, not intraday volume-at-price)
                  </span>
                </>
              )}
              {profile && !profile.available && (
                <span className="text-negative/80">{profile.reason}</span>
              )}
            </span>
          )}
        </div>
      )}
      {expanded && profile?.available && profile.bins?.length ? (
        <ExpandedProfile profile={profile} onClose={() => setExpanded(false)} />
      ) : null}
    </div>
  );
}
