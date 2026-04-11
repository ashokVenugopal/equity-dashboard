"use client";

import { useState, useMemo } from "react";
import { formatCell } from "@/lib/formatters";

interface DataTableProps {
  columns: { key: string; label: string; align?: "left" | "right" }[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  rows: any[];
  compact?: boolean;
}

type SortDir = "asc" | "desc";

export function DataTable({ columns, rows, compact = false }: DataTableProps) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => {
    if (!sortKey) return rows;
    return [...rows].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];
      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;
      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDir === "asc" ? aVal - bVal : bVal - aVal;
      }
      return sortDir === "asc"
        ? String(aVal).localeCompare(String(bVal))
        : String(bVal).localeCompare(String(aVal));
    });
  }, [rows, sortKey, sortDir]);

  function handleSort(key: string) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  const py = compact ? "py-1" : "py-1.5";
  const px = compact ? "px-2" : "px-3";

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse font-mono text-xs">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => handleSort(col.key)}
                className={`
                  ${px} ${py} font-medium text-muted cursor-pointer select-none
                  hover:text-foreground hover:bg-surface-hover transition-colors whitespace-nowrap
                  ${col.align === "right" ? "text-right" : "text-left"}
                `}
              >
                {col.label}
                {sortKey === col.key && (
                  <span className="ml-1 text-accent">
                    {sortDir === "asc" ? "▲" : "▼"}
                  </span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, i) => (
            <tr
              key={i}
              className="border-b border-border/50 hover:bg-surface-hover transition-colors"
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={`
                    ${px} ${py} whitespace-nowrap tabular-nums
                    ${col.align === "right" ? "text-right" : "text-left"}
                  `}
                >
                  {formatCell(col.key, row[col.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {sorted.length === 0 && (
        <div className="text-center text-muted py-8 text-xs">No data</div>
      )}
    </div>
  );
}
