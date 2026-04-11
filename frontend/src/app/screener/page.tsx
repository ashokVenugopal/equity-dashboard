"use client";

import { useState, useContext, useCallback } from "react";
import { searchFilter } from "@/lib/api";
import { DataTable } from "@/components/tables/DataTable";
import { useCachedData } from "@/lib/cache";
import { PageHeader } from "@/components/shared/PageHeader";

interface ScreenerState {
  expression: string;
  results: Record<string, unknown>[];
  columns: { key: string; label: string; align?: "left" | "right" }[];
  info: string;
}

export default function ScreenerPage() {
  // Persist screener state in cache so it survives tab switches
  const { data: cached, set: setCache } = useCachedScreenerState();
  const [expression, setExpression] = useState(cached?.expression || "Filter: PE < 20, ROE > 15");
  const [results, setResults] = useState<Record<string, unknown>[]>(cached?.results || []);
  const [columns, setColumns] = useState(cached?.columns || []);
  const [info, setInfo] = useState(cached?.info || "");
  const [loading, setLoading] = useState(false);
  const [ranAt, setRanAt] = useState<Date | null>(cached ? new Date() : null);

  async function handleExecute() {
    setLoading(true);
    try {
      const data = await searchFilter(expression);
      setResults(data.results);

      const cols = data.results.length > 0
        ? Object.keys(data.results[0]).map((k) => ({
            key: k,
            label: k.replace(/_/g, " ").replace(/\b\w/g, (c: string) => c.toUpperCase()),
            align: (k === "symbol" || k === "name" ? "left" : "right") as "left" | "right",
          }))
        : [];
      setColumns(cols);

      const errors = data.parse_errors.length ? ` | Errors: ${data.parse_errors.join(", ")}` : "";
      const infoStr = `${data.count} result(s) in ${data.elapsed_ms}ms${errors}`;
      setInfo(infoStr);
      setRanAt(new Date());

      // Cache the state
      setCache({ expression, results: data.results, columns: cols, info: infoStr });
    } catch {
      setInfo("Execution failed");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Screener"
        loadedAt={ranAt}
        loading={loading}
        onRefresh={results.length > 0 ? handleExecute : undefined}
      />

      <div className="flex gap-2">
        <input
          type="text"
          value={expression}
          onChange={(e) => setExpression(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleExecute()}
          placeholder="Filter: PE < 20, ROE > 15, Market Cap > 5000"
          className="flex-1 bg-surface border border-border rounded px-3 py-2 text-sm font-mono text-foreground outline-none focus:border-accent/50 placeholder:text-muted"
        />
        <button
          onClick={handleExecute}
          disabled={loading}
          className="px-4 py-2 bg-accent/10 text-accent border border-accent/30 rounded text-xs font-bold hover:bg-accent/20 transition-colors disabled:opacity-50"
        >
          {loading ? "Running..." : "Execute"}
        </button>
      </div>

      {info && <div className="text-[10px] text-muted">{info}</div>}

      <div className="text-[10px] text-muted space-y-1">
        <div>Examples: <code className="text-accent/80">Filter: PE &lt; 15, ROE &gt; 20</code> · <code className="text-accent/80">sales &gt; 50000</code> · <code className="text-accent/80">debt &lt; 0.5, NPM &gt; 10</code></div>
        <div>Concepts: sales, net profit, PAT, market cap, PE, ROE, ROCE, NPM, OPM, debt, borrowings, EPS, dividend yield, book value, P/B, promoters, FII, DII</div>
      </div>

      {results.length > 0 && <DataTable columns={columns} rows={results} />}
    </div>
  );
}

/** Hook to persist screener state in the cache context */
function useCachedScreenerState() {
  // Simple wrapper — uses window.__screenerCache for persistence across navigations
  const [state] = useState<ScreenerState | null>(() => {
    if (typeof window !== "undefined" && (window as unknown as Record<string, unknown>).__screenerCache) {
      return (window as unknown as Record<string, unknown>).__screenerCache as ScreenerState;
    }
    return null;
  });

  const set = useCallback((s: ScreenerState) => {
    if (typeof window !== "undefined") {
      (window as unknown as Record<string, unknown>).__screenerCache = s;
    }
  }, []);

  return { data: state, set };
}
