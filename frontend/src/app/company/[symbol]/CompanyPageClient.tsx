"use client";

import { useCallback, useEffect, useState } from "react";
import type { CompanyMeta, CompanyFinancials, CompanyRiskReward, FinancialGrain, PriceBar } from "@/lib/api";
import { PriceChart, type ChartProfile } from "@/components/charts/PriceChart";
import { getCompanyFinancials, getVolumeProfile } from "@/lib/api";
import { RiskRewardSection } from "@/components/company/RiskRewardSection";
import { formatCell } from "@/lib/formatters";
import { useHashObserver } from "@/hooks/useIntersectionObserver";
import { usePersistentState } from "@/lib/persist";

interface CompanyPageClientProps {
  meta: CompanyMeta;
  financials: CompanyFinancials;
  prices: PriceBar[];
  riskReward: CompanyRiskReward | null;
}

const SECTION_ORDER = ["profit_loss", "balance_sheet", "cash_flow"];
const SECTION_LABELS: Record<string, string> = {
  risk_reward: "Risk / Reward",
  profit_loss: "Profit & Loss",
  balance_sheet: "Balance Sheet",
  cash_flow: "Cash Flow",
};

const GRAINS: { key: FinancialGrain; label: string }[] = [
  { key: "annual", label: "Annual" },
  { key: "quarterly", label: "Quarterly" },
  { key: "half_yearly", label: "Half-yearly" },
];

type DisplayMode = "values" | "yoy" | "qoq";
const GRAIN_LABEL: Record<string, string> = {
  annual: "annual", quarterly: "quarterly", half_yearly: "half-yearly",
};

/** Period one year before `p` — same month/day, previous year. */
function yearBack(p: string): string {
  return `${Number(p.slice(0, 4)) - 1}${p.slice(4)}`;
}

export function CompanyPageClient({ meta, financials: initial, prices, riskReward }: CompanyPageClientProps) {
  const sectionIds = ["overview", "risk_reward", ...SECTION_ORDER, "chart"];
  const [profile, setProfile] = useState<ChartProfile | null>(null);
  const [grain, setGrain] = usePersistentState<FinancialGrain>("fin:grain", "annual");
  const [mode, setMode] = usePersistentState<DisplayMode>("fin:mode", "values");
  const [financials, setFinancials] = useState<CompanyFinancials>(initial);
  const [loadingFin, setLoadingFin] = useState(false);

  useEffect(() => {
    if (grain === (initial.grain ?? "annual")) {
      setFinancials(initial);
      return;
    }
    setLoadingFin(true);
    getCompanyFinancials(meta.symbol, undefined, grain)
      .then(setFinancials)
      .catch(() => setFinancials(initial))
      .finally(() => setLoadingFin(false));
  }, [grain, meta.symbol, initial]);

  const onMeasureChange = useCallback(
    async (from: string | null, to: string | null) => {
      if (!from || !to) {
        setProfile(null);
        return;
      }
      const vp = await getVolumeProfile(meta.symbol, from, to).catch(() => null);
      setProfile(vp ? { ...vp, from, to } : null);
    },
    [meta.symbol],
  );
  useHashObserver(sectionIds);

  // Grains that exist for at least one of the three statements
  const grainsAvailable = new Set(
    SECTION_ORDER.flatMap((s) => financials.grains_available?.[s] ?? ["annual"]));
  // QoQ only makes sense for sub-annual grains
  const effectiveMode: DisplayMode = mode === "qoq" && grain === "annual" ? "yoy" : mode;

  return (
    <div className="space-y-6">
      {/* Company header */}
      <section id="overview">
        <div className="flex items-baseline gap-3 mb-2">
          <h1 className="text-lg font-bold text-accent">{meta.symbol}</h1>
          <span className="text-sm text-foreground">{meta.name}</span>
        </div>
        <div className="flex gap-2 text-[10px] text-muted">
          <span>ISIN: {meta.isin}</span>
          <span>·</span>
          <span>FY: {meta.fy_end_month === 3 ? "Apr-Mar" : `Jan-Dec (${meta.fy_end_month})`}</span>
          {meta.classifications.map((c, i) => (
            <span key={i}>
              · {c.classification_name}
            </span>
          ))}
        </div>

        {/* Sub-nav */}
        <nav className="flex gap-4 mt-4 border-b border-border pb-2">
          {sectionIds.map((id) => (
            <a
              key={id}
              href={`#${id}`}
              className="text-xs text-muted hover:text-accent transition-colors"
            >
              {SECTION_LABELS[id] || id.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}
            </a>
          ))}
        </nav>
      </section>

      {/* Risk / Reward — valuation altitude + price-change attribution */}
      <RiskRewardSection data={riskReward} />

      {/* Statement controls: period grain + display mode */}
      <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono">
        <span className="text-muted">period:</span>
        {GRAINS.filter((g) => grainsAvailable.has(g.key)).map((g) => (
          <button
            key={g.key}
            onClick={() => setGrain(g.key)}
            className={`border rounded px-2 py-0.5 ${
              grain === g.key ? "border-accent text-accent" : "border-border text-muted hover:text-foreground"
            }`}
          >
            {g.label}
          </button>
        ))}
        <span className="text-muted ml-3">show:</span>
        {([["values", "Values"], ["yoy", "YoY %"], ["qoq", "QoQ %"]] as [DisplayMode, string][]).map(([m, label]) => {
          const disabled = m === "qoq" && grain === "annual";
          return (
            <button
              key={m}
              disabled={disabled}
              title={disabled ? "QoQ needs a sub-annual period view" : undefined}
              onClick={() => setMode(m)}
              className={`border rounded px-2 py-0.5 disabled:opacity-30 ${
                effectiveMode === m ? "border-accent text-accent" : "border-border text-muted hover:text-foreground"
              }`}
            >
              {label}
            </button>
          );
        })}
        {loadingFin && <span className="text-muted ml-2">loading…</span>}
      </div>

      {/* Financial tables — screener.in style: concepts as rows, periods as columns */}
      {SECTION_ORDER.map((sectionKey) => {
        const concepts = financials.sections[sectionKey];
        if (!concepts || concepts.length === 0) return null;
        const secPeriods = (financials.section_periods?.[sectionKey] ?? financials.periods)
          .slice(0, grain === "annual" ? 10 : 12);
        const usedGrain = financials.grain_used?.[sectionKey] ?? financials.grain ?? "annual";
        const fellBack = usedGrain !== (financials.grain ?? "annual");

        return (
          <section key={sectionKey} id={sectionKey} className="snap-section">
            <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">
              {SECTION_LABELS[sectionKey]}
              {fellBack && (
                <span className="ml-2 normal-case font-normal text-[10px] text-muted/80">
                  ({GRAIN_LABEL[usedGrain]} — {GRAIN_LABEL[financials.grain ?? "annual"]} not published)
                </span>
              )}
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse font-mono text-xs">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left px-3 py-1.5 text-muted font-medium sticky left-0 bg-background min-w-[200px]">
                      Particulars
                    </th>
                    {secPeriods.map((p) => (
                      <th key={p} className="text-right px-3 py-1.5 text-muted font-medium whitespace-nowrap">
                        {formatPeriod(p)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {concepts.map((concept) => (
                    <tr
                      key={concept.concept_code}
                      className="border-b border-border/30 hover:bg-surface-hover transition-colors"
                    >
                      <td className="px-3 py-1.5 text-foreground sticky left-0 bg-background">
                        {concept.concept_name}
                      </td>
                      {secPeriods.map((p, idx) => (
                        <StatementCell
                          key={p}
                          concept={concept}
                          period={p}
                          prevPeriod={
                            effectiveMode === "qoq"
                              ? secPeriods[idx + 1] ?? null
                              : effectiveMode === "yoy" && usedGrain !== "annual"
                              ? yearBack(p)
                              : effectiveMode === "yoy"
                              ? secPeriods[idx + 1] ?? null
                              : null
                          }
                          mode={effectiveMode}
                        />
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}

      {/* Price Chart */}
      <section id="chart" className="snap-section">
        <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">
          Price Chart
        </h2>
        <PriceChart
          data={prices}
          height={350}
          profile={profile}
          onMeasureChange={onMeasureChange}
          persistKey={meta.symbol}
        />
      </section>
    </div>
  );
}

function StatementCell({
  concept, period, prevPeriod, mode,
}: {
  concept: { unit: string; values: Record<string, number | null> };
  period: string;
  prevPeriod: string | null;
  mode: DisplayMode;
}) {
  const val = concept.values[period];
  if (mode === "values" || val == null) {
    return (
      <td className="px-3 py-1.5 text-right tabular-nums whitespace-nowrap">
        {val != null ? formatCell(concept.unit === "percent" ? "npm" : "value", val) : "—"}
      </td>
    );
  }
  const prev = prevPeriod != null ? concept.values[prevPeriod] : null;
  if (prev == null || (concept.unit !== "percent" && prev === 0)) {
    return <td className="px-3 py-1.5 text-right tabular-nums whitespace-nowrap text-muted">—</td>;
  }
  // Percent-unit rows (margins, yields): show the delta in points, not a
  // %-of-% which reads wrong.
  const isPct = concept.unit === "percent";
  const delta = isPct ? val - prev : ((val - prev) / Math.abs(prev)) * 100;
  const cls = delta > 0 ? "text-positive" : delta < 0 ? "text-negative" : "text-muted";
  return (
    <td className={`px-3 py-1.5 text-right tabular-nums whitespace-nowrap ${cls}`}
        title={`${formatCell(isPct ? "npm" : "value", prev)} → ${formatCell(isPct ? "npm" : "value", val)}`}>
      {delta > 0 ? "+" : ""}{delta.toFixed(1)}{isPct ? "pp" : "%"}
    </td>
  );
}

function formatPeriod(date: string): string {
  // "2025-03-31" → "Mar 2025"
  try {
    const d = new Date(date + "T00:00:00");
    return d.toLocaleDateString("en-IN", { month: "short", year: "numeric" });
  } catch {
    return date;
  }
}
