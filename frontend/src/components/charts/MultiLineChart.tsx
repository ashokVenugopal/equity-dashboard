"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  ColorType,
  CrosshairMode,
  LineSeries,
} from "lightweight-charts";
import { ChartTooltip, type TooltipSeriesConfig } from "./ChartTooltip";

export interface OverlayLine {
  label: string;
  color: string;
  points: { time: string; value: number }[];
  /** "left" puts the line on the left price scale (e.g. a PE overlay). */
  scale?: "right" | "left";
}

const fmt2 = (v: number) => v.toLocaleString("en-IN", { maximumFractionDigits: 2 });

/** Multi-series line overlay (normalized index comparison, PE overlays…). */
export function MultiLineChart({ lines, height = 320 }: { lines: OverlayLine[]; height?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [chartState, setChartState] = useState<{
    chart: IChartApi;
    configs: TooltipSeriesConfig[];
  } | null>(null);

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
      configs.push({
        series: s as ISeriesApi<never>,
        field: { label: line.label, color: line.color, format: fmt2 },
      });
    }
    chart.timeScale().fitContent();
    setChartState({ chart, configs });

    const onResize = () => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      setChartState(null);
      chart.remove();
    };
  }, [lines, height]);

  if (lines.length === 0) return null;

  return (
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
  );
}
