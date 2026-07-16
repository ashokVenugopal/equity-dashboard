"use client";

import type { IndexPerformanceItem } from "@/lib/api";

interface PerformanceCardsProps {
  items: IndexPerformanceItem[];
}

export function PerformanceCards({ items }: PerformanceCardsProps) {
  if (!items.length) return null;

  return (
    <div className="grid grid-cols-4 lg:grid-cols-8 gap-2">
      {items.map((item) => {
        const pct = item.change_pct;
        const isPos = pct != null && pct >= 0;
        const total = item.total || 1;
        const advPct = item.advances != null ? (item.advances / total) * 100 : 50;

        return (
          <div
            key={item.key}
            className="border border-border rounded bg-surface p-2.5"
          >
            <div className="text-[9px] text-muted uppercase tracking-wider mb-1.5">
              {item.label}
            </div>
            <div
              className={`text-sm font-bold font-mono ${
                pct == null
                  ? "text-muted"
                  : isPos
                  ? "text-positive"
                  : "text-negative"
              }`}
            >
              {pct != null
                ? `${isPos ? "+" : ""}${pct.toFixed(2)}%`
                : "—"}
            </div>
            {item.relative_pct != null && (
              <div
                className={`text-[10px] font-mono mt-0.5 ${
                  item.relative_pct >= 0 ? "text-positive/80" : "text-negative/80"
                }`}
                title="vs NIFTY 50 over the same window"
              >
                {item.relative_pct >= 0 ? "+" : ""}{item.relative_pct.toFixed(2)}% vs N50
              </div>
            )}

            {/* Distribution bar */}
            {item.total != null && item.total > 0 && (
              <div className="mt-2">
                <div className="flex h-1.5 rounded-full overflow-hidden bg-border">
                  <div
                    className="bg-positive transition-all"
                    style={{ width: `${advPct}%` }}
                  />
                  <div
                    className="bg-negative transition-all"
                    style={{ width: `${100 - advPct}%` }}
                  />
                </div>
                <div className="flex justify-between text-[8px] text-muted mt-0.5 font-mono">
                  <span className="text-positive">{item.advances}</span>
                  <span className="text-negative">{item.declines}</span>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
