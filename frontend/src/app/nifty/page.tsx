"use client";

import { useCallback } from "react";
import { getIndexConstituents, getIndexMovers, getIndexTechnicals, getIndexBreadth } from "@/lib/api";
import { IndexPageClient } from "./IndexPageClient";
import { useCachedData } from "@/lib/cache";
import { PageHeader } from "@/components/shared/PageHeader";

export default function NiftyPage() {
  const fetcher = useCallback(async () => {
    const [constData, moverData, techData, breadthData] = await Promise.all([
      getIndexConstituents("nifty-50"),
      getIndexMovers("nifty-50", 5),
      getIndexTechnicals("nifty-50"),
      getIndexBreadth("nifty-50"),
    ]);
    return { constData, moverData, techData, breadthData };
  }, []);

  const { data, loading, loadedAt, refresh, error } = useCachedData(
    "nifty-50", fetcher, 5 * 60 * 1000,
  );

  if (error && !data) {
    return (
      <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">
        Failed to load NIFTY data. Ensure the backend is running.
      </div>
    );
  }

  if (!data) {
    return <div className="text-muted text-xs py-8 text-center">Loading...</div>;
  }

  return (
    <>
      <PageHeader title="NIFTY 50" loadedAt={loadedAt} loading={loading} onRefresh={refresh} />
      <IndexPageClient
        indexName={data.constData.index_name}
        constituents={data.constData.constituents}
        gainers={data.moverData.gainers}
        losers={data.moverData.losers}
        technicals={data.techData.technicals}
        breadth={data.breadthData.breadth}
      />
    </>
  );
}
