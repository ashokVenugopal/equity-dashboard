import { getHeatmap } from "@/lib/api";
import { HeatmapsPageClient } from "./HeatmapsPageClient";

export const dynamic = "force-dynamic";

export default async function HeatmapsPage() {
  try {
    const [nifty50, niftyNext50] = await Promise.all([
      getHeatmap("nifty-50"),
      getHeatmap("nifty-next-50").catch(() => ({ index_name: "NIFTY Next 50", blocks: [] })),
    ]);

    return <HeatmapsPageClient nifty50={nifty50} niftyNext50={niftyNext50} />;
  } catch (e) {
    return (
      <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">
        Failed to load heatmap data. Ensure the backend is running.
      </div>
    );
  }
}
