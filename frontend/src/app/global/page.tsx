import { getGlobalOverview } from "@/lib/api";
import { DataTable } from "@/components/tables/DataTable";

export const dynamic = "force-dynamic";

const TYPE_LABELS: Record<string, string> = {
  index: "Global Indices",
  commodity: "Commodities",
  forex: "Forex",
  bond: "Bonds",
  crypto: "Crypto",
  adr: "ADRs",
};

const TYPE_ORDER = ["index", "commodity", "forex", "bond", "crypto", "adr"];

export default async function GlobalPage() {
  try {
    const data = await getGlobalOverview();

    return (
      <div className="space-y-6">
        <h1 className="text-xs font-bold text-accent uppercase tracking-wider">
          Global Markets
        </h1>

        {TYPE_ORDER.map((type) => {
          const instruments = data.groups[type];
          if (!instruments || instruments.length === 0) return null;

          return (
            <section key={type} className="border border-border rounded bg-surface p-3">
              <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">
                {TYPE_LABELS[type] || type}
              </h2>
              <DataTable
                columns={[
                  { key: "symbol", label: "Symbol" },
                  { key: "name", label: "Name" },
                  { key: "close", label: "Close", align: "right" },
                  { key: "high", label: "High", align: "right" },
                  { key: "low", label: "Low", align: "right" },
                  { key: "currency", label: "Ccy" },
                  { key: "trade_date", label: "Date" },
                ]}
                rows={instruments}
                compact
              />
            </section>
          );
        })}
      </div>
    );
  } catch (e) {
    return (
      <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">
        Failed to load global data. Ensure the backend is running.
      </div>
    );
  }
}
