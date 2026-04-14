"use client";

import { useState, useCallback } from "react";
import { getFundFlowSummary, getFundFlowDaily, getFundFlowMonthly } from "@/lib/api";
import { DataTable } from "@/components/tables/DataTable";
import { PageHeader } from "@/components/shared/PageHeader";
import { FlowBarChart, type FlowBarData } from "@/components/charts/FlowBarChart";
import { useCachedData } from "@/lib/cache";

export default function FundFlowPage() {
  const [tab, setTab] = useState<"daily" | "monthly">("daily");
  const [segment, setSegment] = useState("CASH");

  const summaryFetcher = useCallback(() => getFundFlowSummary(), []);
  const dailyFetcher = useCallback(() => getFundFlowDaily(segment, 60), [segment]);
  const monthlyFetcher = useCallback(() => getFundFlowMonthly(segment, 36), [segment]);

  const summary = useCachedData("fundflow-summary", summaryFetcher, 5 * 60 * 1000);
  const daily = useCachedData(`fundflow-daily-${segment}`, dailyFetcher, 5 * 60 * 1000);
  const monthly = useCachedData(`fundflow-monthly-${segment}`, monthlyFetcher, 5 * 60 * 1000);

  const activeData = tab === "daily" ? daily : monthly;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fund Flows — FII / DII"
        loadedAt={summary.loadedAt}
        loading={summary.loading || activeData.loading}
        onRefresh={() => { summary.refresh(); activeData.refresh(); }}
        dataType="flow"
      />

      {/* Summary Cards */}
      {summary.data && <SummaryCards data={summary.data} />}

      {/* FII / DII Bar Chart */}
      {activeData.data && (
        <FlowBarChart
          data={toFlowBarData(activeData.data.flows)}
        />
      )}

      {/* Segment selector + Tab toggle */}
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          {["CASH", "CASH_EQUITY", "CASH_DEBT"].map((seg) => (
            <button
              key={seg}
              onClick={() => setSegment(seg)}
              className={`text-[10px] px-2 py-1 rounded border transition-colors ${
                segment === seg
                  ? "border-accent text-accent bg-accent/10"
                  : "border-border text-muted hover:text-foreground"
              }`}
            >
              {seg.replace(/_/g, " ")}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          {(["daily", "monthly"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`text-xs font-bold uppercase tracking-wider transition-colors ${
                tab === t ? "text-accent border-b-2 border-accent pb-0.5" : "text-muted hover:text-foreground"
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Flow Table */}
      {activeData.data ? (
        <DataTable
          columns={tab === "daily" ? DAILY_COLUMNS : MONTHLY_COLUMNS}
          rows={activeData.data.flows}
          symbolKey=""
        />
      ) : activeData.loading ? (
        <div className="text-muted text-xs text-center py-8">Loading...</div>
      ) : (
        <div className="text-muted text-xs text-center py-8">No data</div>
      )}
    </div>
  );
}

function toFlowBarData(flows: Record<string, unknown>[]): FlowBarData[] {
  return [...flows].reverse().map((row) => ({
    time: String(row.flow_date),
    fii_net: row.fii_net as number | null,
    dii_net: row.dii_net as number | null,
  }));
}

const DAILY_COLUMNS = [
  { key: "flow_date", label: "Date" },
  { key: "fii_buy", label: "FII Buy", align: "right" as const },
  { key: "fii_sell", label: "FII Sell", align: "right" as const },
  { key: "fii_net", label: "FII Net", align: "right" as const },
  { key: "dii_buy", label: "DII Buy", align: "right" as const },
  { key: "dii_sell", label: "DII Sell", align: "right" as const },
  { key: "dii_net", label: "DII Net", align: "right" as const },
];

const MONTHLY_COLUMNS = [
  { key: "flow_date", label: "Month" },
  { key: "fii_net", label: "FII Net", align: "right" as const },
  { key: "dii_net", label: "DII Net", align: "right" as const },
  { key: "fii_buy", label: "FII Buy", align: "right" as const },
  { key: "fii_sell", label: "FII Sell", align: "right" as const },
  { key: "dii_buy", label: "DII Buy", align: "right" as const },
  { key: "dii_sell", label: "DII Sell", align: "right" as const },
];

function SummaryCards({ data }: { data: Record<string, unknown> }) {
  const latest = (data.latest as Record<string, unknown>[]) || [];
  const mtd = (data.mtd as Record<string, unknown>[]) || [];
  const ytd = (data.ytd as Record<string, unknown>[]) || [];

  const fiiLatest = latest.find((r) => r.participant_type === "FII");
  const diiLatest = latest.find((r) => r.participant_type === "DII");
  const fiiMtd = mtd.find((r) => r.participant_type === "FII");
  const diiMtd = mtd.find((r) => r.participant_type === "DII");
  const fiiYtd = ytd.find((r) => r.participant_type === "FII");
  const diiYtd = ytd.find((r) => r.participant_type === "DII");

  return (
    <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
      <SummaryCard
        title={`Latest (${(data.latest_date as string) || "—"})`}
        fii={fiiLatest?.net_value as number | null}
        dii={diiLatest?.net_value as number | null}
      />
      <SummaryCard title="Month to Date" fii={fiiMtd?.net_value as number | null} dii={diiMtd?.net_value as number | null} />
      <SummaryCard title="Year to Date" fii={fiiYtd?.net_value as number | null} dii={diiYtd?.net_value as number | null} />
    </div>
  );
}

function SummaryCard({ title, fii, dii }: { title: string; fii: number | null; dii: number | null }) {
  const fmt = (v: number | null) => v != null ? `${v >= 0 ? "+" : ""}${v.toLocaleString("en-IN")} Cr` : "—";
  const cls = (v: number | null) => v == null ? "text-muted" : v >= 0 ? "text-positive" : "text-negative";

  return (
    <div className="border border-border rounded bg-surface p-3">
      <div className="text-[10px] text-muted uppercase tracking-wider mb-2">{title}</div>
      <div className="flex justify-between text-xs font-mono">
        <div>
          <span className="text-muted mr-2">FII</span>
          <span className={`font-bold ${cls(fii)}`}>{fmt(fii)}</span>
        </div>
        <div>
          <span className="text-muted mr-2">DII</span>
          <span className={`font-bold ${cls(dii)}`}>{fmt(dii)}</span>
        </div>
      </div>
    </div>
  );
}
