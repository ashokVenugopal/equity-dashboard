"use client";

import { useRouter } from "next/navigation";
import type { HeatmapBlock } from "@/lib/api";

interface TreemapHeatmapProps {
  blocks: HeatmapBlock[];
}

function getColor(changePct: number | null): string {
  if (changePct == null) return "#2a2a2a";
  if (changePct >= 3) return "#00c853";
  if (changePct >= 1.5) return "#00a844";
  if (changePct >= 0.5) return "#008836";
  if (changePct >= 0) return "#1a4a2a";
  if (changePct >= -0.5) return "#4a2a1a";
  if (changePct >= -1.5) return "#883620";
  if (changePct >= -3) return "#a84420";
  return "#ff5252";
}

export function TreemapHeatmap({ blocks }: TreemapHeatmapProps) {
  const router = useRouter();
  const totalCap = blocks.reduce((sum, b) => sum + (b.market_cap ?? 0), 0);
  if (totalCap === 0 || blocks.length === 0) {
    return <div className="text-muted text-xs text-center py-8">No heatmap data</div>;
  }

  return (
    <div className="flex flex-wrap gap-[2px]">
      {blocks.map((block) => {
        const weight = (block.market_cap ?? 0) / totalCap;
        // Min width 60px, scale by weight
        const widthPct = Math.max(weight * 100, 3);
        const bgColor = getColor(block.change_pct);

        return (
          <div
            key={block.symbol}
            className="rounded-sm flex flex-col items-center justify-center p-1 font-mono transition-all hover:brightness-125 cursor-pointer"
            style={{
              backgroundColor: bgColor,
              flexBasis: `${widthPct}%`,
              flexGrow: weight * 10,
              minWidth: "60px",
              minHeight: "50px",
            }}
            title={`${block.name}\n${block.change_pct != null ? `${block.change_pct >= 0 ? "+" : ""}${block.change_pct.toFixed(2)}%` : "—"}\nMCap: ${block.market_cap?.toLocaleString("en-IN")} Cr`}
            onClick={() => router.push(`/company/${block.symbol}`)}
          >
            <span className="text-[10px] text-white/90 font-bold truncate max-w-full">
              {block.symbol}
            </span>
            <span className={`text-[10px] font-bold ${(block.change_pct ?? 0) >= 0 ? "text-white/80" : "text-white/80"}`}>
              {block.change_pct != null
                ? `${block.change_pct >= 0 ? "+" : ""}${block.change_pct.toFixed(1)}%`
                : "—"}
            </span>
          </div>
        );
      })}
    </div>
  );
}
