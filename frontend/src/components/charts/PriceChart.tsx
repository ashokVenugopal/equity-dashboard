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

const VA_FILL = "rgba(33, 150, 243, 0.38)";     // value-area bins
const OUT_FILL = "rgba(141, 163, 90, 0.30)";    // outside value area
const LINE_COLORS = { vah: "#FFD700", poc: "#e8e4dc", val: "#26A69A" };

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

  /** Paint the volume-profile histogram onto the overlay canvas. */
  const drawProfile = useCallback(() => {
    const canvas = overlayRef.current;
    const cs = chartState?.candleSeries;
    const chart = chartState?.chart;
    if (!canvas || !cs || !chart) return;
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
    const xFrom = ts.timeToCoordinate(p.from as Time);
    const xTo = ts.timeToCoordinate(p.to as Time);
    if (xFrom == null && xTo == null) return;  // window fully off-screen
    const xR = xTo ?? w;
    // Bar length is a fraction of the canvas, not of the A-B span — a
    // narrow window still gets a readable histogram.
    const maxLen = Math.max(70, Math.min(w * 0.22, 260));
    const maxVol = Math.max(...p.bins.map((b) => b.volume), 1);

    for (const bin of p.bins) {
      if (!bin.volume) continue;
      const yTop = cs.priceToCoordinate(bin.price_high);
      const yBot = cs.priceToCoordinate(bin.price_low);
      if (yTop == null || yBot == null) continue;
      const len = (bin.volume / maxVol) * maxLen;
      ctx.fillStyle = bin.in_va ? VA_FILL : OUT_FILL;
      // Right-anchored at B, growing left — mirrors the classic
      // session-profile rendering.
      ctx.fillRect(xR - len, yTop, len, Math.max(1, yBot - yTop - 0.5));
    }
  }, [chartState]);

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
      chart.remove();
    };
  }, [data, height, showVolume, persistKey]);

  // Snap mode: lock the visible range to a fixed grain anchored at the
  // latest bar, and freeze scroll/scale so screenshots are repeatable.
  useEffect(() => {
    const chart = chartState?.chart;
    if (!chart || data.length === 0) return;
    const grain = SNAP_GRAINS.find((g) => g.label === snapGrain);
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
  }, [snapGrain, chartState, data]);

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
      markersApi.setMarkers(markers);
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
    if (!cs || !chart) return;
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
      for (const [price, title, color] of lines) {
        activeLevelsRef.current.push(cs.createPriceLine({
          price, color, lineWidth: 1, lineStyle: 2,
          axisLabelVisible: true, title,
        }));
      }
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
  }, [profile, chartState, drawProfile]);

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
                <span>
                  VAH {profile.vah} · POC {profile.poc} · VAL {profile.val} — profile from
                  daily bars (approximation, not intraday volume-at-price)
                </span>
              )}
              {profile && !profile.available && (
                <span className="text-negative/80">{profile.reason}</span>
              )}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
