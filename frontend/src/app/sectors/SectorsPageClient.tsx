"use client";

import { useState } from "react";
import type { SectorPerformanceRow } from "@/lib/api";

const TIMEFRAMES = ["1d", "1w", "2w", "4w", "13w", "26w", "52w", "ytd"];

interface SectorsPageClientProps {
  sectors: SectorPerformanceRow[];
  themes: SectorPerformanceRow[];
}

export function SectorsPageClient({ sectors, themes }: SectorsPageClientProps) {
  const [tab, setTab] = useState<"sectors" | "themes">("sectors");
  const data = tab === "sectors" ? sectors : themes;

  return (
    <div className="space-y-4">
      {/* Tabs */}
      <div className="flex gap-4 border-b border-border pb-2">
        <button
          onClick={() => setTab("sectors")}
          className={`text-xs font-bold uppercase tracking-wider transition-colors ${
            tab === "sectors" ? "text-accent border-b-2 border-accent pb-1" : "text-muted hover:text-foreground"
          }`}
        >
          Sectors
        </button>
        <button
          onClick={() => setTab("themes")}
          className={`text-xs font-bold uppercase tracking-wider transition-colors ${
            tab === "themes" ? "text-accent border-b-2 border-accent pb-1" : "text-muted hover:text-foreground"
          }`}
        >
          Themes
        </button>
      </div>

      {/* Performance table */}
      {data.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse font-mono text-xs">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-3 py-1.5 text-muted font-medium sticky left-0 bg-background min-w-[180px]">
                  {tab === "sectors" ? "Sector" : "Theme"}
                </th>
                {TIMEFRAMES.map((tf) => (
                  <th key={tf} className="text-right px-3 py-1.5 text-muted font-medium whitespace-nowrap">
                    {tf}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr
                  key={row.classification_name}
                  className="border-b border-border/30 hover:bg-surface-hover transition-colors cursor-pointer"
                >
                  <td className="px-3 py-1.5 text-foreground sticky left-0 bg-background">
                    {row.classification_name}
                  </td>
                  {TIMEFRAMES.map((tf) => {
                    const val = row[tf] as number | null | undefined;
                    return (
                      <td
                        key={tf}
                        className={`px-3 py-1.5 text-right tabular-nums whitespace-nowrap ${
                          val == null
                            ? "text-muted"
                            : val >= 0
                            ? "text-positive"
                            : "text-negative"
                        }`}
                      >
                        {val != null ? `${val >= 0 ? "+" : ""}${val.toFixed(2)}%` : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-muted text-xs text-center py-8 border border-border rounded bg-surface">
          No performance data available
        </div>
      )}
    </div>
  );
}
