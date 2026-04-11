"""
Tests for cell formatting rules.

Covers: money, price, percent, ratio, volume formatting,
edge cases (None, 0, negative, very small values).
"""
from backend.core.formatting import format_cell, friendly_column_name


# ── Money formatting ──

def test_format_cell_money_positive():
    result = format_cell("market_cap", 150000.50)
    assert "150,000.50" in result
    assert "Cr" in result


def test_format_cell_money_zero():
    assert format_cell("sales", 0.0) == "0.00 Cr"


def test_format_cell_money_negative():
    result = format_cell("net_value", -1500.0)
    assert "-1,500.00" in result
    assert "Cr" in result


def test_format_cell_money_none():
    assert format_cell("market_cap", None) == "—"


# ── Price formatting ──

def test_format_cell_price():
    assert format_cell("close", 22450.75) == "22,450.75"


def test_format_cell_price_zero():
    assert format_cell("close", 0.0) == "0.00"


# ── Percent formatting ──

def test_format_cell_percent():
    assert format_cell("npm", 12.34) == "12.34%"


def test_format_cell_percent_negative():
    assert format_cell("change_pct", -3.5) == "-3.50%"


# ── Ratio formatting ──

def test_format_cell_ratio():
    assert format_cell("debt_to_equity", 0.7512) == "0.7512"


def test_format_cell_ratio_large():
    assert format_cell("price_to_earning", 45.123) == "45.1230"


# ── Volume formatting ──

def test_format_cell_volume():
    assert format_cell("volume", 1234567) == "1,234,567"


def test_format_cell_volume_float():
    """Volume should be formatted as integer even if passed as float."""
    assert format_cell("volume", 1234567.0) == "1,234,567"


# ── Generic float ──

def test_format_cell_generic_float():
    assert format_cell("some_other", 1234.56) == "1,234.56"


def test_format_cell_very_small_float():
    """Very small non-zero floats use 4 decimal places."""
    result = format_cell("some_other", 0.0012)
    assert "0.0012" in result


# ── String and int ──

def test_format_cell_string():
    assert format_cell("symbol", "RELIANCE") == "RELIANCE"


def test_format_cell_integer():
    result = format_cell("some_count", 42)
    assert "42" in result


# ── Friendly column names ──

def test_friendly_column_name_known():
    assert friendly_column_name("symbol") == "Symbol"
    assert friendly_column_name("market_cap") == "Market Cap (Cr)"
    assert friendly_column_name("net_value") == "Net (Cr)"


def test_friendly_column_name_unknown():
    """Unknown columns get title-cased with underscores replaced."""
    assert friendly_column_name("some_custom_field") == "Some Custom Field"
