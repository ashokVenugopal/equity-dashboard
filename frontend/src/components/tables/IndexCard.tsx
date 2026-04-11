import type { IndexCard as IndexCardData } from "@/lib/api";
import { ChangeIndicator } from "@/components/shared/ChangeIndicator";

interface IndexCardProps {
  data: IndexCardData;
}

export function IndexCard({ data }: IndexCardProps) {
  const isPositive = (data.change ?? 0) >= 0;

  return (
    <div className="border border-border rounded bg-surface p-3 hover:border-accent/30 transition-colors min-w-[180px]">
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
  );
}
