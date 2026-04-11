"""
Cell formatting rules for consistent data display.

Ported from equity-chatbased-interface/agent/answer_formatter.py.
These rules are the single source of truth for how values are displayed
in the dashboard. The frontend mirrors these in formatters.ts.
"""
from typing import Any

from equity_shared.rules import MONEY_DISPLAY

MONEY_COLS = frozenset({
    "value", "metric_value", "market_cap", "sales", "net_profit",
    "borrowings", "borrowings_value", "equity_value", "reserves_value",
    "buy_value", "sell_value", "net_value", "enterprise_value",
    "operating_profit", "other_income", "depreciation", "interest",
    "profit_before_tax", "tax", "cfo", "cfi", "cff", "net_cash_flow",
    "free_cash_flow", "total_assets", "total_liabilities",
})

PRICE_COLS = frozenset({
    "open", "high", "low", "close", "adj_close", "current_price",
    "last_price", "eps",
})

PCT_COLS = frozenset({
    "net_profit_margin", "npm", "opm", "roe", "roce",
    "sales_growth_3y", "sales_growth_3y_cagr", "sales_growth_recent",
    "gross_margin", "roic", "return_on_assets", "earnings_yield",
    "dividend_yield", "gnpa", "nnpa", "nim", "casa_ratio",
    "provision_coverage", "fcf_to_sales", "change_pct",
    "long_pct", "short_pct", "avg_return_pct", "median_return_pct",
    "daily_change_pct", "oi_change_pct",
})

RATIO_COLS = frozenset({
    "debt_to_equity_ratio", "debt_to_equity", "price_to_earning",
    "inventory_turnover", "price_to_book", "ev_ebitda", "peg_ratio",
    "price_to_sales", "price_to_fcf", "current_ratio", "quick_ratio",
    "interest_coverage", "asset_turnover", "equity_multiplier",
    "rsi_14", "volume_ratio", "pcr", "advance_decline_ratio",
})

VOLUME_COLS = frozenset({
    "volume", "delivery_qty", "volume_avg_20d",
    "long_contracts", "short_contracts",
    "open_interest", "change_in_oi",
    "advances", "declines", "unchanged",
    "new_52w_highs", "new_52w_lows",
})


def format_cell(col: str, val: Any) -> str:
    """Format a single cell value for display."""
    if val is None:
        return "—"
    if col in MONEY_COLS and isinstance(val, (int, float)):
        return f"{val:,.2f} {MONEY_DISPLAY}"
    if col in PRICE_COLS and isinstance(val, (int, float)):
        return f"{val:,.2f}"
    if col in PCT_COLS and isinstance(val, (int, float)):
        return f"{val:,.2f}%"
    if col in RATIO_COLS and isinstance(val, (int, float)):
        return f"{val:,.4f}"
    if col in VOLUME_COLS and isinstance(val, (int, float)):
        return f"{int(val):,}"
    if isinstance(val, float):
        if abs(val) < 0.01 and val != 0:
            return f"{val:.4f}"
        return f"{val:,.2f}"
    return str(val)


FRIENDLY_NAMES = {
    "symbol": "Symbol",
    "name": "Company",
    "concept_name": "Metric",
    "concept_code": "Metric Code",
    "value": "Value",
    "market_cap": "Market Cap (Cr)",
    "document_type": "Period Type",
    "fiscal_year": "Fiscal Year",
    "period_end_date": "Period End",
    "statement_type": "Statement",
    "open": "Open",
    "high": "High",
    "low": "Low",
    "close": "Close",
    "adj_close": "Adj Close",
    "volume": "Volume",
    "delivery_qty": "Delivery Qty",
    "trade_date": "Date",
    "instrument_name": "Instrument",
    "instrument_type": "Type",
    "classification_type": "Classification",
    "classification_name": "Name",
    "participant_type": "Participant",
    "segment": "Segment",
    "buy_value": "Buy (Cr)",
    "sell_value": "Sell (Cr)",
    "net_value": "Net (Cr)",
    "flow_date": "Date",
    "change_pct": "Change %",
    "advances": "Advances",
    "declines": "Declines",
    "advance_decline_ratio": "A/D Ratio",
    "new_52w_highs": "52W Highs",
    "new_52w_lows": "52W Lows",
}


def friendly_column_name(col: str) -> str:
    """Convert a column name to a human-friendly header."""
    return FRIENDLY_NAMES.get(col, col.replace("_", " ").title())
