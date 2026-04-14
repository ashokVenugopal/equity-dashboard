"use client";

import { useEffect, useRef, useCallback, type RefObject } from "react";
import type { IChartApi, ISeriesApi, MouseEventParams, SeriesType } from "lightweight-charts";

export interface TooltipField {
  label: string;
  color?: string;
  format?: (value: number) => string;
}

export interface TooltipSeriesConfig {
  series: ISeriesApi<SeriesType>;
  field: TooltipField;
}

interface ChartTooltipProps {
  chart: IChartApi | null;
  containerRef: RefObject<HTMLDivElement | null>;
  seriesConfigs: TooltipSeriesConfig[];
  /** Optional custom date formatter. Default: YYYY-MM-DD */
  formatDate?: (time: string) => string;
}

const DEFAULT_FORMAT = (v: number) =>
  v.toLocaleString("en-IN", { maximumFractionDigits: 1 });

const DEFAULT_DATE_FORMAT = (t: string) => t;

/**
 * Reusable chart tooltip that subscribes to crosshair moves and renders
 * a positioned HTML overlay. Attach to any lightweight-charts instance.
 *
 * Usage:
 *   <div ref={containerRef} className="relative">
 *     {chart && <ChartTooltip chart={chart} containerRef={containerRef} seriesConfigs={[...]} />}
 *   </div>
 */
export function ChartTooltip({
  chart,
  containerRef,
  seriesConfigs,
  formatDate = DEFAULT_DATE_FORMAT,
}: ChartTooltipProps) {
  const tooltipRef = useRef<HTMLDivElement>(null);

  const handleCrosshairMove = useCallback(
    (param: MouseEventParams) => {
      const tooltip = tooltipRef.current;
      const container = containerRef.current;
      if (!tooltip || !container) return;

      if (
        !param.time ||
        !param.point ||
        param.point.x < 0 ||
        param.point.y < 0
      ) {
        tooltip.style.opacity = "0";
        return;
      }

      // Build tooltip content
      const date = formatDate(String(param.time));
      let hasData = false;
      let html = `<div class="text-muted text-[9px] mb-1">${date}</div>`;

      for (const config of seriesConfigs) {
        const data = param.seriesData.get(config.series);
        if (!data) continue;

        // Histogram/Line series store value in 'value', Candlestick in 'close'
        const value =
          "value" in data
            ? (data as { value: number }).value
            : "close" in data
            ? (data as { close: number }).close
            : null;

        if (value == null) continue;
        hasData = true;

        const fmt = config.field.format || DEFAULT_FORMAT;
        const colorDot = config.field.color
          ? `<span class="inline-block w-1.5 h-1.5 rounded-full mr-1" style="background:${config.field.color}"></span>`
          : "";

        html += `<div class="flex items-center justify-between gap-3 text-[10px]">
          <span class="text-muted">${colorDot}${config.field.label}</span>
          <span class="font-bold tabular-nums ${value >= 0 ? "text-positive" : "text-negative"}">${fmt(value)}</span>
        </div>`;
      }

      if (!hasData) {
        tooltip.style.opacity = "0";
        return;
      }

      tooltip.innerHTML = html;
      tooltip.style.opacity = "1";

      // Position: prefer right of crosshair, flip to left if near edge
      const containerRect = container.getBoundingClientRect();
      const tooltipWidth = tooltip.offsetWidth;
      const tooltipHeight = tooltip.offsetHeight;
      const margin = 12;

      let left = param.point.x + margin;
      if (left + tooltipWidth > containerRect.width) {
        left = param.point.x - tooltipWidth - margin;
      }

      let top = param.point.y - tooltipHeight / 2;
      top = Math.max(0, Math.min(top, containerRect.height - tooltipHeight));

      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    },
    [seriesConfigs, containerRef, formatDate]
  );

  useEffect(() => {
    if (!chart) return;
    chart.subscribeCrosshairMove(handleCrosshairMove);
    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
    };
  }, [chart, handleCrosshairMove]);

  return (
    <div
      ref={tooltipRef}
      className="absolute z-10 pointer-events-none bg-surface/95 border border-border rounded px-2 py-1.5 backdrop-blur-sm shadow-lg"
      style={{
        opacity: 0,
        transition: "opacity 120ms ease-out",
        left: 0,
        top: 0,
      }}
    />
  );
}

/**
 * OHLCV tooltip variant — extracts open/high/low/close/volume from candlestick + volume series.
 */
export interface OHLCVTooltipProps {
  chart: IChartApi | null;
  containerRef: RefObject<HTMLDivElement | null>;
  candleSeries: ISeriesApi<"Candlestick"> | null;
  volumeSeries?: ISeriesApi<"Histogram"> | null;
  formatDate?: (time: string) => string;
}

export function OHLCVTooltip({
  chart,
  containerRef,
  candleSeries,
  volumeSeries,
  formatDate = DEFAULT_DATE_FORMAT,
}: OHLCVTooltipProps) {
  const tooltipRef = useRef<HTMLDivElement>(null);

  const handleCrosshairMove = useCallback(
    (param: MouseEventParams) => {
      const tooltip = tooltipRef.current;
      const container = containerRef.current;
      if (!tooltip || !container) return;

      if (!param.time || !param.point || param.point.x < 0 || param.point.y < 0) {
        tooltip.style.opacity = "0";
        return;
      }

      const candleData = candleSeries ? param.seriesData.get(candleSeries) : null;
      if (!candleData || !("close" in candleData)) {
        tooltip.style.opacity = "0";
        return;
      }

      const cd = candleData as unknown as { open: number; high: number; low: number; close: number };
      const date = formatDate(String(param.time));
      const change = cd.close - cd.open;
      const changePct = cd.open !== 0 ? (change / cd.open) * 100 : 0;
      const isUp = change >= 0;

      const fmt = (v: number) => v.toLocaleString("en-IN", { maximumFractionDigits: 2 });
      const fmtVol = (v: number) => {
        if (v >= 1e7) return `${(v / 1e7).toFixed(2)} Cr`;
        if (v >= 1e5) return `${(v / 1e5).toFixed(2)} L`;
        return v.toLocaleString("en-IN");
      };

      let volHtml = "";
      if (volumeSeries) {
        const volData = param.seriesData.get(volumeSeries);
        if (volData && "value" in volData) {
          volHtml = `<div class="flex justify-between gap-3 text-[10px]">
            <span class="text-muted">Vol</span>
            <span class="tabular-nums">${fmtVol((volData as { value: number }).value)}</span>
          </div>`;
        }
      }

      tooltip.innerHTML = `
        <div class="text-muted text-[9px] mb-1">${date}</div>
        <div class="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[10px] tabular-nums">
          <span class="text-muted">O</span><span class="text-right">${fmt(cd.open)}</span>
          <span class="text-muted">H</span><span class="text-right">${fmt(cd.high)}</span>
          <span class="text-muted">L</span><span class="text-right">${fmt(cd.low)}</span>
          <span class="text-muted">C</span><span class="text-right">${fmt(cd.close)}</span>
        </div>
        <div class="mt-1 pt-1 border-t border-border/50 text-[10px] font-bold tabular-nums ${isUp ? "text-positive" : "text-negative"}">
          ${isUp ? "+" : ""}${fmt(change)} (${isUp ? "+" : ""}${changePct.toFixed(2)}%)
        </div>
        ${volHtml}
      `;
      tooltip.style.opacity = "1";

      // Position
      const tooltipWidth = tooltip.offsetWidth;
      const tooltipHeight = tooltip.offsetHeight;
      const margin = 12;
      const containerWidth = container.getBoundingClientRect().width;
      const containerHeight = container.getBoundingClientRect().height;

      let left = param.point.x + margin;
      if (left + tooltipWidth > containerWidth) left = param.point.x - tooltipWidth - margin;

      let top = param.point.y - tooltipHeight / 2;
      top = Math.max(0, Math.min(top, containerHeight - tooltipHeight));

      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    },
    [candleSeries, volumeSeries, containerRef, formatDate]
  );

  useEffect(() => {
    if (!chart) return;
    chart.subscribeCrosshairMove(handleCrosshairMove);
    return () => { chart.unsubscribeCrosshairMove(handleCrosshairMove); };
  }, [chart, handleCrosshairMove]);

  return (
    <div
      ref={tooltipRef}
      className="absolute z-10 pointer-events-none bg-surface/95 border border-border rounded px-2 py-1.5 backdrop-blur-sm shadow-lg"
      style={{
        opacity: 0,
        transition: "opacity 120ms ease-out",
        left: 0,
        top: 0,
      }}
    />
  );
}
