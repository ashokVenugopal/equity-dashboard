/**
 * Typed API client for the FastAPI backend.
 * Used by both server components (SSR) and client components.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${res.statusText}`);
  }
  return res.json();
}

// ── Market endpoints ──

export interface IndexCard {
  symbol: string;
  name: string;
  close: number;
  trade_date: string;
  open: number;
  high: number;
  low: number;
  volume: number;
  prev_close: number | null;
  prev_date: string | null;
  change: number | null;
  change_pct: number | null;
}

export interface Flow {
  flow_date: string;
  participant_type: string;
  segment: string;
  buy_value: number | null;
  sell_value: number | null;
  net_value: number | null;
}

export interface Breadth {
  trade_date: string;
  advances: number;
  declines: number;
  unchanged: number;
  advance_decline_ratio: number;
  new_52w_highs: number;
  new_52w_lows: number;
}

export interface GlobalInstrument {
  instrument_type: string;
  symbol: string;
  name: string;
  currency: string;
  close: number | null;
  trade_date: string | null;
  open: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
}

export interface MarketOverview {
  indices: IndexCard[];
  flows: Flow[];
  breadth: Breadth | null;
}

export function getMarketOverview(): Promise<MarketOverview> {
  return apiFetch("/api/market/overview");
}

export function getMarketFlows(params?: { participant_type?: string; limit?: number }): Promise<{ flows: Flow[] }> {
  const qs = new URLSearchParams();
  if (params?.participant_type) qs.set("participant_type", params.participant_type);
  if (params?.limit) qs.set("limit", String(params.limit));
  return apiFetch(`/api/market/flows?${qs}`);
}

export function getMarketBreadth(limit = 10): Promise<{ breadth: Breadth[] }> {
  return apiFetch(`/api/market/breadth?limit=${limit}`);
}

export function getMarketGlobal(): Promise<{ instruments: GlobalInstrument[] }> {
  return apiFetch("/api/market/global");
}

export function getHealth(): Promise<Record<string, unknown>> {
  return apiFetch("/api/health");
}
