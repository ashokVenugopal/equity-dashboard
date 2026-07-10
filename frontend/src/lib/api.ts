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
  change_pct_1w: number | null;
  change_pct_1m: number | null;
  change_pct_1y: number | null;
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

export interface DataFreshness {
  last_trading_day: string | null;
  last_price_ingest: string | null;
  last_index_price: string | null;
  last_fundamental_ingest: string | null;
  last_flow_date: string | null;
}

export function getDataFreshness(): Promise<DataFreshness> {
  return apiFetch("/api/data-freshness");
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

export function getDerivativesFIIPositioning(
  limit = 40,
  participants: string[] = ["FII", "CLIENT"],
): Promise<{ positioning: FIIPositioning[] }> {
  const pts = encodeURIComponent(participants.join(","));
  return apiFetch(`/api/derivatives/fii-positioning?limit=${limit}&participants=${pts}`);
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

export interface RiskGauge {
  floor: number;
  peak: number;
  current: number;
  current_date: string;
  altitude_pct: number;
  trend: { date: string; value: number }[];
}

export interface AttributionRow {
  window: string;
  available: boolean;
  eps_source?: "ttm" | "annual";
  price_change_pct?: number;
  earnings_change_pct?: number | null;
  multiple_change_pct?: number | null;
  earnings_share_pct?: number | null;
  multiple_share_pct?: number | null;
}

export interface CompanyRiskReward {
  symbol: string;
  pe: RiskGauge | null;
  ev_ebitda: RiskGauge | null;
  ocf_pat: RiskGauge | null;
  attribution: AttributionRow[];
}

export function getCompanyRiskReward(symbol: string): Promise<CompanyRiskReward> {
  return apiFetch(`/api/company/${symbol}/risk-reward`);
}

// ── Index history (/indices page) ──

export interface IndexCatalog {
  instruments: Record<string, { symbol: string; name: string; exchange: string | null }[]>;
  baskets: { classification_type: string; classification_name: string; members: number }[];
}

export interface OverlaySeries {
  symbol: string;
  name: string;
  instrument_type: string;
  /** First close in the window — the rebasing base (null if no data). */
  base: number | null;
  points: { time: string; value: number }[];
}

export interface RangeHL {
  high: number;
  low: number;
  off_high_pct: number;
  off_low_pct: number;
}

export interface IndexStatsRow {
  symbol: string;
  name?: string;
  instrument_type?: string;
  available: boolean;
  last?: number;
  last_date?: string;
  first_date?: string;
  w52?: RangeHL;
  y3?: RangeHL;
  alltime?: RangeHL;
}

export function getIndexHistoryCatalog(): Promise<IndexCatalog> {
  return apiFetch(`/api/index-history/catalog`);
}

export function getIndexHistorySeries(
  symbols: string[], range = "3y", normalize = true,
): Promise<{ range: string; normalized: boolean; series: OverlaySeries[] }> {
  return apiFetch(
    `/api/index-history/series?symbols=${encodeURIComponent(symbols.join(","))}&range=${range}&normalize=${normalize}`);
}

export function getIndexHistoryStats(symbols: string[]): Promise<{ stats: IndexStatsRow[] }> {
  return apiFetch(`/api/index-history/stats?symbols=${encodeURIComponent(symbols.join(","))}`);
}

// ── Macro (liquidity + risk calendar) ──

export interface MacroSeries {
  code: string;
  points: { time: string; value: number }[];
}

export interface CalendarEvent {
  category: string;
  title: string;
  country: string | null;
  symbol: string | null;
  detail: string | null;
}

export function getMacroSeries(
  codes: string[], transform: "none" | "yoy" = "none", start = "2015-01-01",
): Promise<{ transform: string; series: MacroSeries[] }> {
  return apiFetch(
    `/api/macro/series?codes=${encodeURIComponent(codes.join(","))}&transform=${transform}&start=${start}`);
}

export function getMacroEvents(
  daysAhead = 45, daysBack = 7, categories: string[] = [],
): Promise<{ days: { date: string; events: CalendarEvent[] }[]; total: number }> {
  const cats = categories.length ? `&categories=${encodeURIComponent(categories.join(","))}` : "";
  return apiFetch(`/api/macro/events?days_ahead=${daysAhead}&days_back=${daysBack}${cats}`);
}

export interface CustomIndex {
  id: number;
  name: string;
  symbols: string[];
  updated_at?: string;
}

export function getCustomIndices(): Promise<{ custom_indices: CustomIndex[] }> {
  return apiFetch(`/api/index-history/custom`);
}

export function createCustomIndex(name: string, symbols: string[]): Promise<CustomIndex> {
  return apiFetch(`/api/index-history/custom`, {
    method: "POST",
    body: JSON.stringify({ name, symbols }),
  });
}

export function updateCustomIndex(id: number, name: string, symbols: string[]): Promise<CustomIndex> {
  return apiFetch(`/api/index-history/custom/${id}`, {
    method: "PUT",
    body: JSON.stringify({ name, symbols }),
  });
}

export function deleteCustomIndex(id: number): Promise<{ deleted: number }> {
  return apiFetch(`/api/index-history/custom/${id}`, { method: "DELETE" });
}

export function getCustomIndexSeries(
  id: number, range = "3y",
): Promise<{ id: number; name: string; members_used: number; points: { time: string; value: number }[] }> {
  return apiFetch(`/api/index-history/custom/${id}/series?range=${range}`);
}

export interface VolumeProfile {
  symbol: string;
  available: boolean;
  reason?: string;
  days?: number;
  approx?: boolean;
  poc?: number;
  vah?: number;
  val?: number;
}

export function getVolumeProfile(symbol: string, from: string, to: string): Promise<VolumeProfile> {
  return apiFetch(`/api/index-history/volume-profile?symbol=${encodeURIComponent(symbol)}&from=${from}&to=${to}`);
}

export function getIndexHistoryBasket(
  classificationType: string, name: string, range = "3y",
): Promise<{ name: string; members_used: number; points: { time: string; value: number }[] }> {
  return apiFetch(
    `/api/index-history/basket?classification_type=${encodeURIComponent(classificationType)}&name=${encodeURIComponent(name)}&range=${range}`);
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

export function searchFilter(expression: string, limit = 50): Promise<{
  expression: string;
  parsed_conditions: { concept_code: string; op: string; value: number; raw: string; unit?: string }[];
  parse_errors: string[];
  results: Record<string, unknown>[];
  count: number;
  elapsed_ms: number;
}> {
  return apiFetch("/api/search/filter", {
    method: "POST",
    body: JSON.stringify({ expression, limit }),
  });
}

export function searchSuggestions(q: string): Promise<{ query: string; suggestions: { type: string; text: string; symbol?: string; code?: string }[] }> {
  return apiFetch(`/api/search/suggestions?q=${encodeURIComponent(q)}`);
}

// ── Heatmap endpoints ──

export interface HeatmapBlock {
  symbol: string;
  name: string;
  market_cap: number | null;
  close: number | null;
  change_pct: number | null;
}

export function getHeatmap(index: string): Promise<{ index_name: string; blocks: HeatmapBlock[] }> {
  return apiFetch(`/api/heatmap/${index}`);
}

// ── FundFlow endpoints ──

export function getFundFlowSummary(): Promise<Record<string, unknown>> {
  return apiFetch("/api/fundflow/summary");
}

export function getFundFlowDaily(segment = "CASH", limit = 30): Promise<{ segment: string; flows: Record<string, unknown>[] }> {
  return apiFetch(`/api/fundflow/daily?segment=${segment}&limit=${limit}`);
}

export function getFundFlowMonthly(segment = "CASH", limit = 24): Promise<{ segment: string; flows: Record<string, unknown>[] }> {
  return apiFetch(`/api/fundflow/monthly?segment=${segment}&limit=${limit}`);
}

export function getFundFlowYearly(): Promise<{ flows: Record<string, unknown>[] }> {
  return apiFetch("/api/fundflow/yearly");
}

export function getFundFlowDetailed(
  timeframe = "daily", view = "cash_provisional", foSub?: string, limit = 30,
): Promise<{ timeframe: string; view: string; aggregations: Record<string, unknown>[]; rows: Record<string, unknown>[] }> {
  const params = new URLSearchParams({ timeframe, view, limit: String(limit) });
  if (foSub) params.set("fo_sub", foSub);
  return apiFetch(`/api/fundflow/detailed?${params}`);
}

// ── Index Detail endpoints ──

export function getIndexDetailOverview(slug: string): Promise<Record<string, unknown>> {
  return apiFetch(`/api/index-detail/${slug}/overview`);
}

export function getIndexDetailTable(slug: string, view = "overview"): Promise<{ index_name: string; view: string; rows: Record<string, unknown>[]; count: number }> {
  return apiFetch(`/api/index-detail/${slug}/table?view=${view}`);
}

export interface IndexPerformanceItem {
  key: string;
  label: string;
  change_pct: number | null;
  advances?: number;
  declines?: number;
  total?: number;
}

export interface IndexStats {
  index_name: string;
  performance: IndexPerformanceItem[];
  technicals: Record<string, number | null>;
  support_resistance: Record<string, number | null>;
  price_ranges?: Record<string, number | null>;
}

export function getIndexDetailStats(slug: string): Promise<IndexStats> {
  return apiFetch(`/api/index-detail/${slug}/stats`);
}

// ── Global endpoints ──

export function getGlobalOverview(): Promise<{ groups: Record<string, GlobalInstrument[]>; total: number }> {
  return apiFetch("/api/global/overview");
}

// ── Investors (superstar portfolios) ──

export interface InvestorRow {
  id: number;
  trendlyne_id: number;
  name: string;
  slug: string;
  categories: string[];
  holdings_latest: number;
  changes_latest: { new: number; exit: number; add: number; trim: number };
}

export interface InvestorChange {
  investor_id: number;
  investor: string;
  categories: string[];
  stock_name: string;
  nse_code: string | null;
  tracked: boolean;
  sector: string | null;
  kind: "new" | "exit" | "add" | "trim";
  prev_pct: number | null;
  cur_pct: number | null;
  delta: number;
}

export interface MatrixCellEntry {
  investor: string;
  investor_id: number;
  pct: number;
  flag: string | null;
  stock: string | null;
}

export interface InvestorHoldingRow {
  stock_name: string;
  nse_code: string | null;
  tracked: boolean;
  quarters: Record<string, number | null>;
  latest_change: string | null;
}

export interface InvestorGroup {
  id: number;
  name: string;
  member_ids: number[];
}

export interface GroupHoldingRow {
  stock_name: string;
  nse_code: string | null;
  tracked: boolean;
  quarters: Record<string, number>;
  members: Record<string, Record<string, number>>;
  holders_latest: number;
}

export function getInvestorsList(category = ""): Promise<{ investors: InvestorRow[]; quarters: string[] }> {
  return apiFetch(`/api/investors/list?category=${category}`);
}

export function getInvestorChanges(quarter = "", kind = "", category = ""):
  Promise<{ changes: InvestorChange[]; quarter: string | null; prior?: string; quarters: string[] }> {
  return apiFetch(`/api/investors/changes?quarter=${quarter}&kind=${kind}&category=${category}`);
}

export function getInvestorMatrix(by: "sector" | "stock" = "sector", quartersCount = 8, category = "", minPct = 0):
  Promise<{ rows: { row: string; cells: Record<string, MatrixCellEntry[]> }[]; quarters: string[]; by: string }> {
  return apiFetch(`/api/investors/matrix?by=${by}&quarters_count=${quartersCount}&category=${category}&min_pct=${minPct}`);
}

export function getMissingCompanies():
  Promise<{ missing: { stock_name: string; nse_code: string | null; holders: number; holders_latest: number; last_seen: string }[]; latest_quarter: string | null }> {
  return apiFetch(`/api/investors/missing-companies`);
}

export function getInvestorHoldings(id: number):
  Promise<{ investor: { investor_id: number; name: string; categories: string }; quarters: string[]; holdings: InvestorHoldingRow[] }> {
  return apiFetch(`/api/investors/${id}/holdings`);
}

export function getInvestorGroups(): Promise<{ groups: InvestorGroup[] }> {
  return apiFetch(`/api/investors/groups`);
}

export function createInvestorGroup(name: string, memberIds: number[]): Promise<InvestorGroup> {
  return apiFetch(`/api/investors/groups`, { method: "POST", body: JSON.stringify({ name, member_ids: memberIds }) });
}

export function updateInvestorGroup(id: number, name: string, memberIds: number[]): Promise<InvestorGroup> {
  return apiFetch(`/api/investors/groups/${id}`, { method: "PUT", body: JSON.stringify({ name, member_ids: memberIds }) });
}

export function deleteInvestorGroup(id: number): Promise<{ deleted: number }> {
  return apiFetch(`/api/investors/groups/${id}`, { method: "DELETE" });
}

export function getGroupHoldings(id: number, mode: "consolidated" | "overlap" = "consolidated"):
  Promise<{ group: string; mode: string; quarters: string[]; holdings: GroupHoldingRow[] }> {
  return apiFetch(`/api/investors/groups/${id}/holdings?mode=${mode}`);
}
