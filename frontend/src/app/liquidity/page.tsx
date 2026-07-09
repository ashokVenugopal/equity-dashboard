"use client";

import { useCallback } from "react";
import {
  getFundFlowDaily,
  getMacroEvents,
  getMacroSeries,
  type CalendarEvent,
  type MacroSeries,
} from "@/lib/api";
import { FlowBarChart, type FlowBarData } from "@/components/charts/FlowBarChart";
import { MultiLineChart, type OverlayLine } from "@/components/charts/MultiLineChart";
import { PageHeader } from "@/components/shared/PageHeader";
import { useCachedData } from "@/lib/cache";

/*
 * Liquidity tab: FII/DII flows, policy rates (Fed + RBI repo), CPI YoY,
 * Fed balance sheet (QE/QT), US 10Y, and the current IPO pipeline.
 * Data: FRED (daily download-macro), seeds/ CSVs, NSE IPO calendar.
 */

interface LiquidityData {
  rates: MacroSeries[];
  cpi: MacroSeries[];
  walcl: MacroSeries[];
  dgs10: MacroSeries[];
  flows: { flows: Record<string, unknown>[] };
  ipos: CalendarEvent[];
}

const step = (points: { time: string; value: number }[]) => points; // step-ish is fine as line

export default function LiquidityPage() {
  const fetcher = useCallback(async () => {
    const [rates, cpi, walcl, dgs10, flows, events] = await Promise.all([
      getMacroSeries(["FEDFUNDS", "IN_REPO_RATE"], "none", "2019-01-01"),
      getMacroSeries(["CPIAUCSL", "IN_CPI_YOY"], "yoy", "2019-01-01"),
      getMacroSeries(["WALCL"], "none", "2019-01-01"),
      getMacroSeries(["DGS10"], "none", "2019-01-01"),
      getFundFlowDaily("CASH", 60),
      getMacroEvents(60, 0, ["ipo"]),
    ]);
    return {
      rates: rates.series,
      cpi: cpi.series,
      walcl: walcl.series,
      dgs10: dgs10.series,
      flows,
      ipos: events.days.flatMap((d) =>
        d.events.map((e) => ({ ...e, detail: `${d.date} · ${e.detail || ""}` }))),
    } as LiquidityData;
  }, []);

  const { data, loading, loadedAt, refresh, error } = useCachedData(
    "liquidity", fetcher, 15 * 60 * 1000);

  if (error && !data) {
    return <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">{error}</div>;
  }
  if (!data) {
    return <div className="text-muted text-xs py-8 text-center">Loading Liquidity...</div>;
  }

  const bySeries = (list: MacroSeries[], code: string) =>
    list.find((s) => s.code === code)?.points ?? [];

  const rateLines: OverlayLine[] = [
    { label: "Fed Funds %", color: "#2196F3", points: step(bySeries(data.rates, "FEDFUNDS")) },
    { label: "RBI Repo %", color: "#FFD700", points: step(bySeries(data.rates, "IN_REPO_RATE")) },
  ].filter((l) => l.points.length > 0);

  const cpiLines: OverlayLine[] = [
    { label: "US CPI YoY %", color: "#2196F3", points: bySeries(data.cpi, "CPIAUCSL") },
    { label: "India CPI YoY %", color: "#FFD700", points: bySeries(data.cpi, "IN_CPI_YOY") },
  ].filter((l) => l.points.length > 0);

  const walclLines: OverlayLine[] = [
    { label: "Fed Balance Sheet $mn", color: "#AB47BC", points: bySeries(data.walcl, "WALCL") },
  ].filter((l) => l.points.length > 0);

  const dgs10Lines: OverlayLine[] = [
    { label: "US 10Y %", color: "#26A69A", points: bySeries(data.dgs10, "DGS10") },
  ].filter((l) => l.points.length > 0);

  const barData: FlowBarData[] = [...data.flows.flows].reverse().map((r) => ({
    time: String(r.flow_date),
    fii_net: r.fii_net as number | null,
    dii_net: r.dii_net as number | null,
  }));

  return (
    <div className="space-y-4">
      <PageHeader title="Liquidity" loadedAt={loadedAt} loading={loading} onRefresh={refresh} />

      {/* Flows */}
      {barData.length > 0 && <FlowBarChart data={barData} height={180} />}

      {/* Policy rates + CPI */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="border border-border rounded bg-surface p-3">
          <h2 className="text-[11px] text-muted uppercase tracking-wider font-medium mb-2">
            Policy rates — Fed funds vs RBI repo
          </h2>
          <MultiLineChart lines={rateLines} height={220} />
          <p className="text-[10px] text-muted mt-1">
            Repo rate is manually seeded (seeds/india_repo_rate.csv) — verify after each MPC.
          </p>
        </section>
        <section className="border border-border rounded bg-surface p-3">
          <h2 className="text-[11px] text-muted uppercase tracking-wider font-medium mb-2">
            CPI YoY
          </h2>
          <MultiLineChart lines={cpiLines} height={220} />
          {bySeries(data.cpi, "IN_CPI_YOY").length === 0 && (
            <p className="text-[10px] text-muted mt-1">
              India CPI not seeded yet — add monthly index values to seeds/india_cpi_yoy.csv.
            </p>
          )}
        </section>
      </div>

      {/* QE + 10Y */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="border border-border rounded bg-surface p-3">
          <h2 className="text-[11px] text-muted uppercase tracking-wider font-medium mb-2">
            Fed balance sheet (QE / QT)
          </h2>
          <MultiLineChart lines={walclLines} height={220} />
        </section>
        <section className="border border-border rounded bg-surface p-3">
          <h2 className="text-[11px] text-muted uppercase tracking-wider font-medium mb-2">
            Bond market — US 10Y yield
          </h2>
          <MultiLineChart lines={dgs10Lines} height={220} />
        </section>
      </div>

      {/* IPO pipeline */}
      <section className="border border-border rounded bg-surface p-3">
        <h2 className="text-[11px] text-muted uppercase tracking-wider font-medium mb-2">
          IPO pipeline (NSE, next 60 days)
        </h2>
        {data.ipos.length > 0 ? (
          <ul className="space-y-1">
            {data.ipos.map((e, i) => (
              <li key={i} className="text-[11px] font-mono">
                <span className="text-foreground">{e.title}</span>
                <span className="text-muted ml-2">{e.detail}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-muted text-xs">No upcoming IPOs captured.</p>
        )}
      </section>

      {/* Planned — intentionally empty, keep the intention visible */}
      <section className="border border-dashed border-border rounded bg-surface/50 p-3">
        <h2 className="text-[11px] text-muted uppercase tracking-wider font-medium mb-1">
          Planned (no free data source yet)
        </h2>
        <ul className="text-[11px] text-muted list-disc ml-4 space-y-0.5">
          <li>MSCI index weights — India weight in MSCI EM (msci.com factsheets are PDF-only)</li>
          <li>Household borrowings-to-savings ratio (RBI annual publications)</li>
          <li>Social benefit / transfer rates history (source undecided)</li>
          <li>India 10Y G-sec yield (no reliable free daily feed found)</li>
        </ul>
      </section>
    </div>
  );
}
