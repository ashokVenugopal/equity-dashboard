"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  ColorType,
  CrosshairMode,
  CandlestickSeries,
  HistogramSeries,
} from "lightweight-charts";
import { OHLCVTooltip } from "./ChartTooltip";
import type { PriceBar } from "@/lib/api";

interface PriceChartProps {
  data: PriceBar[];
  height?: number;
  showVolume?: boolean;
}

export function PriceChart({ data, height = 350, showVolume = true }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const [chartState, setChartState] = useState<{
    chart: IChartApi;
    candleSeries: ISeriesApi<"Candlestick">;
    volumeSeries: ISeriesApi<"Histogram"> | null;
  } | null>(null);

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
      chart.remove();
    };
  }, [data, height, showVolume]);

  if (data.length === 0) {
    return <div className="text-muted text-xs text-center py-8">No price data available</div>;
  }

  return (
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
  );
}
