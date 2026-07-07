import {
  getCompanyMeta,
  getCompanyFinancials,
  getCompanyRiskReward,
  getInstrumentPriceHistory,
} from "@/lib/api";
import { CompanyPageClient } from "./CompanyPageClient";

export const dynamic = "force-dynamic";

export default async function CompanyPage({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;

  try {
    const [meta, financials, priceData, riskReward] = await Promise.all([
      getCompanyMeta(symbol),
      getCompanyFinancials(symbol),
      getInstrumentPriceHistory(symbol, { limit: 365 }).catch(() => ({ symbol, prices: [], count: 0 })),
      getCompanyRiskReward(symbol).catch(() => null),
    ]);

    return (
      <CompanyPageClient
        meta={meta}
        financials={financials}
        prices={priceData.prices}
        riskReward={riskReward}
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
