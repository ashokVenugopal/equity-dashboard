"use client";

interface TechnicalPanelsProps {
  technicals: Record<string, number | null>;
  supportResistance: Record<string, number | null>;
  currentPrice?: number | null;
}

export function TechnicalPanels({ technicals, supportResistance, currentPrice }: TechnicalPanelsProps) {
  const hasTech = Object.keys(technicals).length > 0;
  const hasSR = Object.keys(supportResistance).length > 0;

  if (!hasTech && !hasSR) return null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      {/* SMA / Technical Indicators */}
      {hasTech && (
        <div className="border border-border rounded bg-surface p-3">
          <div className="text-[10px] text-muted uppercase tracking-wider font-medium mb-2">
            Technical Indicators
          </div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1.5">
            <TechRow label="SMA 30" value={technicals.dma_30} price={currentPrice} />
            <TechRow label="SMA 50" value={technicals.dma_50} price={currentPrice} />
            <TechRow label="SMA 100" value={technicals.dma_100} price={currentPrice} />
            <TechRow label="SMA 200" value={technicals.dma_200} price={currentPrice} />
            <TechRow label="RSI (14)" value={technicals.rsi_14} isRSI />
          </div>
        </div>
      )}

      {/* Support & Resistance */}
      {hasSR && (
        <div className="border border-border rounded bg-surface p-3">
          <div className="text-[10px] text-muted uppercase tracking-wider font-medium mb-2">
            Support & Resistance
          </div>
          <div className="space-y-2">
            {/* Resistance levels */}
            <div className="grid grid-cols-4 gap-2 text-xs font-mono">
              <SRCell label="R3" value={supportResistance.r3} price={currentPrice} type="resistance" />
              <SRCell label="R2" value={supportResistance.r2} price={currentPrice} type="resistance" />
              <SRCell label="R1" value={supportResistance.r1} price={currentPrice} type="resistance" />
              <SRCell label="Pivot" value={supportResistance.pivot} price={currentPrice} type="pivot" />
            </div>
            {/* Visual position bar */}
            {currentPrice && supportResistance.s3 != null && supportResistance.r3 != null && (
              <SRPositionBar
                price={currentPrice}
                s3={supportResistance.s3}
                r3={supportResistance.r3}
                pivot={supportResistance.pivot}
              />
            )}
            {/* Support levels */}
            <div className="grid grid-cols-3 gap-2 text-xs font-mono">
              <SRCell label="S1" value={supportResistance.s1} price={currentPrice} type="support" />
              <SRCell label="S2" value={supportResistance.s2} price={currentPrice} type="support" />
              <SRCell label="S3" value={supportResistance.s3} price={currentPrice} type="support" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TechRow({
  label,
  value,
  price,
  isRSI,
}: {
  label: string;
  value?: number | null;
  price?: number | null;
  isRSI?: boolean;
}) {
  if (value == null) return null;

  let signal: string | null = null;
  let signalClass = "text-muted";

  if (isRSI) {
    if (value > 70) { signal = "Overbought"; signalClass = "text-negative"; }
    else if (value < 30) { signal = "Oversold"; signalClass = "text-positive"; }
    else { signal = "Neutral"; signalClass = "text-muted"; }
  } else if (price != null) {
    if (price > value) { signal = "Above"; signalClass = "text-positive"; }
    else { signal = "Below"; signalClass = "text-negative"; }
  }

  return (
    <div className="flex items-center justify-between text-xs font-mono">
      <span className="text-muted">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-foreground">{value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</span>
        {signal && <span className={`text-[9px] ${signalClass}`}>{signal}</span>}
      </div>
    </div>
  );
}

function SRCell({
  label,
  value,
  price,
  type,
}: {
  label: string;
  value?: number | null;
  price?: number | null;
  type: "resistance" | "support" | "pivot";
}) {
  const diffPct = value && price ? ((value - price) / price * 100) : null;
  const colorClass = type === "resistance" ? "text-positive" : type === "support" ? "text-negative" : "text-accent";

  return (
    <div className="text-center">
      <div className={`text-[9px] uppercase tracking-wider ${colorClass}`}>{label}</div>
      <div className="text-foreground text-xs">
        {value != null ? value.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "—"}
      </div>
      {diffPct != null && (
        <div className="text-[9px] text-muted">
          {diffPct >= 0 ? "+" : ""}{diffPct.toFixed(2)}%
        </div>
      )}
    </div>
  );
}

function SRPositionBar({
  price,
  s3,
  r3,
  pivot,
}: {
  price: number;
  s3: number | null;
  r3: number | null;
  pivot?: number | null;
}) {
  if (s3 == null || r3 == null || r3 === s3) return null;
  const range = r3 - s3;
  const pricePct = Math.max(0, Math.min(100, ((price - s3) / range) * 100));
  const pivotPct = pivot != null ? Math.max(0, Math.min(100, ((pivot - s3) / range) * 100)) : null;

  return (
    <div className="relative h-2 bg-border rounded-full my-1">
      {/* Gradient from red (support) to green (resistance) */}
      <div className="absolute inset-0 rounded-full overflow-hidden">
        <div
          className="h-full"
          style={{
            background: "linear-gradient(to right, var(--negative), var(--border) 50%, var(--positive))",
          }}
        />
      </div>
      {/* Pivot marker */}
      {pivotPct != null && (
        <div
          className="absolute top-0 bottom-0 w-px bg-accent"
          style={{ left: `${pivotPct}%` }}
        />
      )}
      {/* Current price marker */}
      <div
        className="absolute top-[-2px] w-2.5 h-2.5 rounded-full bg-foreground border border-background"
        style={{ left: `${pricePct}%`, transform: "translateX(-50%)" }}
      />
    </div>
  );
}
