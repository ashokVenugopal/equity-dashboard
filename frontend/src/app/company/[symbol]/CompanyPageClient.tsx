"use client";

import { useEffect } from "react";
import type { CompanyMeta, CompanyFinancials, PriceBar } from "@/lib/api";
import { PriceChart } from "@/components/charts/PriceChart";
import { formatCell } from "@/lib/formatters";
import { useHashObserver } from "@/hooks/useIntersectionObserver";

interface CompanyPageClientProps {
  meta: CompanyMeta;
  financials: CompanyFinancials;
  prices: PriceBar[];
}

const SECTION_ORDER = ["profit_loss", "balance_sheet", "cash_flow"];
const SECTION_LABELS: Record<string, string> = {
  profit_loss: "Profit & Loss",
  balance_sheet: "Balance Sheet",
  cash_flow: "Cash Flow",
};

export function CompanyPageClient({ meta, financials, prices }: CompanyPageClientProps) {
  const sectionIds = ["overview", ...SECTION_ORDER, "chart"];
  useHashObserver(sectionIds);

  const periods = financials.periods.slice(0, 10); // Max 10 years

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

      {/* Financial tables — screener.in style: concepts as rows, periods as columns */}
      {SECTION_ORDER.map((sectionKey) => {
        const concepts = financials.sections[sectionKey];
        if (!concepts || concepts.length === 0) return null;

        return (
          <section key={sectionKey} id={sectionKey} className="snap-section">
            <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">
              {SECTION_LABELS[sectionKey]}
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse font-mono text-xs">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left px-3 py-1.5 text-muted font-medium sticky left-0 bg-background min-w-[200px]">
                      Particulars
                    </th>
                    {periods.map((p) => (
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
                      {periods.map((p) => {
                        const val = concept.values[p];
                        return (
                          <td key={p} className="px-3 py-1.5 text-right tabular-nums whitespace-nowrap">
                            {val != null ? formatCell(concept.unit === "percent" ? "npm" : "value", val) : "—"}
                          </td>
                        );
                      })}
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
        <PriceChart data={prices} height={350} />
      </section>
    </div>
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
