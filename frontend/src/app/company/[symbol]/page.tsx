import {
  getCompanyMeta,
  getCompanyFinancials,
  getInstrumentPriceHistory,
} from "@/lib/api";
import { CompanyPageClient } from "./CompanyPageClient";

export const dynamic = "force-dynamic";

export default async function CompanyPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;

  try {
    const [meta, financials, priceData] = await Promise.all([
      getCompanyMeta(symbol),
      getCompanyFinancials(symbol),
      getInstrumentPriceHistory(symbol, { limit: 365 }).catch(() => ({ symbol, prices: [], count: 0 })),
    ]);

    return (
      <CompanyPageClient
        meta={meta}
        financials={financials}
        prices={priceData.prices}
      />
    );
  } catch (e) {
    return (
      <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">
        Failed to load company data for {symbol.toUpperCase()}. Ensure the backend is running.
      </div>
    );
  }
}
