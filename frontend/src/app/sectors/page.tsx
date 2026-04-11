import { getSectorPerformance } from "@/lib/api";
import { SectorsPageClient } from "./SectorsPageClient";

export const dynamic = "force-dynamic";

export default async function SectorsPage() {
  try {
    const [sectorData, themeData] = await Promise.all([
      getSectorPerformance("sector"),
      getSectorPerformance("theme"),
    ]);

    return (
      <SectorsPageClient
        sectors={sectorData.performance}
        themes={themeData.performance}
      />
    );
  } catch (e) {
    return (
      <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">
        Failed to load sector data. Ensure the backend is running.
      </div>
    );
  }
}
