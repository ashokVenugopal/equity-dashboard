import { getIndexConstituents, getIndexMovers, getIndexTechnicals, getIndexBreadth } from "@/lib/api";
import { IndexPageClient } from "./IndexPageClient";

export const dynamic = "force-dynamic";

export default async function NiftyPage() {
  try {
    const [constData, moverData, techData, breadthData] = await Promise.all([
      getIndexConstituents("nifty-50"),
      getIndexMovers("nifty-50", 5),
      getIndexTechnicals("nifty-50"),
      getIndexBreadth("nifty-50"),
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
        Failed to load NIFTY data. Ensure the backend is running.
      </div>
    );
  }
}
