"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createInvestorGroup,
  deleteInvestorGroup,
  getCoInvestMatrix,
  getGroupHoldings,
  getInvestorChanges,
  getInvestorHoldings,
  getInvestorMatrix,
  getInvestorsList,
  getInvestorGroups,
  getMissingCompanies,
  updateInvestorGroup,
  type CoInvestor,
  type CoInvestPair,
  type GroupHoldingRow,
  type InvestorChange,
  type InvestorGroup,
  type InvestorHoldingRow,
  type InvestorRow,
  type MatrixCellEntry,
} from "@/lib/api";
import { PageHeader } from "@/components/shared/PageHeader";
import { usePersistentState } from "@/lib/persist";

/*
 * Investors page — superstar-shareholder portfolios (Trendlyne, quarterly):
 *   Investors — registry + drill-down (stocks × quarters pivot)
 *   Changes   — new buys / exits / adds / trims per quarter
 *   Matrix    — sector-or-stock × quarter radar with investor chips
 *   Groups    — related/coordinating investor sets: consolidated + overlap
 *   Missing   — held stocks outside our tracked universe (import wishlist)
 */

const VIEWS = ["investors", "changes", "matrix", "co-invest", "groups", "missing"] as const;
type View = (typeof VIEWS)[number];

const CATEGORIES = ["", "individual", "institutional", "fii"] as const;

const KIND_META: Record<string, { label: string; cls: string }> = {
  new: { label: "NEW", cls: "text-positive border-positive/50" },
  add: { label: "ADD", cls: "text-positive/80 border-positive/30" },
  trim: { label: "TRIM", cls: "text-[#FFD700] border-[#FFD700]/40" },
  exit: { label: "EXIT", cls: "text-negative border-negative/50" },
};

const fmtQ = (iso: string) => {
  const [y, m] = iso.split("-");
  return `${["", "", "", "Mar", "", "", "Jun", "", "", "Sep", "", "", "Dec"][Number(m)] || m} ${y.slice(2)}`;
};

const fmtPct = (v: number | null | undefined) => (v != null ? `${v}%` : "—");

function KindBadge({ kind }: { kind: string | null }) {
  if (!kind || !KIND_META[kind]) return null;
  const k = KIND_META[kind];
  return (
    <span className={`text-[9px] px-1 rounded border font-mono ${k.cls}`}>{k.label}</span>
  );
}

export default function InvestorsPage() {
  const [view, setView] = usePersistentState<View>("inv:view", "investors");
  const [category, setCategory] = usePersistentState("inv:category", "");
  const [loading, setLoading] = useState(false);

  return (
    <div className="space-y-4">
      <PageHeader title="Investors" loadedAt={null} loading={loading} onRefresh={() => {}} />

      <div className="flex flex-wrap items-center gap-2">
        {VIEWS.map((v) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`text-[11px] px-2.5 py-0.5 rounded border capitalize ${
              view === v ? "border-accent text-accent" : "border-border text-muted"
            }`}
          >
            {v}
          </button>
        ))}
        <span className="text-[10px] text-muted ml-3">category:</span>
        {CATEGORIES.map((c) => (
          <button
            key={c || "all"}
            onClick={() => setCategory(c)}
            className={`text-[11px] px-2 py-0.5 rounded border ${
              category === c ? "border-accent text-accent" : "border-border text-muted"
            }`}
          >
            {c || "all"}
          </button>
        ))}
      </div>

      {view === "investors" && <InvestorsView category={category} setLoading={setLoading} />}
      {view === "changes" && <ChangesView category={category} setLoading={setLoading} />}
      {view === "matrix" && <MatrixView category={category} setLoading={setLoading} />}
      {view === "co-invest" && <CoInvestView category={category} setLoading={setLoading} />}
      {view === "groups" && <GroupsView setLoading={setLoading} />}
      {view === "missing" && <MissingView setLoading={setLoading} />}
    </div>
  );
}

// ── Investors list + drill-down ─────────────────────────────────────────

function InvestorsView({ category, setLoading }: { category: string; setLoading: (b: boolean) => void }) {
  const [investors, setInvestors] = useState<InvestorRow[]>([]);
  const [search, setSearch] = usePersistentState("inv:search", "");
  const [selected, setSelected] = usePersistentState<InvestorRow | null>("inv:selected", null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getInvestorsList(category)
      .then((d) => {
        setInvestors(d.investors);
        if (d.investors.length === 0) {
          setError("No investor data — run: python -m pipeline.cli download-investor-portfolios");
        }
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [category, setLoading]);

  const filtered = investors.filter(
    (i) => !search || i.name.toLowerCase().includes(search.toLowerCase()));

  if (selected) {
    return <InvestorDrilldown investor={selected} onBack={() => setSelected(null)} />;
  }

  return (
    <section className="border border-border rounded bg-surface p-3">
      {error && (
        <p className="text-negative text-xs border border-negative/30 rounded p-2 bg-negative/5 mb-2">{error}</p>
      )}
      <div className="flex items-center gap-2 mb-2">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="search investors…"
          className="bg-background border border-border rounded px-2 py-0.5 text-[11px] font-mono w-56"
        />
        <span className="text-[10px] text-muted">{filtered.length} investors</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse font-mono text-[11px]">
          <thead>
            <tr className="border-b border-border text-muted">
              <th className="text-left py-1 pr-3 font-medium">Investor</th>
              <th className="text-left py-1 px-3 font-medium">Categories</th>
              <th className="text-right py-1 px-3 font-medium">Holdings</th>
              <th className="text-right py-1 px-3 font-medium text-positive">New</th>
              <th className="text-right py-1 px-3 font-medium text-positive/80">Add</th>
              <th className="text-right py-1 px-3 font-medium text-[#FFD700]">Trim</th>
              <th className="text-right py-1 pl-3 font-medium text-negative">Exit</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((i) => (
              <tr
                key={i.id}
                className="border-b border-border/30 hover:bg-surface-hover cursor-pointer"
                onClick={() => setSelected(i)}
              >
                <td className="py-1 pr-3 text-accent">{i.name}</td>
                <td className="py-1 px-3 text-muted">{i.categories.join(", ")}</td>
                <td className="text-right py-1 px-3">{i.holdings_latest}</td>
                <td className="text-right py-1 px-3 text-positive">{i.changes_latest.new || ""}</td>
                <td className="text-right py-1 px-3 text-positive/80">{i.changes_latest.add || ""}</td>
                <td className="text-right py-1 px-3 text-[#FFD700]">{i.changes_latest.trim || ""}</td>
                <td className="text-right py-1 pl-3 text-negative">{i.changes_latest.exit || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function InvestorDrilldown({ investor, onBack }: { investor: InvestorRow; onBack: () => void }) {
  const [data, setData] = useState<{ quarters: string[]; holdings: InvestorHoldingRow[] } | null>(null);

  useEffect(() => {
    getInvestorHoldings(investor.id).then((d) =>
      setData({ quarters: d.quarters, holdings: d.holdings }));
  }, [investor.id]);

  return (
    <section className="border border-border rounded bg-surface p-3">
      <div className="flex items-center gap-3 mb-2">
        <button className="text-[11px] text-muted border border-border rounded px-2 py-0.5" onClick={onBack}>
          ← back
        </button>
        <h2 className="text-[12px] font-mono font-bold text-accent">{investor.name}</h2>
        <span className="text-[10px] text-muted">{investor.categories.join(", ")}</span>
      </div>
      {!data ? (
        <p className="text-muted text-xs py-4">Loading holdings…</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse font-mono text-[11px]">
            <thead>
              <tr className="border-b border-border text-muted">
                <th className="text-left py-1 pr-3 font-medium sticky left-0 bg-surface">Stock</th>
                <th className="text-left py-1 px-2 font-medium"></th>
                {data.quarters.map((q) => (
                  <th key={q} className="text-right py-1 px-3 font-medium whitespace-nowrap">{fmtQ(q)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.holdings.map((h) => (
                <tr key={h.stock_name} className="border-b border-border/30">
                  <td className="py-1 pr-3 sticky left-0 bg-surface whitespace-nowrap">
                    {h.stock_name}
                    {!h.tracked && <span className="text-[9px] text-muted ml-1" title="not in tracked universe">∉</span>}
                  </td>
                  <td className="py-1 px-2"><KindBadge kind={h.latest_change} /></td>
                  {data.quarters.map((q) => (
                    <td key={q} className="text-right py-1 px-3 tabular-nums">
                      {fmtPct(h.quarters[q])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// ── Changes ─────────────────────────────────────────────────────────────

function ChangesView({ category, setLoading }: { category: string; setLoading: (b: boolean) => void }) {
  const [kind, setKind] = usePersistentState("inv:changes:kind", "");
  const [quarter, setQuarter] = usePersistentState("inv:changes:quarter", "");
  const [data, setData] = useState<{ changes: InvestorChange[]; quarter: string | null; quarters: string[] } | null>(null);

  useEffect(() => {
    setLoading(true);
    getInvestorChanges(quarter, kind, category)
      .then(setData)
      .finally(() => setLoading(false));
  }, [quarter, kind, category, setLoading]);

  return (
    <section className="border border-border rounded bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <select
          value={quarter}
          onChange={(e) => setQuarter(e.target.value)}
          className="bg-background border border-border rounded px-2 py-0.5 text-[11px] font-mono"
        >
          {(data?.quarters ?? []).map((q) => (
            <option key={q} value={q}>{fmtQ(q)}</option>
          ))}
        </select>
        {["", "new", "add", "trim", "exit"].map((k) => (
          <button
            key={k || "all"}
            onClick={() => setKind(k)}
            className={`text-[11px] px-2 py-0.5 rounded border ${
              kind === k ? "border-accent text-accent" : "border-border text-muted"
            }`}
          >
            {k || "all"}
          </button>
        ))}
        <span className="text-[10px] text-muted ml-2">
          {data?.changes.length ?? 0} changes · “exit” = sold OR fell below the 1% disclosure threshold
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse font-mono text-[11px]">
          <thead>
            <tr className="border-b border-border text-muted">
              <th className="text-left py-1 pr-3 font-medium">Kind</th>
              <th className="text-left py-1 px-3 font-medium">Investor</th>
              <th className="text-left py-1 px-3 font-medium">Stock</th>
              <th className="text-left py-1 px-3 font-medium">Sector</th>
              <th className="text-right py-1 px-3 font-medium">Prev %</th>
              <th className="text-right py-1 px-3 font-medium">Now %</th>
              <th className="text-right py-1 pl-3 font-medium">Δ</th>
            </tr>
          </thead>
          <tbody>
            {(data?.changes ?? []).map((c, i) => (
              <tr key={i} className="border-b border-border/30">
                <td className="py-1 pr-3"><KindBadge kind={c.kind} /></td>
                <td className="py-1 px-3 text-accent whitespace-nowrap">{c.investor}</td>
                <td className="py-1 px-3 whitespace-nowrap">
                  {c.stock_name}
                  {!c.tracked && <span className="text-[9px] text-muted ml-1">∉</span>}
                </td>
                <td className="py-1 px-3 text-muted">{c.sector ?? "—"}</td>
                <td className="text-right py-1 px-3">{fmtPct(c.prev_pct)}</td>
                <td className="text-right py-1 px-3">{fmtPct(c.cur_pct)}</td>
                <td className={`text-right py-1 pl-3 ${c.delta >= 0 ? "text-positive" : "text-negative"}`}>
                  {c.delta > 0 ? "+" : ""}{c.delta}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ── Matrix (radar) ──────────────────────────────────────────────────────

function MatrixView({ category, setLoading }: { category: string; setLoading: (b: boolean) => void }) {
  const [by, setBy] = usePersistentState<"sector" | "stock">("inv:matrix:by", "sector");
  const [minPct, setMinPct] = usePersistentState("inv:matrix:minpct", 1.0);
  const [data, setData] = useState<{ rows: { row: string; cells: Record<string, MatrixCellEntry[]> }[]; quarters: string[] } | null>(null);

  useEffect(() => {
    setLoading(true);
    getInvestorMatrix(by, 9, category, minPct)
      .then(setData)
      .finally(() => setLoading(false));
  }, [by, category, minPct, setLoading]);

  return (
    <section className="border border-border rounded bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        {(["sector", "stock"] as const).map((b) => (
          <button
            key={b}
            onClick={() => setBy(b)}
            className={`text-[11px] px-2 py-0.5 rounded border ${
              by === b ? "border-accent text-accent" : "border-border text-muted"
            }`}
          >
            by {b}
          </button>
        ))}
        <span className="text-[10px] text-muted ml-2">min holding %:</span>
        {[0.5, 1.0, 2.0, 5.0].map((p) => (
          <button
            key={p}
            onClick={() => setMinPct(p)}
            className={`text-[11px] px-2 py-0.5 rounded border ${
              minPct === p ? "border-accent text-accent" : "border-border text-muted"
            }`}
          >
            ≥{p}%
          </button>
        ))}
        <span className="text-[10px] text-muted ml-2">
          chips: investor (pct) · alphabetical in every cell · ★ new, ▲ add, ▼ trim
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="border-collapse font-mono text-[10px] min-w-full">
          <thead>
            <tr className="border-b border-border text-muted">
              <th className="text-left py-1 pr-3 font-medium sticky left-0 bg-surface min-w-40">
                {by === "sector" ? "Sector" : "Stock"}
              </th>
              {(data?.quarters ?? []).map((q) => (
                <th key={q} className="text-left py-1 px-2 font-medium min-w-52">{fmtQ(q)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(data?.rows ?? []).map((r) => (
              <tr key={r.row} className="border-b border-border/30 align-top">
                <td className="py-1.5 pr-3 sticky left-0 bg-surface text-foreground whitespace-nowrap">
                  {r.row}
                </td>
                {(data?.quarters ?? []).map((q) => {
                  const entries = r.cells[q] ?? [];
                  return (
                    <td key={q} className="py-1.5 px-2">
                      <div className="flex flex-wrap gap-1 max-w-64">
                        {entries.slice(0, 12).map((e, i) => (
                          <span
                            key={i}
                            title={`${e.investor}${e.stock ? ` · ${e.stock}` : ""} — ${e.pct}%${e.flag ? ` (${e.flag})` : ""}`}
                            className={`px-1 py-0.5 rounded border text-[9px] whitespace-nowrap ${
                              e.flag === "new"
                                ? "border-positive/60 text-positive"
                                : e.flag === "add"
                                ? "border-positive/30 text-positive/80"
                                : e.flag === "trim"
                                ? "border-[#FFD700]/40 text-[#FFD700]"
                                : "border-border text-muted"
                            }`}
                          >
                            {e.flag === "new" ? "★ " : e.flag === "add" ? "▲ " : e.flag === "trim" ? "▼ " : ""}
                            {e.investor.length > 16 ? e.investor.slice(0, 15) + "…" : e.investor} ({e.pct})
                          </span>
                        ))}
                        {entries.length > 12 && (
                          <span className="text-[9px] text-muted">+{entries.length - 12} more</span>
                        )}
                      </div>
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
}

// ── Co-invest (investor × investor overlap heatmap) ─────────────────────

function CoInvestView({ category, setLoading }: { category: string; setLoading: (b: boolean) => void }) {
  const [minOverlap, setMinOverlap] = usePersistentState("inv:coinvest:min", 3);
  const [top, setTop] = usePersistentState("inv:coinvest:top", 30);
  const [quarter, setQuarter] = usePersistentState("inv:coinvest:quarter", "");
  const [data, setData] = useState<{
    investors: CoInvestor[]; pairs: CoInvestPair[];
    quarter: string | null; quarters: string[]; total_investors: number;
  } | null>(null);
  const [selectedPair, setSelectedPair] = useState<CoInvestPair | null>(null);

  useEffect(() => {
    setLoading(true);
    setSelectedPair(null);
    getCoInvestMatrix(quarter, category, minOverlap, top)
      .then(setData)
      .finally(() => setLoading(false));
  }, [quarter, category, minOverlap, top, setLoading]);

  const pairKey = (a: number, b: number) => (a < b ? `${a}-${b}` : `${b}-${a}`);
  const pairMap = new Map((data?.pairs ?? []).map((p) => [pairKey(p.a, p.b), p]));
  const maxCount = Math.max(...(data?.pairs ?? []).map((p) => p.count), 1);
  const invs = data?.investors ?? [];
  const nameById = new Map(invs.map((i) => [i.id, i.name]));
  const short = (n: string) => (n.length > 22 ? n.slice(0, 21) + "…" : n);

  return (
    <section className="border border-border rounded bg-surface p-3">
      <div className="flex flex-wrap items-center gap-2 mb-2">
        <select
          value={quarter}
          onChange={(e) => setQuarter(e.target.value)}
          className="bg-background border border-border rounded px-2 py-0.5 text-[11px] font-mono"
        >
          {(data?.quarters ?? []).map((q) => (
            <option key={q} value={q}>{fmtQ(q)}</option>
          ))}
        </select>
        <span className="text-[10px] text-muted ml-2">min common stocks:</span>
        {[2, 3, 5, 10].map((m) => (
          <button
            key={m}
            onClick={() => setMinOverlap(m)}
            className={`text-[11px] px-2 py-0.5 rounded border ${
              minOverlap === m ? "border-accent text-accent" : "border-border text-muted"
            }`}
          >
            ≥{m}
          </button>
        ))}
        <span className="text-[10px] text-muted ml-2">show top:</span>
        {[20, 30, 50, 100].map((t) => (
          <button
            key={t}
            onClick={() => setTop(t)}
            className={`text-[11px] px-2 py-0.5 rounded border ${
              top === t ? "border-accent text-accent" : "border-border text-muted"
            }`}
          >
            {t}
          </button>
        ))}
        <span className="text-[10px] text-muted ml-2">
          {invs.length} of {data?.total_investors ?? 0} investors (most-connected first) ·
          cell = stocks both disclose · click a cell to list them
        </span>
      </div>

      {invs.length === 0 ? (
        <p className="text-muted text-xs py-4">
          No co-investment pairs at this threshold — lower “min common stocks”.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="border-collapse font-mono text-[9px]">
            <thead>
              <tr>
                <th className="sticky left-0 bg-surface z-10" />
                <th className="text-right text-muted pr-1 pb-1 font-medium">n</th>
                {invs.map((c) => (
                  <th key={c.id} className="align-bottom pb-1 px-0" title={c.name}>
                    <div
                      className="text-muted font-normal whitespace-nowrap mx-auto"
                      style={{ writingMode: "vertical-rl", transform: "rotate(180deg)", maxHeight: 110, overflow: "hidden" }}
                    >
                      {short(c.name)}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {invs.map((r) => (
                <tr key={r.id}>
                  <td
                    className="sticky left-0 bg-surface z-10 pr-2 py-0 text-muted whitespace-nowrap text-right"
                    title={`${r.name} — ${r.holdings} holdings, ${r.partners} partners`}
                  >
                    {short(r.name)}
                  </td>
                  <td className="text-right pr-1 text-muted/70">{r.holdings}</td>
                  {invs.map((c) => {
                    if (c.id === r.id) {
                      return <td key={c.id} className="w-6 h-6 text-center text-muted/40 bg-border/20">·</td>;
                    }
                    const p = pairMap.get(pairKey(r.id, c.id));
                    if (!p) return <td key={c.id} className="w-6 h-6 border border-border/20" />;
                    const alpha = 0.15 + 0.7 * (p.count / maxCount);
                    return (
                      <td
                        key={c.id}
                        onClick={() => setSelectedPair(p)}
                        title={`${r.name} × ${c.name} — ${p.count} common: ${p.stocks.slice(0, 8).join(", ")}${p.stocks_total > 8 ? "…" : ""}`}
                        className="w-6 h-6 text-center cursor-pointer border border-border/20 hover:outline hover:outline-1 hover:outline-accent"
                        style={{ backgroundColor: `rgba(33, 150, 243, ${alpha.toFixed(2)})` }}
                      >
                        {p.count}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedPair && (
        <div className="mt-3 border-t border-border/50 pt-2">
          <div className="flex items-center gap-2 text-[11px] font-mono">
            <span className="text-accent">
              {nameById.get(selectedPair.a)} × {nameById.get(selectedPair.b)}
            </span>
            <span className="text-muted">— {selectedPair.stocks_total} common holdings</span>
            <button
              className="text-[10px] text-muted border border-border rounded px-1.5"
              onClick={() => setSelectedPair(null)}
            >
              close
            </button>
          </div>
          <div className="flex flex-wrap gap-1 mt-1.5">
            {selectedPair.stocks.map((s) => (
              <span key={s} className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-border">
                {s}
              </span>
            ))}
            {selectedPair.stocks_total > selectedPair.stocks.length && (
              <span className="text-[10px] text-muted">
                +{selectedPair.stocks_total - selectedPair.stocks.length} more
              </span>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

// ── Groups ──────────────────────────────────────────────────────────────

function GroupsView({ setLoading }: { setLoading: (b: boolean) => void }) {
  const [groups, setGroups] = useState<InvestorGroup[]>([]);
  const [investors, setInvestors] = useState<InvestorRow[]>([]);
  const [selected, setSelected] = usePersistentState<InvestorGroup | null>("inv:group:selected", null);
  const [mode, setMode] = usePersistentState<"consolidated" | "overlap">("inv:group:mode", "consolidated");
  const [holdings, setHoldings] = useState<{ quarters: string[]; holdings: GroupHoldingRow[] } | null>(null);
  const [editName, setEditName] = useState("");
  const [editMembers, setEditMembers] = useState<number[]>([]);
  const [editId, setEditId] = useState<number | null>(null);
  const [picker, setPicker] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const refresh = useCallback(() => {
    getInvestorGroups().then((d) => setGroups(d.groups));
  }, []);

  useEffect(() => {
    refresh();
    getInvestorsList().then((d) => setInvestors(d.investors));
  }, [refresh]);

  useEffect(() => {
    if (!selected) return;
    setLoading(true);
    getGroupHoldings(selected.id, mode)
      .then((d) => setHoldings({ quarters: d.quarters, holdings: d.holdings }))
      .finally(() => setLoading(false));
  }, [selected, mode, setLoading]);

  const nameById = new Map(investors.map((i) => [i.id, i.name]));

  const save = async () => {
    setErr(null);
    try {
      if (editId == null) await createInvestorGroup(editName, editMembers);
      else await updateInvestorGroup(editId, editName, editMembers);
      setEditName(""); setEditMembers([]); setEditId(null);
      refresh();
    } catch (e) {
      setErr(String(e));
    }
  };

  return (
    <div className="space-y-3">
      <section className="border border-border rounded bg-surface p-3 space-y-2">
        <h2 className="text-[11px] text-muted uppercase tracking-wider font-medium">
          Groups — related / coordinating investors
        </h2>
        <div className="flex flex-wrap gap-2">
          {groups.map((g) => (
            <span key={g.id} className="flex items-center gap-1">
              <button
                onClick={() => setSelected(g)}
                className={`text-[11px] px-2 py-0.5 rounded border font-mono ${
                  selected?.id === g.id ? "border-accent text-accent" : "border-border text-foreground"
                }`}
              >
                {g.name} ({g.member_ids.length})
              </button>
              <button
                className="text-[10px] text-muted hover:text-accent"
                onClick={() => {
                  setEditId(g.id); setEditName(g.name); setEditMembers(g.member_ids);
                }}
              >
                edit
              </button>
              <button
                className="text-[10px] text-muted hover:text-negative"
                onClick={async () => {
                  await deleteInvestorGroup(g.id).catch(() => {});
                  if (selected?.id === g.id) setSelected(null);
                  refresh();
                }}
              >
                ×
              </button>
            </span>
          ))}
          {groups.length === 0 && <span className="text-[11px] text-muted">no groups yet — create one below</span>}
        </div>

        <div className="border-t border-border/50 pt-2 flex flex-wrap items-center gap-2">
          <span className="text-[10px] text-muted">{editId == null ? "new:" : `editing #${editId}:`}</span>
          <input
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            placeholder="group name…"
            className="bg-background border border-border rounded px-2 py-0.5 text-[11px] font-mono w-44"
          />
          {editMembers.map((id) => (
            <span key={id} className="text-[10px] font-mono px-1.5 py-0.5 rounded border border-border">
              {nameById.get(id) ?? id}
              <button className="text-muted hover:text-negative ml-1"
                      onClick={() => setEditMembers(editMembers.filter((x) => x !== id))}>×</button>
            </span>
          ))}
          <input
            list="investor-options"
            value={picker}
            onChange={(e) => {
              const v = e.target.value;
              // Selecting a datalist option fires change (not Enter) —
              // add immediately on an exact name match.
              const inv = investors.find((i) => i.name === v.trim());
              if (inv) {
                if (!editMembers.includes(inv.id)) setEditMembers((m) => [...m, inv.id]);
                setPicker("");
              } else {
                setPicker(v);
              }
            }}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;
              const inv = investors.find(
                (i) => i.name.toLowerCase() === picker.trim().toLowerCase());
              if (inv && !editMembers.includes(inv.id)) {
                setEditMembers([...editMembers, inv.id]);
                setPicker("");
              }
            }}
            placeholder="add investor…"
            className="bg-background border border-border rounded px-2 py-0.5 text-[11px] font-mono w-52"
          />
          <datalist id="investor-options">
            {investors.map((i) => <option key={i.id} value={i.name} />)}
          </datalist>
          <button
            className="text-[11px] text-accent border border-border rounded px-2 py-0.5"
            onClick={() => {
              const inv = investors.find(
                (i) => i.name.toLowerCase() === picker.trim().toLowerCase());
              if (inv && !editMembers.includes(inv.id)) {
                setEditMembers([...editMembers, inv.id]);
                setPicker("");
              }
            }}
          >
            add
          </button>
          <button
            className="text-[11px] text-positive border border-border rounded px-2 py-0.5 disabled:opacity-40"
            disabled={!editName.trim() || editMembers.length < 2}
            onClick={save}
          >
            {editId == null ? "create" : "save"}
          </button>
          {err && <span className="text-[10px] text-negative">{err}</span>}
        </div>
      </section>

      {selected && (
        <section className="border border-border rounded bg-surface p-3">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-[12px] font-mono font-bold text-accent">{selected.name}</h3>
            {(["consolidated", "overlap"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`text-[11px] px-2 py-0.5 rounded border ${
                  mode === m ? "border-accent text-accent" : "border-border text-muted"
                }`}
              >
                {m}
              </button>
            ))}
            <span className="text-[10px] text-muted">
              {mode === "consolidated"
                ? "all stocks any member holds · pct = sum across members"
                : "only stocks held by ≥2 members in the latest quarter"}
            </span>
          </div>
          {!holdings ? (
            <p className="text-muted text-xs py-3">Loading…</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse font-mono text-[11px]">
                <thead>
                  <tr className="border-b border-border text-muted">
                    <th className="text-left py-1 pr-3 font-medium sticky left-0 bg-surface">Stock</th>
                    <th className="text-right py-1 px-2 font-medium">Members</th>
                    {holdings.quarters.map((q) => (
                      <th key={q} className="text-right py-1 px-3 font-medium whitespace-nowrap">{fmtQ(q)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {holdings.holdings.map((h) => (
                    <tr key={h.stock_name} className="border-b border-border/30">
                      <td className="py-1 pr-3 sticky left-0 bg-surface whitespace-nowrap"
                          title={Object.entries(h.members).map(([m, qs]) =>
                            `${m}: ${Object.entries(qs).slice(0, 3).map(([q, p]) => `${fmtQ(q)}=${p}%`).join(", ")}`).join(" · ")}>
                        {h.stock_name}
                        {!h.tracked && <span className="text-[9px] text-muted ml-1">∉</span>}
                      </td>
                      <td className="text-right py-1 px-2">{h.holders_latest}</td>
                      {holdings.quarters.map((q) => (
                        <td key={q} className="text-right py-1 px-3 tabular-nums">
                          {h.quarters[q] != null ? `${h.quarters[q]}%` : "—"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

// ── Missing companies ───────────────────────────────────────────────────

function MissingView({ setLoading }: { setLoading: (b: boolean) => void }) {
  const [data, setData] = useState<{ missing: { stock_name: string; nse_code: string | null; holders: number; holders_latest: number; last_seen: string }[] } | null>(null);

  useEffect(() => {
    setLoading(true);
    getMissingCompanies().then(setData).finally(() => setLoading(false));
  }, [setLoading]);

  return (
    <section className="border border-border rounded bg-surface p-3">
      <p className="text-[10px] text-muted mb-2">
        Stocks held by tracked investors but missing from our companies universe — add the
        ones you care about to companies.csv, then run discovery + ingest.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse font-mono text-[11px]">
          <thead>
            <tr className="border-b border-border text-muted">
              <th className="text-left py-1 pr-3 font-medium">Stock</th>
              <th className="text-left py-1 px-3 font-medium">NSE code</th>
              <th className="text-right py-1 px-3 font-medium">Holders (latest Q)</th>
              <th className="text-right py-1 px-3 font-medium">Holders (ever)</th>
              <th className="text-right py-1 pl-3 font-medium">Last seen</th>
            </tr>
          </thead>
          <tbody>
            {(data?.missing ?? []).map((m) => (
              <tr key={`${m.stock_name}-${m.nse_code}`} className="border-b border-border/30">
                <td className="py-1 pr-3">{m.stock_name}</td>
                <td className="py-1 px-3 text-accent">{m.nse_code ?? "—"}</td>
                <td className="text-right py-1 px-3">{m.holders_latest}</td>
                <td className="text-right py-1 px-3 text-muted">{m.holders}</td>
                <td className="text-right py-1 pl-3 text-muted">{m.last_seen}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
