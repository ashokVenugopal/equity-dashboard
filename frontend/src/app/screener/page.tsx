"use client";

import { useState } from "react";
import { searchFilter } from "@/lib/api";
import { DataTable } from "@/components/tables/DataTable";
import { useRouter } from "next/navigation";

export default function ScreenerPage() {
  const [expression, setExpression] = useState("Filter: PE < 20, ROE > 15");
  const [results, setResults] = useState<Record<string, unknown>[]>([]);
  const [columns, setColumns] = useState<{ key: string; label: string; align?: "left" | "right" }[]>([]);
  const [info, setInfo] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleExecute() {
    setLoading(true);
    try {
      const data = await searchFilter(expression);
      setResults(data.results);

      // Build columns from results
      if (data.results.length > 0) {
        const keys = Object.keys(data.results[0]);
        setColumns(keys.map((k) => ({
          key: k,
          label: k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
          align: k === "symbol" || k === "name" ? "left" as const : "right" as const,
        })));
      }

      const errors = data.parse_errors.length ? ` | Errors: ${data.parse_errors.join(", ")}` : "";
      setInfo(`${data.count} result(s) in ${data.elapsed_ms}ms${errors}`);
    } catch (e) {
      setInfo("Execution failed");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xs font-bold text-accent uppercase tracking-wider">
        Screener
      </h1>

      {/* Input */}
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

      {/* Info */}
      {info && (
        <div className="text-[10px] text-muted">{info}</div>
      )}

      {/* Hints */}
      <div className="text-[10px] text-muted space-y-1">
        <div>Examples: <code className="text-accent/80">Filter: PE &lt; 15, ROE &gt; 20</code> · <code className="text-accent/80">sales &gt; 50000</code> · <code className="text-accent/80">debt &lt; 0.5, NPM &gt; 10</code></div>
        <div>Concepts: sales, net profit, PAT, market cap, PE, ROE, ROCE, NPM, OPM, debt, borrowings, EPS, dividend yield, book value, P/B, promoters, FII, DII</div>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <DataTable columns={columns} rows={results} />
      )}
    </div>
  );
}
