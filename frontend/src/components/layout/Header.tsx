"use client";

import { useState, useEffect, useRef } from "react";

export function Header() {
  const [cmdOpen, setCmdOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setCmdOpen(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (cmdOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [cmdOpen]);

  return (
    <header className="h-10 border-b border-border bg-surface flex items-center px-4 shrink-0">
      <div className="flex items-center gap-3 flex-1">
        <span className="text-accent font-bold text-sm tracking-wider">EQ</span>
        <span className="text-muted text-xs">EQUITY DASHBOARD</span>
      </div>

      {/* Command bar trigger */}
      <button
        onClick={() => setCmdOpen(true)}
        className="flex items-center gap-2 px-3 py-1 rounded border border-border text-muted text-xs hover:border-accent/50 transition-colors"
      >
        <span>Search / Command</span>
        <kbd className="bg-background px-1.5 py-0.5 rounded text-[10px] border border-border">
          ⌘K
        </kbd>
      </button>

      {/* Command bar overlay */}
      {cmdOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-50 flex items-start justify-center pt-[20vh]"
          onClick={() => setCmdOpen(false)}
        >
          <div
            className="bg-surface border border-border rounded-lg w-[560px] shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <input
              ref={inputRef}
              type="text"
              placeholder="Type a symbol, command, or filter... (e.g. Filter: PAT Growth > 20%)"
              className="w-full bg-transparent px-4 py-3 text-foreground text-sm outline-none placeholder:text-muted"
              onKeyDown={(e) => {
                if (e.key === "Escape") setCmdOpen(false);
              }}
            />
            <div className="border-t border-border px-4 py-2 text-muted text-xs">
              Navigate: type symbol · Filter: &quot;Filter: SME, Debt &lt; 0.5&quot; · Esc to close
            </div>
          </div>
        </div>
      )}
    </header>
  );
}
