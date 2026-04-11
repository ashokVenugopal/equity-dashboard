import {
  getMarketOverview,
  getMarketGlobal,
  getDerivativesPCR,
  getDerivativesFIIPositioning,
  getDerivativesOIChanges,
} from "@/lib/api";
import { DataTable } from "@/components/tables/DataTable";

export const dynamic = "force-dynamic";

export default async function TradeSetupPage() {
  let flows, breadth, globalInstruments, pcr, fiiPos, oiChanges;
  let error: string | null = null;

  try {
    const [overview, globalData, pcrData, posData, oiData] = await Promise.all([
      getMarketOverview(),
      getMarketGlobal(),
      getDerivativesPCR("NIFTY", 5),
      getDerivativesFIIPositioning(20),
      getDerivativesOIChanges("NIFTY"),
    ]);
    flows = overview.flows;
    breadth = overview.breadth;
    globalInstruments = globalData.instruments;
    pcr = pcrData.pcr_data;
    fiiPos = posData.positioning;
    oiChanges = oiData.oi_data;
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load";
  }

  if (error) {
    return (
      <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">
        {error}. Ensure the backend is running.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xs font-bold text-accent uppercase tracking-wider">
        Pre-Market Trade Setup
      </h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* FII/DII Flows */}
        <section className="border border-border rounded bg-surface p-3">
          <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">
            Cash Market Flows
          </h2>
          {flows && flows.length > 0 ? (
            <div className="space-y-2">
              {flows.map((f) => (
                <div key={f.participant_type} className="flex items-center justify-between text-xs font-mono">
                  <span>{f.participant_type}</span>
                  <div className="flex gap-4">
                    <span className="text-muted">B: {f.buy_value?.toLocaleString()} Cr</span>
                    <span className="text-muted">S: {f.sell_value?.toLocaleString()} Cr</span>
                    <span className={`font-bold ${(f.net_value ?? 0) >= 0 ? "text-positive" : "text-negative"}`}>
                      Net: {f.net_value?.toLocaleString()} Cr
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <span className="text-muted text-xs">No data</span>
          )}
        </section>

        {/* Market Breadth */}
        <section className="border border-border rounded bg-surface p-3">
          <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">
            Market Breadth
          </h2>
          {breadth ? (
            <div className="grid grid-cols-3 gap-2 text-xs font-mono">
              <div>
                <span className="text-muted block">Advances</span>
                <span className="text-positive text-lg font-bold">{breadth.advances}</span>
              </div>
              <div>
                <span className="text-muted block">Declines</span>
                <span className="text-negative text-lg font-bold">{breadth.declines}</span>
              </div>
              <div>
                <span className="text-muted block">A/D Ratio</span>
                <span className="text-foreground text-lg">{breadth.advance_decline_ratio?.toFixed(2)}</span>
              </div>
            </div>
          ) : (
            <span className="text-muted text-xs">No data</span>
          )}
        </section>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* PCR */}
        <section className="border border-border rounded bg-surface p-3">
          <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">
            Nifty Put-Call Ratio
          </h2>
          {pcr && pcr.length > 0 ? (
            <DataTable
              columns={[
                { key: "trade_date", label: "Date" },
                { key: "expiry_date", label: "Expiry" },
                { key: "put_oi", label: "Put OI", align: "right" },
                { key: "call_oi", label: "Call OI", align: "right" },
                { key: "pcr", label: "PCR", align: "right" },
              ]}
              rows={pcr}
              compact
            />
          ) : (
            <span className="text-muted text-xs">No PCR data</span>
          )}
        </section>

        {/* FII Derivatives Positioning */}
        <section className="border border-border rounded bg-surface p-3">
          <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">
            FII Derivatives Positioning
          </h2>
          {fiiPos && fiiPos.length > 0 ? (
            <DataTable
              columns={[
                { key: "trade_date", label: "Date" },
                { key: "instrument_category", label: "Category" },
                { key: "long_contracts", label: "Long", align: "right" },
                { key: "short_contracts", label: "Short", align: "right" },
                { key: "long_pct", label: "Long %", align: "right" },
                { key: "short_pct", label: "Short %", align: "right" },
              ]}
              rows={fiiPos}
              compact
            />
          ) : (
            <span className="text-muted text-xs">No positioning data</span>
          )}
        </section>
      </div>

      {/* Global Cues */}
      {globalInstruments && globalInstruments.length > 0 && (
        <section className="border border-border rounded bg-surface p-3">
          <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">
            Global Market Cues
          </h2>
          <DataTable
            columns={[
              { key: "instrument_type", label: "Type" },
              { key: "symbol", label: "Symbol" },
              { key: "name", label: "Name" },
              { key: "close", label: "Close", align: "right" },
              { key: "currency", label: "Ccy" },
            ]}
            rows={globalInstruments}
            compact
          />
        </section>
      )}

      {/* OI Changes */}
      {oiChanges && oiChanges.length > 0 && (
        <section className="border border-border rounded bg-surface p-3">
          <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">
            Nifty Series OI
          </h2>
          <DataTable
            columns={[
              { key: "trade_date", label: "Date" },
              { key: "expiry_date", label: "Expiry" },
              { key: "futures_oi", label: "Futures OI", align: "right" },
              { key: "options_oi", label: "Options OI", align: "right" },
              { key: "total_oi", label: "Total OI", align: "right" },
              { key: "total_volume", label: "Volume", align: "right" },
            ]}
            rows={oiChanges}
            compact
          />
        </section>
      )}
    </div>
  );
}
