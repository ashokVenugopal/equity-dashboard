"use client";

import { useCallback } from "react";
import { getSectorPerformance } from "@/lib/api";
import { SectorsPageClient } from "./SectorsPageClient";
import { PageHeader } from "@/components/shared/PageHeader";
import { useCachedData } from "@/lib/cache";

export default function SectorsPage() {
  const fetcher = useCallback(async () => {
    const [sectorData, themeData] = await Promise.all([
      getSectorPerformance("sector"),
      getSectorPerformance("theme"),
    ]);
    return { sectors: sectorData.performance, themes: themeData.performance };
  }, []);

  const { data, loading, loadedAt, refresh, error } = useCachedData(
    "sectors", fetcher, 5 * 60 * 1000,
  );

  if (error && !data) {
    return (
      <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">
        Failed to load sector data. Ensure the backend is running.
      </div>
    );
  }

  if (!data) {
    return <div className="text-muted text-xs py-8 text-center">Loading...</div>;
  }

  return (
    <>
      <PageHeader title="Sectors & Themes" loadedAt={loadedAt} loading={loading} onRefresh={refresh} />
      <SectorsPageClient sectors={data.sectors} themes={data.themes} />
    </>
  );
}
