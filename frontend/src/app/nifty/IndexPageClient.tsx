"use client";

import { useState } from "react";
import { DataTable } from "@/components/tables/DataTable";
import { PriceChart } from "@/components/charts/PriceChart";
import type { Constituent, Mover, TechnicalRow, PriceBar } from "@/lib/api";
import { getInstrumentPriceHistory } from "@/lib/api";
import { ScrollSection } from "@/components/layout/ScrollSection";
import { useHashObserver } from "@/hooks/useIntersectionObserver";

interface IndexPageClientProps {
  indexName: string;
  constituents: Constituent[];
  gainers: Mover[];
  losers: Mover[];
  technicals: TechnicalRow[];
  breadth: { advances: number; declines: number; unchanged: number; total: number };
}

export function IndexPageClient({
  indexName,
  constituents,
  gainers,
  losers,
  technicals,
  breadth,
}: IndexPageClientProps) {
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [chartData, setChartData] = useState<PriceBar[]>([]);
  const [chartLoading, setChartLoading] = useState(false);

  useHashObserver(["constituents", "movers", "technicals", "chart"]);

  async function handleRowClick(symbol: string) {
    setSelectedSymbol(symbol);
    setChartLoading(true);
    try {
      const data = await getInstrumentPriceHistory(symbol, { limit: 180 });
      setChartData(data.prices);
    } catch {
      setChartData([]);
    } finally {
      setChartLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* Breadth bar */}
      <div className="flex items-center gap-4 text-xs font-mono">
        <span className="text-muted">{indexName}</span>
        <span className="text-positive">▲ {breadth.advances}</span>
        <span className="text-negative">▼ {breadth.declines}</span>
        <span className="text-muted">━ {breadth.unchanged}</span>
        <span className="text-muted">({breadth.total} total)</span>
      </div>

      {/* Movers */}
      <ScrollSection id="movers" title="Top Movers">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="border border-border rounded bg-surface p-3">
            <h3 className="text-xs text-positive font-bold mb-2">GAINERS</h3>
            {gainers.map((m) => (
              <div key={m.symbol} className="flex justify-between py-1 text-xs font-mono">
                <span
                  className="text-foreground cursor-pointer hover:text-accent"
                  onClick={() => handleRowClick(m.symbol)}
                >
                  {m.symbol}
                </span>
                <span className="text-positive">+{m.change_pct?.toFixed(2)}%</span>
              </div>
            ))}
          </div>
          <div className="border border-border rounded bg-surface p-3">
            <h3 className="text-xs text-negative font-bold mb-2">LOSERS</h3>
            {losers.map((m) => (
              <div key={m.symbol} className="flex justify-between py-1 text-xs font-mono">
                <span
                  className="text-foreground cursor-pointer hover:text-accent"
                  onClick={() => handleRowClick(m.symbol)}
                >
                  {m.symbol}
                </span>
                <span className="text-negative">{m.change_pct?.toFixed(2)}%</span>
              </div>
            ))}
          </div>
        </div>
      </ScrollSection>

      {/* Constituents table */}
      <ScrollSection id="constituents" title="Constituents">
        <DataTable
          columns={[
            { key: "symbol", label: "Symbol" },
            { key: "name", label: "Company" },
            { key: "close", label: "Close", align: "right" },
            { key: "change", label: "Chg", align: "right" },
            { key: "change_pct", label: "Chg %", align: "right" },
            { key: "volume", label: "Volume", align: "right" },
          ]}
          rows={constituents}
        />
      </ScrollSection>

      {/* Technicals */}
      <ScrollSection id="technicals" title="Technicals">
        <DataTable
          columns={[
            { key: "symbol", label: "Symbol" },
            { key: "name", label: "Company" },
            { key: "dma_50", label: "DMA 50", align: "right" },
            { key: "dma_200", label: "DMA 200", align: "right" },
            { key: "rsi_14", label: "RSI 14", align: "right" },
            { key: "high_52w", label: "52W High", align: "right" },
            { key: "low_52w", label: "52W Low", align: "right" },
            { key: "daily_change_pct", label: "Day Chg %", align: "right" },
          ]}
          rows={technicals}
        />
      </ScrollSection>

      {/* Chart panel */}
      <ScrollSection id="chart" title={selectedSymbol ? `Chart: ${selectedSymbol}` : "Chart"}>
        {selectedSymbol ? (
          chartLoading ? (
            <div className="text-muted text-xs py-8 text-center">Loading chart...</div>
          ) : (
            <PriceChart data={chartData} height={350} />
          )
        ) : (
          <div className="text-muted text-xs py-8 text-center border border-border rounded bg-surface">
            Click a symbol above to load its chart
          </div>
        )}
      </ScrollSection>
    </div>
  );
}
