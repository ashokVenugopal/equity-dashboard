"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { searchFilter, apiFetch } from "@/lib/api";
import { DataTable } from "@/components/tables/DataTable";
import { PageHeader } from "@/components/shared/PageHeader";

interface ScreenerState {
  expression: string;
  results: Record<string, unknown>[];
  columns: { key: string; label: string; align?: "left" | "right" }[];
  info: string;
}

interface ConceptSuggestion {
  alias: string;
  code: string;
}

export default function ScreenerPage() {
  const cached = useCachedScreenerState();
  const [expression, setExpression] = useState(cached.data?.expression || "");
  const [results, setResults] = useState<Record<string, unknown>[]>(cached.data?.results || []);
  const [columns, setColumns] = useState(cached.data?.columns || []);
  const [info, setInfo] = useState(cached.data?.info || "");
  const [loading, setLoading] = useState(false);
  const [ranAt, setRanAt] = useState<Date | null>(cached.data ? new Date() : null);

  // Concept suggestions
  const [suggestions, setSuggestions] = useState<ConceptSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedSuggIdx, setSelectedSuggIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  async function handleExecute() {
    if (!expression.trim()) return;
    setLoading(true);
    setShowSuggestions(false);
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
      cached.set({ expression, results: data.results, columns: cols, info: infoStr });
    } catch {
      setInfo("Execution failed");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  function handleInputChange(val: string) {
    setExpression(val);

    // Extract the last concept being typed (after last comma or "Filter:")
    const lastPart = val.split(",").pop()?.trim() || "";
    const conceptPart = lastPart.replace(/^filter:\s*/i, "").replace(/[><=!]\s*[\d.]*$/, "").trim();

    if (conceptPart.length >= 1) {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(async () => {
        try {
          const data = await apiFetch<{ concepts: ConceptSuggestion[] }>(
            `/api/search/concepts?q=${encodeURIComponent(conceptPart)}`
          );
          setSuggestions(data.concepts);
          setShowSuggestions(data.concepts.length > 0);
          setSelectedSuggIdx(0);
        } catch {
          setSuggestions([]);
          setShowSuggestions(false);
        }
      }, 150);
    } else {
      setShowSuggestions(false);
    }
  }

  function insertConcept(alias: string) {
    // Replace the last partial concept with the selected alias
    const parts = expression.split(",");
    const lastPart = parts.pop() || "";
    const beforeOp = lastPart.replace(/[><=!]\s*[\d.]*$/, "");
    const afterPrefix = lastPart.replace(/^filter:\s*/i, "");
    const prefix = lastPart.slice(0, lastPart.length - afterPrefix.length);
    const operator = lastPart.slice(beforeOp.length);

    parts.push(`${prefix}${alias}${operator || " > "}`);
    const newExpr = parts.join(", ");
    setExpression(newExpr);
    setShowSuggestions(false);
    inputRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (showSuggestions && suggestions.length > 0) {
      if (e.key === "ArrowDown") { e.preventDefault(); setSelectedSuggIdx((i) => Math.min(i + 1, suggestions.length - 1)); return; }
      if (e.key === "ArrowUp") { e.preventDefault(); setSelectedSuggIdx((i) => Math.max(i - 1, 0)); return; }
      if (e.key === "Tab" || (e.key === "Enter" && showSuggestions)) {
        e.preventDefault();
        insertConcept(suggestions[selectedSuggIdx].alias);
        return;
      }
      if (e.key === "Escape") { setShowSuggestions(false); return; }
    }
    if (e.key === "Enter") handleExecute();
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Screener"
        loadedAt={ranAt}
        loading={loading}
        onRefresh={results.length > 0 ? handleExecute : undefined}
        dataType="fundamental"
      />

      <div className="relative">
        <div className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={expression}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
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

        {/* Concept suggestions dropdown */}
        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute z-10 top-full left-0 mt-1 bg-surface border border-border rounded shadow-xl max-h-[240px] overflow-y-auto w-[400px]">
            {suggestions.map((s, i) => (
              <div
                key={s.code}
                className={`px-3 py-1.5 text-xs font-mono cursor-pointer flex justify-between ${
                  i === selectedSuggIdx ? "bg-accent/10 text-accent" : "text-foreground hover:bg-surface-hover"
                }`}
                onMouseDown={() => insertConcept(s.alias)}
              >
                <span>{s.alias}</span>
                <span className="text-muted text-[10px]">{s.code}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {info && <div className="text-[10px] text-muted">{info}</div>}

      <div className="text-[10px] text-muted space-y-1">
        <div>Type a concept name to see suggestions · Tab/Enter to select · Comma to add more conditions</div>
        <div>Examples: <code className="text-accent/80">PE &lt; 15, ROE &gt; 20</code> · <code className="text-accent/80">sales &gt; 50000, debt &lt; 0.5</code> · <code className="text-accent/80">peg &lt; 1, npm &gt; 10</code></div>
      </div>

      {results.length > 0 && <DataTable columns={columns} rows={results} />}
    </div>
  );
}

function useCachedScreenerState() {
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
