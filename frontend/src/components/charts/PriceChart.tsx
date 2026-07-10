"use client";

import { useEffect, useRef, useState } from "react";
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
import type { PriceBar } from "@/lib/api";

export interface PriceLevelLine {
  value: number;
  label: string;
  color: string;
}

interface PriceChartProps {
  data: PriceBar[];
  height?: number;
  showVolume?: boolean;
  /** Horizontal dashed levels (e.g. VAH/VAL/POC for the A→B window). */
  levelLines?: PriceLevelLine[];
  /** Two-click measurement: called with (from, to) when both anchors set. */
  onMeasureChange?: (from: string | null, to: string | null) => void;
}

export function PriceChart({
  data, height = 350, showVolume = true,
  levelLines = [], onMeasureChange,
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [chartState, setChartState] = useState<{
    chart: IChartApi;
    candleSeries: ISeriesApi<"Candlestick">;
    volumeSeries: ISeriesApi<"Histogram"> | null;
  } | null>(null);
  const [anchors, setAnchors] = useState<string[]>([]);
  const markersApiRef = useRef<ReturnType<typeof createSeriesMarkers<Time>> | null>(null);
  const activeLevelsRef = useRef<ReturnType<ISeriesApi<"Candlestick">["createPriceLine"]>[]>([]);

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
    setAnchors([]);

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
  }, [data, height, showVolume]);

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
    if (onMeasureChange) {
      if (anchors.length < 2) onMeasureChange(anchors[0] ?? null, null);
      else {
        const [from, to] = [...anchors].sort();
        onMeasureChange(from, to);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anchors]);

  // Level lines (VAH/VAL/POC)
  useEffect(() => {
    const cs = chartState?.candleSeries;
    if (!cs) return;
    for (const handle of activeLevelsRef.current) {
      try { cs.removePriceLine(handle); } catch { /* chart may be gone */ }
    }
    activeLevelsRef.current = [];
    for (const ll of levelLines) {
      activeLevelsRef.current.push(cs.createPriceLine({
        price: ll.value,
        color: ll.color,
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: ll.label,
      }));
    }
  }, [levelLines, chartState]);

  if (data.length === 0) {
    return <div className="text-muted text-xs text-center py-8">No price data available</div>;
  }

  return (
    <div>
      <div ref={wrapperRef} className="relative w-full">
        <div ref={containerRef} className="w-full" />
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
          {anchors.length === 0 && "click the chart twice to mark A → B and draw the window's VAH/VAL"}
          {anchors.length === 1 && `anchor A = ${anchors[0]} — click a second point`}
          {anchors.length === 2 && (
            <button className="border border-border rounded px-1.5 hover:text-negative"
                    onClick={() => setAnchors([])}>
              clear A/B
            </button>
          )}
        </div>
      )}
    </div>
  );
}
