"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
} from "lightweight-charts";
import { ChartTooltip, type TooltipSeriesConfig } from "./ChartTooltip";

export interface FlowBarData {
  time: string;
  fii_net: number | null;
  dii_net: number | null;
}

interface FlowBarChartProps {
  data: FlowBarData[];
  height?: number;
}

const FII_COLOR = "#2196F3";
const DII_COLOR = "#AB47BC";
const CUM_COLOR = "#FFD700";

const fmtCr = (v: number) =>
  `${v >= 0 ? "+" : ""}${v.toLocaleString("en-IN", { maximumFractionDigits: 0 })} Cr`;

export function FlowBarChart({ data, height = 220 }: FlowBarChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartWrapperRef = useRef<HTMLDivElement>(null);
  const [chartState, setChartState] = useState<{
    chart: IChartApi;
    configs: TooltipSeriesConfig[];
  } | null>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

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
      timeScale: {
        borderColor: "#2a2a2a",
        timeVisible: false,
        barSpacing: data.length < 20 ? 16 : 8,
      },
      rightPriceScale: {
        borderColor: "#2a2a2a",
      },
      leftPriceScale: {
        borderColor: "#2a2a2a",
        visible: true,
      },
    });

    // FII net bars (blue) — right price scale (shared)
    const fiiSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "price", precision: 0, minMove: 1 },
      priceScaleId: "right",
    });
    fiiSeries.setData(
      data
        .filter((d) => d.fii_net != null)
        .map((d) => ({
          time: d.time,
          value: d.fii_net!,
          color: d.fii_net! >= 0 ? `${FII_COLOR}b0` : `${FII_COLOR}70`,
        }))
    );

    // DII net bars (purple) — SAME right price scale so magnitudes are comparable
    const diiSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "price", precision: 0, minMove: 1 },
      priceScaleId: "right",
    });
    diiSeries.setData(
      data
        .filter((d) => d.dii_net != null)
        .map((d) => ({
          time: d.time,
          value: d.dii_net!,
          color: d.dii_net! >= 0 ? `${DII_COLOR}b0` : `${DII_COLOR}70`,
        }))
    );

    // Cumulative net line (FII + DII running total) — left price scale
    let cumulative = 0;
    const cumData = data
      .filter((d) => d.fii_net != null || d.dii_net != null)
      .map((d) => {
        cumulative += (d.fii_net || 0) + (d.dii_net || 0);
        return { time: d.time, value: Math.round(cumulative) };
      });

    const cumSeries = chart.addSeries(LineSeries, {
      color: CUM_COLOR,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 3,
      priceScaleId: "left",
      priceFormat: { type: "price", precision: 0, minMove: 1 },
    });
    cumSeries.setData(cumData);

    chart.timeScale().fitContent();

    // Tooltip config
    const configs: TooltipSeriesConfig[] = [
      {
        series: fiiSeries as ISeriesApi<never>,
        field: { label: "FII Net", color: FII_COLOR, format: fmtCr },
      },
      {
        series: diiSeries as ISeriesApi<never>,
        field: { label: "DII Net", color: DII_COLOR, format: fmtCr },
      },
      {
        series: cumSeries as ISeriesApi<never>,
        field: { label: "Cumulative", color: CUM_COLOR, format: fmtCr },
      },
    ];

    setChartState({ chart, configs });

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      setChartState(null);
      chart.remove();
    };
  }, [data, height]);

  if (data.length === 0) return null;

  return (
    <div className="border border-border rounded bg-surface">
      <div className="flex items-center justify-between px-3 pt-2 pb-1">
        <span className="text-[10px] text-muted uppercase tracking-wider font-medium">FII / DII Net Activity (Cr)</span>
        <div className="flex gap-3 text-[10px]">
          <span className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: FII_COLOR }} />
            FII Equity
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-2.5 rounded-sm" style={{ background: DII_COLOR }} />
            DII / MF Equity
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2.5 h-0.5 rounded" style={{ background: CUM_COLOR }} />
            Cumulative
          </span>
        </div>
      </div>
      <div ref={chartWrapperRef} className="relative w-full">
        <div ref={containerRef} className="w-full" />
        {chartState && (
          <ChartTooltip
            chart={chartState.chart}
            containerRef={chartWrapperRef}
            seriesConfigs={chartState.configs}
          />
        )}
      </div>
    </div>
  );
}
