import { getIndexConstituents, getIndexMovers, getIndexTechnicals, getIndexBreadth } from "@/lib/api";
import { IndexPageClient } from "../nifty/IndexPageClient";

export const dynamic = "force-dynamic";

export default async function BankNiftyPage() {
  try {
    const [constData, moverData, techData, breadthData] = await Promise.all([
      getIndexConstituents("nifty-bank"),
      getIndexMovers("nifty-bank", 5),
      getIndexTechnicals("nifty-bank"),
      getIndexBreadth("nifty-bank"),
    ]);

    return (
      <IndexPageClient
        indexName={constData.index_name}
        constituents={constData.constituents}
        gainers={moverData.gainers}
        losers={moverData.losers}
        technicals={techData.technicals}
        breadth={breadthData.breadth}
      />
    );
  } catch (e) {
    return (
      <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">
        Failed to load BANKNIFTY data. Ensure the backend is running.
      </div>
    );
  }
}
