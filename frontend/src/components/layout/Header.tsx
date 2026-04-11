"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { searchSuggestions, searchFilter } from "@/lib/api";

export function Header() {
  const [cmdOpen, setCmdOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<{ type: string; text: string; symbol?: string }[]>([]);
  const [filterResults, setFilterResults] = useState<Record<string, unknown>[] | null>(null);
  const [filterInfo, setFilterInfo] = useState<string | null>(null);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const router = useRouter();

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdOpen((prev) => !prev);
      }
      if (e.key === "Escape") setCmdOpen(false);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (cmdOpen && inputRef.current) {
      inputRef.current.focus();
      setQuery("");
      setSuggestions([]);
      setFilterResults(null);
      setFilterInfo(null);
      setSelectedIdx(0);
    }
  }, [cmdOpen]);

  const fetchSuggestions = useCallback(async (q: string) => {
    if (!q.trim()) {
      setSuggestions([{ type: "hint", text: "Type a symbol or filter (Filter: PE < 15, ROE > 20)" }]);
      return;
    }
    try {
      const data = await searchSuggestions(q);
      setSuggestions(data.suggestions);
      setSelectedIdx(0);
    } catch {
      setSuggestions([]);
    }
  }, []);

  function handleInputChange(val: string) {
    setQuery(val);
    setFilterResults(null);
    setFilterInfo(null);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchSuggestions(val), 150);
  }

  async function handleSubmit() {
    const q = query.trim();
    if (!q) return;

    // Check if it's a filter expression
    if (q.toLowerCase().startsWith("filter") || /[><=]/.test(q)) {
      try {
        const data = await searchFilter(q);
        setFilterResults(data.results);
        setFilterInfo(`${data.count} result(s) in ${data.elapsed_ms}ms${data.parse_errors.length ? ` · Errors: ${data.parse_errors.join(", ")}` : ""}`);
        setSuggestions([]);
      } catch {
        setFilterInfo("Filter execution failed");
      }
      return;
    }

    // Navigate to company if suggestion selected
    if (suggestions.length > 0 && suggestions[selectedIdx]?.type === "company" && suggestions[selectedIdx]?.symbol) {
      router.push(`/company/${suggestions[selectedIdx].symbol}`);
      setCmdOpen(false);
      return;
    }

    // Try direct symbol navigation
    router.push(`/company/${q.toUpperCase()}`);
    setCmdOpen(false);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") { setCmdOpen(false); return; }
    if (e.key === "Enter") { handleSubmit(); return; }
    if (e.key === "ArrowDown") { e.preventDefault(); setSelectedIdx((i) => Math.min(i + 1, suggestions.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setSelectedIdx((i) => Math.max(i - 1, 0)); }
  }

  return (
    <header className="h-10 border-b border-border bg-surface flex items-center px-4 shrink-0">
      <div className="flex items-center gap-3 flex-1">
        <span className="text-accent font-bold text-sm tracking-wider">EQ</span>
        <span className="text-muted text-xs">EQUITY DASHBOARD</span>
      </div>

      <button
        onClick={() => setCmdOpen(true)}
        className="flex items-center gap-2 px-3 py-1 rounded border border-border text-muted text-xs hover:border-accent/50 transition-colors"
      >
        <span>Search / Command</span>
        <kbd className="bg-background px-1.5 py-0.5 rounded text-[10px] border border-border">⌘K</kbd>
      </button>

      {cmdOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-50 flex items-start justify-center pt-[15vh]"
          onClick={() => setCmdOpen(false)}
        >
          <div
            className="bg-surface border border-border rounded-lg w-[600px] shadow-2xl max-h-[60vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => handleInputChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Symbol, filter, or command... (e.g. Filter: PE < 15, ROE > 20)"
              className="w-full bg-transparent px-4 py-3 text-foreground text-sm outline-none placeholder:text-muted font-mono"
            />

            {/* Suggestions */}
            {suggestions.length > 0 && !filterResults && (
              <div className="border-t border-border max-h-[200px] overflow-y-auto">
                {suggestions.map((s, i) => (
                  <div
                    key={i}
                    className={`px-4 py-2 text-xs font-mono cursor-pointer transition-colors ${
                      i === selectedIdx ? "bg-accent/10 text-accent" : "text-foreground hover:bg-surface-hover"
                    }`}
                    onClick={() => {
                      if (s.type === "company" && s.symbol) {
                        router.push(`/company/${s.symbol}`);
                        setCmdOpen(false);
                      }
                    }}
                  >
                    <span className="text-muted text-[10px] mr-2">{s.type}</span>
                    {s.text}
                  </div>
                ))}
              </div>
            )}

            {/* Filter results */}
            {filterResults && (
              <div className="border-t border-border max-h-[300px] overflow-y-auto">
                {filterInfo && (
                  <div className="px-4 py-1 text-[10px] text-muted border-b border-border/50">{filterInfo}</div>
                )}
                {filterResults.length > 0 ? (
                  filterResults.slice(0, 20).map((r, i) => (
                    <div
                      key={i}
                      className="px-4 py-1.5 text-xs font-mono hover:bg-surface-hover cursor-pointer flex items-center gap-3"
                      onClick={() => {
                        router.push(`/company/${r.symbol}`);
                        setCmdOpen(false);
                      }}
                    >
                      <span className="text-accent font-bold w-20">{String(r.symbol)}</span>
                      <span className="text-foreground">{String(r.name)}</span>
                      {Object.entries(r)
                        .filter(([k]) => k !== "symbol" && k !== "name")
                        .map(([k, v]) => (
                          <span key={k} className="text-muted">
                            {k}: {typeof v === "number" ? v.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : String(v)}
                          </span>
                        ))}
                    </div>
                  ))
                ) : (
                  <div className="px-4 py-3 text-xs text-muted text-center">No matches</div>
                )}
              </div>
            )}

            <div className="border-t border-border px-4 py-1.5 text-muted text-[10px] flex gap-4">
              <span>↑↓ Navigate</span>
              <span>↵ Select / Execute</span>
              <span>Esc Close</span>
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
