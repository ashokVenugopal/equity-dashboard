import React from "react";
import type { FIIPositioning } from "@/lib/api";

// ── Formatting helpers ──

const fmt = (v: number | null | undefined, digits = 2) =>
  v != null ? v.toLocaleString("en-IN", { maximumFractionDigits: digits }) : "—";

const cls = (v: number | null | undefined) =>
  v == null ? "text-muted" : v >= 0 ? "text-positive" : "text-negative";

// "+1.37 L" / "-1.83 L" — signed Lakh with explicit sign.
const fmtLakhSignedSpaced = (n: number | null | undefined) => {
  if (n == null) return "—";
  const lakh = n / 100000;
  const sign = lakh >= 0 ? "+" : "";
  return `${sign}${lakh.toFixed(2)} L`;
};

// "+1.37L" / "-1.83L" — signed Lakh, compact (no space before unit).
const fmtLakhSigned = (n: number | null | undefined) => {
  if (n == null) return "—";
  const lakh = n / 100000;
  return `${lakh >= 0 ? "+" : ""}${lakh.toFixed(2)}L`;
};

// "0.72L" — unsigned (used for absolute long/short contract counts).
const fmtLakhAbs = (n: number | null | undefined) => {
  if (n == null) return "—";
  return `${(n / 100000).toFixed(2)}L`;
};

interface HistoryRow {
  date: string;
  long_pct: number | null;
  short_pct: number | null;
  long_contracts: number;
  short_contracts: number;
  net: number;
  delta: number | null; // vs previous day (null for the oldest row)
}

/**
 * Compact 5-day table of daily Long / Short (% and absolute in Lakh),
 * Net (Lakh), and Δ vs previous day.
 */
function NetHistoryTable({ rows }: { rows: HistoryRow[] }) {
  if (rows.length === 0) {
    return <div className="text-[11px] text-muted">No history</div>;
  }
  return (
    <div className="text-[11px] font-mono">
      <div className="grid grid-cols-[auto_1fr_1fr_auto_auto] gap-x-3 gap-y-0.5 items-baseline">
        <div className="text-muted uppercase tracking-wider text-[10px]">Date</div>
        <div className="text-muted uppercase tracking-wider text-[10px]">Long</div>
        <div className="text-muted uppercase tracking-wider text-[10px]">Short</div>
        <div className="text-muted uppercase tracking-wider text-[10px] text-right">Net</div>
        <div className="text-muted uppercase tracking-wider text-[10px] text-right">Δ</div>

        {rows.map((r) => (
          <React.Fragment key={r.date}>
            <div className="text-muted">{r.date.slice(5)}</div>
            <div className="text-positive">
              {fmt(r.long_pct, 1)}%
              <span className="text-muted ml-1">({fmtLakhAbs(r.long_contracts)})</span>
            </div>
            <div className="text-negative">
              {fmt(r.short_pct, 1)}%
              <span className="text-muted ml-1">({fmtLakhAbs(r.short_contracts)})</span>
            </div>
            <div className={`text-right ${cls(r.net)}`}>{fmtLakhSigned(r.net)}</div>
            <div
              className={`text-right ${
                r.delta == null
                  ? "text-muted/50"
                  : r.delta >= 0
                  ? "text-positive"
                  : "text-negative"
              }`}
            >
              {r.delta == null
                ? "—"
                : `${r.delta >= 0 ? "+" : ""}${(r.delta / 100000).toFixed(2)}`}
            </div>
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

/**
 * One instrument category row (Index Futures OR Index Options) for a
 * participant. Shows current Long/Short split, net position, and a 5-day
 * history table with per-day deltas.
 */
function CategoryPositionRow({
  label,
  rows,
  highlightExtreme = false,
}: {
  label: string;
  rows: FIIPositioning[];
  highlightExtreme?: boolean;
}) {
  if (rows.length === 0) {
    return (
      <div>
        <div className="text-[11px] text-muted uppercase tracking-wider mb-1">{label}</div>
        <p className="text-muted text-xs">No data.</p>
      </div>
    );
  }

  const sortedDesc = [...rows].sort((a, b) => (a.trade_date > b.trade_date ? -1 : 1));
  const latest = sortedDesc[0];
  const latestNet = (latest.long_contracts ?? 0) - (latest.short_contracts ?? 0);

  // Last 5 days, newest → oldest (most recent row is at TOP of the table).
  const last5 = sortedDesc.slice(0, 5);
  const history: HistoryRow[] = last5.map((r, i) => {
    const net = (r.long_contracts ?? 0) - (r.short_contracts ?? 0);
    const olderRow = last5[i + 1];
    const olderNet = olderRow
      ? (olderRow.long_contracts ?? 0) - (olderRow.short_contracts ?? 0)
      : null;
    return {
      date: r.trade_date,
      long_pct: r.long_pct,
      short_pct: r.short_pct,
      long_contracts: r.long_contracts ?? 0,
      short_contracts: r.short_contracts ?? 0,
      net,
      delta: olderNet == null ? null : net - olderNet,
    };
  });

  const isExtremeShort = (latest.short_pct ?? 0) > 70;
  const isExtremeLong = (latest.long_pct ?? 0) > 70;
  const latestDelta = history.length >= 1 ? history[0].delta : null;

  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <div className="text-[11px] text-muted uppercase tracking-wider">{label}</div>
        <div className="text-[11px] text-muted font-mono">{latest.trade_date}</div>
      </div>

      <div className="flex items-center gap-3 mb-1 text-sm font-mono">
        <span className="text-positive font-bold">Long {fmt(latest.long_pct, 1)}%</span>
        <span className="text-negative font-bold">Short {fmt(latest.short_pct, 1)}%</span>
      </div>
      <div className="flex h-3 rounded overflow-hidden mb-2">
        <div className="bg-positive" style={{ width: `${latest.long_pct ?? 50}%` }} />
        <div className="bg-negative" style={{ width: `${latest.short_pct ?? 50}%` }} />
      </div>

      <div className="flex items-baseline justify-between mb-2">
        <div>
          <div className="text-[10px] text-muted uppercase tracking-wider leading-none">Net</div>
          <div className={`text-base font-mono font-bold leading-tight ${cls(latestNet)}`}>
            {fmtLakhSignedSpaced(latestNet)}
            <span className="text-[11px] text-muted ml-1 font-normal">
              ({fmt(latestNet, 0)})
            </span>
          </div>
        </div>
        {latestDelta != null && (
          <div className="text-right">
            <div className="text-[10px] text-muted uppercase tracking-wider leading-none">Δ vs prev</div>
            <div className={`text-sm font-mono leading-tight ${cls(latestDelta)}`}>
              {latestDelta >= 0 ? "+" : ""}
              {(latestDelta / 100000).toFixed(2)} L
            </div>
          </div>
        )}
      </div>

      <NetHistoryTable rows={history} />

      {highlightExtreme && isExtremeShort && (
        <div className="mt-1 text-[11px] text-negative font-bold">
          EXTREME SHORT ({fmt(latest.short_pct, 1)}%)
        </div>
      )}
      {highlightExtreme && isExtremeLong && (
        <div className="mt-1 text-[11px] text-positive font-bold">
          EXTREME LONG ({fmt(latest.long_pct, 1)}%)
        </div>
      )}
    </div>
  );
}

/**
 * Card for one participant (FII or CLIENT) showing both index futures
 * and index options positioning with 5-day history for each.
 */
function ParticipantPositioningCard({
  title,
  rows,
}: {
  title: string;
  rows: FIIPositioning[];
}) {
  const futuresRows = rows.filter((r) => r.instrument_category === "INDEX_FUTURES");
  const optionsRows = rows.filter((r) => r.instrument_category === "INDEX_OPTIONS");

  return (
    <div className="border border-border rounded bg-bg p-3 space-y-4">
      <h3 className="text-xs text-muted uppercase tracking-wider font-bold">{title}</h3>
      <CategoryPositionRow label="Index Futures" rows={futuresRows} highlightExtreme />
      <CategoryPositionRow label="Index Options" rows={optionsRows} />
    </div>
  );
}

/**
 * Full "Derivatives Positioning — FII vs Client" section.
 * Drop into any page; takes the unfiltered positioning list from the API.
 */
export function ParticipantPositioningPanel({
  positioning,
  title = "Derivatives Positioning — FII vs Client",
}: {
  positioning: FIIPositioning[];
  title?: string;
}) {
  if (!positioning || positioning.length === 0) {
    return (
      <section className="border border-border rounded bg-surface p-4">
        <h2 className="text-[11px] text-muted uppercase tracking-wider font-medium mb-2">
          Derivatives Positioning
        </h2>
        <p className="text-muted text-xs">
          No data. Run:{" "}
          <code className="text-accent">python -m pipeline.cli download-fo-participant</code>
        </p>
      </section>
    );
  }

  const fiiRows = positioning.filter((p) => p.participant_type === "FII");
  const clientRows = positioning.filter((p) => p.participant_type === "CLIENT");

  return (
    <section className="border border-border rounded bg-surface p-4">
      <h2 className="text-[11px] text-muted uppercase tracking-wider font-medium mb-3">
        {title}
      </h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <ParticipantPositioningCard title="FII" rows={fiiRows} />
        <ParticipantPositioningCard title="Client" rows={clientRows} />
      </div>
    </section>
  );
}
