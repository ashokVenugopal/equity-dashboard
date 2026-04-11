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

// ── Index endpoints ──

export interface Constituent {
  symbol: string;
  name: string;
  sort_order: number | null;
  close: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  trade_date: string | null;
  prev_close: number | null;
  change: number | null;
  change_pct: number | null;
}

export interface Mover {
  symbol: string;
  name: string;
  close: number;
  change_pct: number;
  mover_type: string;
}

export interface TechnicalRow {
  symbol: string;
  name: string;
  dma_50: number | null;
  dma_200: number | null;
  rsi_14: number | null;
  high_52w: number | null;
  low_52w: number | null;
  daily_change_pct: number | null;
}

export function getIndexConstituents(slug: string): Promise<{ index_name: string; constituents: Constituent[]; count: number }> {
  return apiFetch(`/api/index/${slug}/constituents`);
}

export function getIndexMovers(slug: string, limit = 5): Promise<{ index_name: string; gainers: Mover[]; losers: Mover[] }> {
  return apiFetch(`/api/index/${slug}/movers?limit=${limit}`);
}

export function getIndexTechnicals(slug: string): Promise<{ index_name: string; technicals: TechnicalRow[] }> {
  return apiFetch(`/api/index/${slug}/technicals`);
}

export function getIndexBreadth(slug: string): Promise<{ index_name: string; breadth: { advances: number; declines: number; unchanged: number; total: number } }> {
  return apiFetch(`/api/index/${slug}/breadth`);
}

// ── Instrument endpoints ──

export interface PriceBar {
  trade_date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number;
  adj_close: number | null;
  volume: number | null;
  delivery_qty: number | null;
}

export function getInstrumentPriceHistory(symbol: string, params?: { start_date?: string; limit?: number }): Promise<{ symbol: string; prices: PriceBar[]; count: number }> {
  const qs = new URLSearchParams();
  if (params?.start_date) qs.set("start_date", params.start_date);
  if (params?.limit) qs.set("limit", String(params.limit));
  return apiFetch(`/api/instrument/${symbol}/price-history?${qs}`);
}

// ── Derivatives endpoints ──

export interface PCRRow {
  instrument_symbol: string;
  trade_date: string;
  expiry_date: string;
  put_oi: number;
  call_oi: number;
  pcr: number | null;
}

export interface FIIPositioning {
  trade_date: string;
  participant_type: string;
  instrument_category: string;
  long_contracts: number;
  short_contracts: number;
  long_pct: number | null;
  short_pct: number | null;
}

export function getDerivativesPCR(instrument = "NIFTY", limit = 10): Promise<{ instrument: string; pcr_data: PCRRow[] }> {
  return apiFetch(`/api/derivatives/pcr?instrument=${instrument}&limit=${limit}`);
}

export function getDerivativesFIIPositioning(limit = 10): Promise<{ positioning: FIIPositioning[] }> {
  return apiFetch(`/api/derivatives/fii-positioning?limit=${limit}`);
}

export function getDerivativesOIChanges(instrument = "NIFTY"): Promise<{ instrument: string; oi_data: Record<string, unknown>[] }> {
  return apiFetch(`/api/derivatives/oi-changes?instrument=${instrument}`);
}

// ── Company endpoints ──

export interface CompanyMeta {
  company_id: number;
  symbol: string;
  name: string;
  isin: string;
  slug: string;
  fy_end_month: number;
  classifications: { classification_type: string; classification_name: string }[];
}

export interface FinancialConcept {
  concept_code: string;
  concept_name: string;
  unit: string;
  values: Record<string, number | null>;
}

export interface CompanyFinancials {
  symbol: string;
  statement_type: string;
  periods: string[];
  sections: Record<string, FinancialConcept[]>;
}

export function getCompanyMeta(symbol: string): Promise<CompanyMeta> {
  return apiFetch(`/api/company/${symbol}`);
}

export function getCompanyFinancials(symbol: string, section?: string): Promise<CompanyFinancials> {
  const qs = section ? `?section=${section}` : "";
  return apiFetch(`/api/company/${symbol}/financials${qs}`);
}

export function getCompanyRatios(symbol: string): Promise<{ symbol: string; periods: string[]; ratios: FinancialConcept[] }> {
  return apiFetch(`/api/company/${symbol}/ratios`);
}

export function getCompanyShareholding(symbol: string): Promise<{ symbol: string; periods: string[]; shareholding: FinancialConcept[] }> {
  return apiFetch(`/api/company/${symbol}/shareholding`);
}

export function getCompanyPeers(symbol: string): Promise<{ symbol: string; sector: string | null; peers: { symbol: string; name: string }[] }> {
  return apiFetch(`/api/company/${symbol}/peers`);
}

// ── Sectors endpoints ──

export interface SectorPerformanceRow {
  classification_name: string;
  compute_date: string;
  [timeframe: string]: string | number | null;
}

export function getSectorPerformance(type = "sector"): Promise<{ classification_type: string; metric: string; performance: SectorPerformanceRow[] }> {
  return apiFetch(`/api/sectors/performance?classification_type=${type}`);
}

export function getSectorConstituents(type: string, name: string): Promise<{ classification_type: string; name: string; constituents: Constituent[]; count: number }> {
  return apiFetch(`/api/sectors/${type}/${encodeURIComponent(name)}/constituents`);
}

// ── Search endpoints ──

export function searchCompanies(q: string): Promise<{ query: string; results: { symbol: string; name: string; isin: string }[]; count: number }> {
  return apiFetch(`/api/search/companies?q=${encodeURIComponent(q)}`);
}
