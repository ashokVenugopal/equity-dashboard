"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
  ColorType,
  CrosshairMode,
  LineSeries,
  createSeriesMarkers,
} from "lightweight-charts";
import { ChartTooltip, type TooltipSeriesConfig } from "./ChartTooltip";

export interface OverlayLine {
  label: string;
  color: string;
  points: { time: string; value: number }[];
  /** "left" puts the line on the left price scale (e.g. a PE overlay). */
  scale?: "right" | "left";
}

/** Horizontal level drawn on a specific series (e.g. VAH/VAL). */
export interface ChartLevelLine {
  seriesLabel: string;
  value: number;
  label: string;
  color: string;
}

const fmt2 = (v: number) => v.toLocaleString("en-IN", { maximumFractionDigits: 2 });

interface MeasureResult {
  from: string;
  to: string;
  perLine: { label: string; color: string; changePct: number | null }[];
}

/** Nearest value at or before an ISO date (points sorted ascending). */
function valueAsOf(points: { time: string; value: number }[], iso: string): number | null {
  let best: number | null = null;
  for (const p of points) {
    if (p.time > iso) break;
    best = p.value;
  }
  return best;
}

/**
 * Multi-series line overlay (normalized index comparison, PE overlays…).
 *
 * Measure mode: click once to set the anchor, click again to set the
 * finish — the panel below reports each series' % change between the
 * two dates (chronologically ordered, whichever order you click).
 */
export function MultiLineChart({
  lines,
  height = 320,
  levelLines = [],
  onMeasureChange,
}: {
  lines: OverlayLine[];
  height?: number;
  levelLines?: ChartLevelLine[];
  onMeasureChange?: (from: string | null, to: string | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [chartState, setChartState] = useState<{
    chart: IChartApi;
    configs: TooltipSeriesConfig[];
  } | null>(null);
  const [anchors, setAnchors] = useState<string[]>([]);
  const linesRef = useRef(lines);
  linesRef.current = lines;

  const markerTargetRef = useRef<ISeriesApi<"Line"> | null>(null);
  const seriesByLabelRef = useRef<Map<string, ISeriesApi<"Line">>>(new Map());
  const activeLevelLinesRef = useRef<{ series: ISeriesApi<"Line">; handle: ReturnType<ISeriesApi<"Line">["createPriceLine"]> }[]>([]);
  const markersApiRef = useRef<ReturnType<typeof createSeriesMarkers<Time>> | null>(null);

  useEffect(() => {
    if (!containerRef.current || lines.length === 0) return;
    const hasLeft = lines.some((l) => l.scale === "left");

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#0a0a0a" },
        textColor: "#666",
        fontSize: 10,
        fontFamily: "monospace",
      },
      grid: {
        vertLines: { color: "#1a1a1a" },
        horzLines: { color: "#1a1a1a" },
      },
      crosshair: { mode: CrosshairMode.Magnet },
      timeScale: { borderColor: "#2a2a2a", timeVisible: false },
      rightPriceScale: { borderColor: "#2a2a2a" },
      leftPriceScale: { borderColor: "#2a2a2a", visible: hasLeft },
    });

    const configs: TooltipSeriesConfig[] = [];
    let firstSeries: ISeriesApi<"Line"> | null = null;
    for (const line of lines) {
      const s = chart.addSeries(LineSeries, {
        color: line.color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 3,
        priceScaleId: line.scale === "left" ? "left" : "right",
        priceFormat: { type: "price", precision: 2, minMove: 0.01 },
      });
      s.setData(line.points);
      seriesByLabelRef.current.set(line.label, s);
      if (!firstSeries) firstSeries = s;
      configs.push({
        series: s as ISeriesApi<never>,
        field: { label: line.label, color: line.color, format: fmt2 },
      });
    }
    markerTargetRef.current = firstSeries;
    markersApiRef.current = firstSeries ? createSeriesMarkers(firstSeries, []) : null;

    // Measure mode: two clicks define anchor → finish.
    chart.subscribeClick((param) => {
      if (!param.time) return;
      const iso = String(param.time);
      setAnchors((prev) => (prev.length >= 2 ? [iso] : [...prev, iso]));
    });

    chart.timeScale().fitContent();
    setChartState({ chart, configs });
    setAnchors([]);

    const onResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      setChartState(null);
      markerTargetRef.current = null;
      markersApiRef.current = null;
      seriesByLabelRef.current = new Map();
      activeLevelLinesRef.current = [];
      chart.remove();
    };
  }, [lines, height]);

  // Render A/B markers whenever anchors change.
  useEffect(() => {
    const markersApi = markersApiRef.current;
    if (!markersApi) return;
    const sorted = [...anchors].sort();
    const markers: SeriesMarker<Time>[] = sorted.map((iso, i) => ({
      time: iso as Time,
      position: "aboveBar",
      color: i === 0 ? "#FFD700" : "#26A69A",
      shape: "arrowDown",
      text: i === 0 ? "A" : "B",
    }));
    markersApi.setMarkers(markers);
  }, [anchors]);

  // Draw/refresh horizontal level lines (VAH/VAL etc.) on their series.
  useEffect(() => {
    for (const { series, handle } of activeLevelLinesRef.current) {
      try { series.removePriceLine(handle); } catch { /* series may be gone */ }
    }
    activeLevelLinesRef.current = [];
    for (const ll of levelLines) {
      const series = seriesByLabelRef.current.get(ll.seriesLabel);
      if (!series) continue;
      const handle = series.createPriceLine({
        price: ll.value,
        color: ll.color,
        lineWidth: 1,
        lineStyle: 2, // dashed
        axisLabelVisible: true,
        title: ll.label,
      });
      activeLevelLinesRef.current.push({ series, handle });
    }
  }, [levelLines, chartState]);

  // Notify the parent when the measurement window changes.
  useEffect(() => {
    if (!onMeasureChange) return;
    if (anchors.length < 2) {
      onMeasureChange(anchors[0] ?? null, null);
      return;
    }
    const [from, to] = [...anchors].sort();
    onMeasureChange(from, to);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anchors]);

  const measure: MeasureResult | null = useMemo(() => {
    if (anchors.length < 2) return null;
    const [from, to] = [...anchors].sort();
    if (from === to) return null;
    return {
      from,
      to,
      perLine: linesRef.current.map((l) => {
        const v0 = valueAsOf(l.points, from);
        const v1 = valueAsOf(l.points, to);
        return {
          label: l.label,
          color: l.color,
          changePct: v0 && v1 ? (v1 / v0 - 1) * 100 : null,
        };
      }),
    };
  }, [anchors]);

  if (lines.length === 0) return null;

  return (
    <div>
      <div ref={wrapperRef} className="relative w-full">
        <div ref={containerRef} className="w-full" />
        {chartState && (
          <ChartTooltip
            chart={chartState.chart}
            containerRef={wrapperRef}
            seriesConfigs={chartState.configs}
          />
        )}
      </div>

      {/* Measurement panel */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-1 min-h-6 text-[11px] font-mono">
        {measure ? (
          <>
            <span className="text-muted">
              {measure.from} → {measure.to}:
            </span>
            {measure.perLine.map((r) => (
              <span key={r.label} style={{ color: r.color }}>
                {r.label}{" "}
                {r.changePct == null ? (
                  <span className="text-muted">n/a</span>
                ) : (
                  <span className={r.changePct >= 0 ? "text-positive" : "text-negative"}>
                    {r.changePct >= 0 ? "+" : ""}
                    {r.changePct.toFixed(2)}%
                  </span>
                )}
              </span>
            ))}
            <button
              className="text-muted border border-border rounded px-1.5 hover:text-negative"
              onClick={() => setAnchors([])}
            >
              clear
            </button>
          </>
        ) : (
          <span className="text-muted/60">
            {anchors.length === 1
              ? `anchor A = ${anchors[0]} — click a second point to measure`
              : "click the chart twice to measure % change between two dates"}
          </span>
        )}
      </div>
    </div>
  );
}
