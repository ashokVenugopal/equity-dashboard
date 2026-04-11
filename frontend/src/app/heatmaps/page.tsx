"use client";

import { useCallback } from "react";
import { getHeatmap } from "@/lib/api";
import { HeatmapsPageClient } from "./HeatmapsPageClient";
import { PageHeader } from "@/components/shared/PageHeader";
import { useCachedData } from "@/lib/cache";

export default function HeatmapsPage() {
  const fetcher = useCallback(async () => {
    const [nifty50, niftyNext50] = await Promise.all([
      getHeatmap("nifty-50"),
      getHeatmap("nifty-next-50").catch(() => ({ index_name: "NIFTY NEXT 50", blocks: [] })),
    ]);
    return { nifty50, niftyNext50 };
  }, []);

  const { data, loading, loadedAt, refresh, error } = useCachedData(
    "heatmaps", fetcher, 5 * 60 * 1000,
  );

  if (error && !data) {
    return (
      <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">
        Failed to load heatmap data. Ensure the backend is running.
      </div>
    );
  }

  if (!data) {
    return <div className="text-muted text-xs py-8 text-center">Loading...</div>;
  }

  return (
    <>
      <PageHeader title="Heatmaps" loadedAt={loadedAt} loading={loading} onRefresh={refresh} />
      <HeatmapsPageClient nifty50={data.nifty50} niftyNext50={data.niftyNext50} />
    </>
  );
}
