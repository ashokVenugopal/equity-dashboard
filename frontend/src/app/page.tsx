"use client";

import { useCallback } from "react";
import { getMarketOverview, getMarketGlobal, type MarketOverview as MarketOverviewData, type GlobalInstrument } from "@/lib/api";
import { IndexCard } from "@/components/tables/IndexCard";
import { DataTable } from "@/components/tables/DataTable";
import { PageHeader } from "@/components/shared/PageHeader";
import { useCachedData } from "@/lib/cache";

interface OverviewData {
  overview: MarketOverviewData;
  instruments: GlobalInstrument[];
}

export default function MarketOverview() {
  const fetcher = useCallback(async (): Promise<OverviewData> => {
    const [overview, globalData] = await Promise.all([
      getMarketOverview(),
      getMarketGlobal(),
    ]);
    return { overview, instruments: globalData.instruments };
  }, []);

  const { data, loading, loadedAt, refresh, error } = useCachedData<OverviewData>(
    "market-overview", fetcher, 5 * 60 * 1000,
  );

  if (error && !data) {
    return (
      <div className="p-4">
        <PageHeader title="Market Overview" loadedAt={null} />
        <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">
          {error}. Ensure the backend is running on :8000.
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-4">
        <PageHeader title="Market Overview" loadedAt={null} loading />
        <div className="text-muted text-xs py-8 text-center">Loading...</div>
      </div>
    );
  }

  const { overview, instruments } = data;
  const { indices, flows, breadth } = overview;

  return (
    <div className="space-y-6">
      <PageHeader title="Market Overview" loadedAt={loadedAt} loading={loading} onRefresh={refresh} />

      <section>
        <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">Indices</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          {indices.map((idx) => (
            <IndexCard key={idx.symbol} data={idx} />
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="border border-border rounded bg-surface p-3">
          <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">Institutional Flows</h2>
          {flows.length > 0 ? (
            <div className="space-y-2">
              {flows.map((f) => (
                <div key={f.participant_type} className="flex items-center justify-between">
                  <span className="text-xs font-mono">{f.participant_type}</span>
                  <div className="flex items-center gap-4 text-xs font-mono">
                    <span className="text-muted">B: {f.buy_value?.toLocaleString("en-IN")} Cr</span>
                    <span className="text-muted">S: {f.sell_value?.toLocaleString("en-IN")} Cr</span>
                    <span className={`font-bold ${(f.net_value ?? 0) >= 0 ? "text-positive" : "text-negative"}`}>
                      Net: {f.net_value?.toLocaleString("en-IN")} Cr
                    </span>
                  </div>
                </div>
              ))}
              <div className="text-[10px] text-muted mt-1">As of {flows[0]?.flow_date}</div>
            </div>
          ) : (
            <div className="text-muted text-xs">No flow data available</div>
          )}
        </section>

        <section className="border border-border rounded bg-surface p-3">
          <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">Market Breadth</h2>
          {breadth ? (
            <div className="grid grid-cols-2 gap-3 text-xs font-mono">
              <div><span className="text-muted">Advances</span><span className="block text-positive text-lg font-bold">{breadth.advances}</span></div>
              <div><span className="text-muted">Declines</span><span className="block text-negative text-lg font-bold">{breadth.declines}</span></div>
              <div><span className="text-muted">A/D Ratio</span><span className="block text-foreground">{breadth.advance_decline_ratio?.toFixed(2)}</span></div>
              <div><span className="text-muted">Unchanged</span><span className="block text-foreground">{breadth.unchanged}</span></div>
              <div><span className="text-muted">52W Highs</span><span className="block text-positive">{breadth.new_52w_highs}</span></div>
              <div><span className="text-muted">52W Lows</span><span className="block text-negative">{breadth.new_52w_lows}</span></div>
              <div className="col-span-2 text-[10px] text-muted">As of {breadth.trade_date}</div>
            </div>
          ) : (
            <div className="text-muted text-xs">No breadth data available</div>
          )}
        </section>
      </div>

      {instruments.length > 0 && (
        <section>
          <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">Global Markets</h2>
          <DataTable
            columns={[
              { key: "instrument_type", label: "Type" },
              { key: "symbol", label: "Symbol" },
              { key: "name", label: "Name" },
              { key: "close", label: "Close", align: "right" },
              { key: "currency", label: "Ccy" },
              { key: "trade_date", label: "Date" },
            ]}
            rows={instruments}
            symbolKey=""
            compact
          />
        </section>
      )}
    </div>
  );
}
