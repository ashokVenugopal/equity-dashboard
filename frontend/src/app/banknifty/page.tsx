"use client";

import { useCallback } from "react";
import { getIndexConstituents, getIndexMovers, getIndexTechnicals, getIndexBreadth } from "@/lib/api";
import { IndexPageClient } from "../nifty/IndexPageClient";
import { useCachedData } from "@/lib/cache";
import { PageHeader } from "@/components/shared/PageHeader";

export default function BankNiftyPage() {
  const fetcher = useCallback(async () => {
    const [constData, moverData, techData, breadthData] = await Promise.all([
      getIndexConstituents("nifty-bank"),
      getIndexMovers("nifty-bank", 5),
      getIndexTechnicals("nifty-bank"),
      getIndexBreadth("nifty-bank"),
    ]);
    return { constData, moverData, techData, breadthData };
  }, []);

  const { data, loading, loadedAt, refresh, error } = useCachedData(
    "nifty-bank", fetcher, 5 * 60 * 1000,
  );

  if (error && !data) {
    return (
      <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">
        Failed to load BANKNIFTY data. Ensure the backend is running.
      </div>
    );
  }

  if (!data) {
    return <div className="text-muted text-xs py-8 text-center">Loading...</div>;
  }

  return (
    <>
      <PageHeader title="NIFTY Bank" loadedAt={loadedAt} loading={loading} onRefresh={refresh} />
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
