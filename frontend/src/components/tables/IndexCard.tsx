import Link from "next/link";
import type { IndexCard as IndexCardData } from "@/lib/api";
import { ChangeIndicator } from "@/components/shared/ChangeIndicator";

interface IndexCardProps {
  data: IndexCardData;
}

/** Map index symbols to their index-view slugs */
function indexSlug(symbol: string): string {
  const map: Record<string, string> = {
    NIFTY50: "nifty-50", BANKNIFTY: "nifty-bank", NIFTYNXT50: "nifty-next-50",
    NIFTYIT: "nifty-it", NIFTYAUTO: "nifty-auto", NIFTYENERGY: "nifty-energy",
    NIFTYPSUBANK: "nifty-psu-bank", NIFTY100: "nifty-100", NIFTY200: "nifty-200",
    NIFTY500: "nifty-500", NIFTYPHARMA: "nifty-pharma", NIFTYMETAL: "nifty-metal",
    NIFTYFMCG: "nifty-fmcg", NIFTYREALTY: "nifty-realty",
    NIFTYFINSERV: "nifty-financial-services", NIFTYPVTBANK: "nifty-private-bank",
  };
  return map[symbol] || symbol.toLowerCase().replace(/\s+/g, "-");
}

export function IndexCard({ data }: IndexCardProps) {
  return (
    <Link href={`/index-view/${indexSlug(data.symbol)}`}>
      <div className="border border-border rounded bg-surface p-3 hover:border-accent/30 transition-colors min-w-[180px] cursor-pointer">
        <div className="flex items-baseline justify-between mb-1">
          <span className="text-xs text-muted">{data.symbol}</span>
          <span className="text-[10px] text-muted">{data.trade_date}</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="text-lg font-mono font-bold text-foreground">
            {data.close?.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="mt-1">
          <ChangeIndicator change={data.change} changePct={data.change_pct} size="sm" />
        </div>
      </div>
    </Link>
  );
}
