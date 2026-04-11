"use client";

import { useState } from "react";
import type { HeatmapBlock } from "@/lib/api";
import { TreemapHeatmap } from "@/components/heatmap/TreemapHeatmap";

interface HeatmapsPageClientProps {
  nifty50: { index_name: string; blocks: HeatmapBlock[] };
  niftyNext50: { index_name: string; blocks: HeatmapBlock[] };
}

export function HeatmapsPageClient({ nifty50, niftyNext50 }: HeatmapsPageClientProps) {
  const [tab, setTab] = useState<"nifty50" | "next50">("nifty50");
  const data = tab === "nifty50" ? nifty50 : niftyNext50;

  return (
    <div className="space-y-4">
      <div className="flex gap-4 border-b border-border pb-2">
        <button
          onClick={() => setTab("nifty50")}
          className={`text-xs font-bold uppercase tracking-wider transition-colors ${
            tab === "nifty50" ? "text-accent border-b-2 border-accent pb-1" : "text-muted hover:text-foreground"
          }`}
        >
          NIFTY 50
        </button>
        <button
          onClick={() => setTab("next50")}
          className={`text-xs font-bold uppercase tracking-wider transition-colors ${
            tab === "next50" ? "text-accent border-b-2 border-accent pb-1" : "text-muted hover:text-foreground"
          }`}
        >
          NIFTY Next 50
        </button>
      </div>

      <div className="text-[10px] text-muted mb-2">
        Block size ∝ market cap · Color ∝ daily change
      </div>

      <TreemapHeatmap blocks={data.blocks} />
    </div>
  );
}
