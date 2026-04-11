"use client";

import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

interface Observation {
  observation_id: number;
  data_point_ref: string;
  data_point_type: string;
  context_json: string;
  note: string;
  tags: string | null;
  created_at: string;
  updated_at: string;
}

export default function ObservationsPage() {
  const [observations, setObservations] = useState<Observation[]>([]);
  const [filter, setFilter] = useState<string>("");
  const [tagFilter, setTagFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchObservations();
  }, []);

  async function fetchObservations() {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "200" });
      if (tagFilter) params.set("tags", tagFilter);
      const data = await apiFetch<{ observations: Observation[] }>(`/api/observations?${params}`);
      setObservations(data.observations);
    } catch {
      setObservations([]);
    } finally {
      setLoading(false);
    }
  }

  const filtered = observations.filter((o) => {
    if (!filter) return true;
    const term = filter.toLowerCase();
    return (
      o.data_point_ref.toLowerCase().includes(term) ||
      o.note.toLowerCase().includes(term) ||
      (o.tags || "").toLowerCase().includes(term)
    );
  });

  // Group by data_point_type
  const grouped = filtered.reduce<Record<string, Observation[]>>((acc, o) => {
    const key = o.data_point_type;
    if (!acc[key]) acc[key] = [];
    acc[key].push(o);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xs font-bold text-accent uppercase tracking-wider">
          Observations ({filtered.length})
        </h1>
        <div className="flex gap-2">
          <a
            href="/api/export/observations?format=csv"
            target="_blank"
            className="text-[10px] text-muted border border-border rounded px-2 py-1 hover:text-accent hover:border-accent/50 transition-colors"
          >
            Export CSV
          </a>
          <a
            href="/api/export/observations"
            target="_blank"
            className="text-[10px] text-muted border border-border rounded px-2 py-1 hover:text-accent hover:border-accent/50 transition-colors"
          >
            Export JSON
          </a>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search observations..."
          className="flex-1 bg-surface border border-border rounded px-3 py-1.5 text-xs font-mono text-foreground outline-none focus:border-accent/50 placeholder:text-muted"
        />
        <input
          type="text"
          value={tagFilter}
          onChange={(e) => setTagFilter(e.target.value)}
          onBlur={fetchObservations}
          onKeyDown={(e) => e.key === "Enter" && fetchObservations()}
          placeholder="Filter by tag..."
          className="w-40 bg-surface border border-border rounded px-3 py-1.5 text-xs font-mono text-foreground outline-none focus:border-accent/50 placeholder:text-muted"
        />
      </div>

      {loading ? (
        <div className="text-muted text-xs text-center py-8">Loading...</div>
      ) : filtered.length === 0 ? (
        <div className="text-muted text-xs text-center py-8 border border-border rounded bg-surface">
          No observations yet. Tag data points from any page to start building your observation log.
        </div>
      ) : (
        Object.entries(grouped).map(([type, obs]) => (
          <section key={type} className="border border-border rounded bg-surface p-3">
            <h2 className="text-xs font-bold text-muted uppercase tracking-wider mb-3">
              {type} ({obs.length})
            </h2>
            <div className="space-y-2">
              {obs.map((o) => (
                <div
                  key={o.observation_id}
                  className="border-b border-border/30 pb-2 last:border-0 last:pb-0"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <span className="text-[10px] text-accent font-mono">{o.data_point_ref}</span>
                      <p className="text-xs text-foreground mt-0.5">{o.note}</p>
                      {o.tags && (
                        <div className="flex gap-1 mt-1">
                          {o.tags.split(",").map((tag) => (
                            <span
                              key={tag}
                              className="text-[9px] bg-accent/10 text-accent rounded px-1.5 py-0.5"
                            >
                              {tag.trim()}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <span className="text-[10px] text-muted ml-4 whitespace-nowrap">
                      {o.updated_at}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}
