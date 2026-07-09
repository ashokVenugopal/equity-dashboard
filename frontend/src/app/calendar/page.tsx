"use client";

import { useCallback, useState } from "react";
import { getMacroEvents, type CalendarEvent } from "@/lib/api";
import { PageHeader } from "@/components/shared/PageHeader";
import { useCachedData } from "@/lib/cache";

/*
 * Risk Calendar: FOMC / RBI decisions, US jobs prints, results dates and
 * corporate actions for tracked stocks, and IPO windows — refreshed daily
 * by the pipeline (seed-macro-events + download-calendar).
 */

const CATEGORY_META: Record<string, { label: string; cls: string }> = {
  fomc: { label: "FOMC", cls: "border-negative/60 text-negative" },
  rbi_mpc: { label: "RBI", cls: "border-accent/60 text-accent" },
  us_jobs: { label: "US Jobs", cls: "border-muted/60 text-muted" },
  results: { label: "Results", cls: "border-positive/60 text-positive" },
  corp_action: { label: "Corp Action", cls: "border-[#FFD700]/60 text-[#FFD700]" },
  ipo: { label: "IPO", cls: "border-[#AB47BC]/60 text-[#AB47BC]" },
};

const ALL_CATEGORIES = Object.keys(CATEGORY_META);

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function fmtDay(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return `${WEEKDAYS[d.getDay()]} ${iso}`;
}

export default function CalendarPage() {
  const [active, setActive] = useState<string[]>(ALL_CATEGORIES);

  const fetcher = useCallback(() => getMacroEvents(60, 3), []);
  const { data, loading, loadedAt, refresh, error } = useCachedData(
    "risk-calendar", fetcher, 15 * 60 * 1000);

  if (error && !data) {
    return <div className="text-negative text-xs border border-negative/30 rounded p-3 bg-negative/5">{error}</div>;
  }
  if (!data) {
    return <div className="text-muted text-xs py-8 text-center">Loading Risk Calendar...</div>;
  }

  const todayIso = new Date().toISOString().slice(0, 10);
  const toggle = (c: string) =>
    setActive((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));

  const days = data.days
    .map((d) => ({ ...d, events: d.events.filter((e) => active.includes(e.category)) }))
    .filter((d) => d.events.length > 0);

  return (
    <div className="space-y-4">
      <PageHeader title="Risk Calendar" loadedAt={loadedAt} loading={loading} onRefresh={refresh} />

      {/* Category filter chips */}
      <div className="flex flex-wrap gap-2">
        {ALL_CATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => toggle(c)}
            className={`text-[11px] px-2 py-0.5 rounded border font-mono ${
              active.includes(c) ? CATEGORY_META[c].cls : "border-border text-muted/50"
            }`}
          >
            {CATEGORY_META[c].label}
          </button>
        ))}
        <span className="text-[10px] text-muted self-center ml-2">
          {data.total} events · next 60 days · RBI dates marked “tentative” until the official
          schedule is seeded (seeds/market_events.csv)
        </span>
      </div>

      {/* Day-grouped event list */}
      <div className="space-y-2">
        {days.map((day) => (
          <section
            key={day.date}
            className={`border rounded bg-surface p-3 ${
              day.date === todayIso ? "border-accent" : "border-border"
            }`}
          >
            <div className="flex items-baseline gap-2 mb-2">
              <h2 className="text-[12px] font-mono font-bold text-foreground">{fmtDay(day.date)}</h2>
              {day.date === todayIso && (
                <span className="text-[10px] text-accent uppercase">today</span>
              )}
            </div>
            <ul className="space-y-1">
              {day.events.map((e: CalendarEvent, i: number) => (
                <li key={i} className="flex items-start gap-2 text-[11px] font-mono">
                  <span
                    className={`shrink-0 text-[10px] px-1.5 rounded border ${CATEGORY_META[e.category]?.cls || "border-border text-muted"}`}
                  >
                    {CATEGORY_META[e.category]?.label || e.category}
                  </span>
                  <span className="text-foreground">{e.title}</span>
                  {e.detail && <span className="text-muted truncate max-w-96">— {e.detail}</span>}
                </li>
              ))}
            </ul>
          </section>
        ))}
        {days.length === 0 && (
          <p className="text-muted text-xs py-6 text-center">No events for the selected filters.</p>
        )}
      </div>
    </div>
  );
}
