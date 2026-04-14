"use client";

import { useDataFreshness } from "@/lib/freshness";
import type { DataFreshness } from "@/lib/api";

interface PageHeaderProps {
  title: string;
  loadedAt: Date | null;
  loading?: boolean;
  onRefresh?: () => void;
  /** Which freshness date to highlight: "market" (default), "fundamental", "flow" */
  dataType?: "market" | "fundamental" | "flow";
}

function timeAgo(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 10) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m ago`;
}

function getFreshnessLabel(freshness: DataFreshness, dataType: string): { label: string; date: string | null } {
  switch (dataType) {
    case "fundamental":
      return {
        label: "Fundamentals as of",
        date: freshness.last_fundamental_ingest
          ? freshness.last_fundamental_ingest.split(" ")[0]
          : null,
      };
    case "flow":
      return { label: "Flows as of", date: freshness.last_flow_date };
    case "market":
    default:
      return { label: "Market data", date: freshness.last_trading_day };
  }
}

export function PageHeader({ title, loadedAt, loading, onRefresh, dataType = "market" }: PageHeaderProps) {
  const freshness = useDataFreshness();
  const freshnessInfo = freshness ? getFreshnessLabel(freshness, dataType) : null;

  return (
    <div className="flex items-center justify-between mb-4">
      <h1 className="text-xs font-bold text-accent uppercase tracking-wider">{title}</h1>
      <div className="flex items-center gap-3 text-[10px] text-muted">
        {freshnessInfo?.date && (
          <span className="border border-border/50 rounded px-1.5 py-0.5">
            {freshnessInfo.label}{" "}
            <span className="text-foreground font-mono">{freshnessInfo.date}</span>
          </span>
        )}
        {loadedAt && (
          <span title={loadedAt.toLocaleString()}>
            Loaded {timeAgo(loadedAt)}
          </span>
        )}
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={loading}
            className="px-2 py-0.5 border border-border rounded hover:border-accent/50 hover:text-accent transition-colors disabled:opacity-30"
          >
            {loading ? "..." : "↻ Refresh"}
          </button>
        )}
      </div>
    </div>
  );
}
