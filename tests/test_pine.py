"""
Tests for Pine Script engine: lexer, parser, compiler, runtime.

Covers: tokenization, AST generation, compilation, indicator computation,
edge cases (empty script, unknown function, division by zero), end-to-end.
"""
import pytest
import numpy as np

from backend.pine.lexer import tokenize, TokenType
from backend.pine.parser import Parser, Assignment, FunctionCall, BinaryOp, NumberLiteral, Identifier
from backend.pine.compiler import compile_ast, BUILTINS
from backend.pine.runtime import execute


# ── Lexer tests ──

def test_lexer_assignment():
    tokens = tokenize("x = 42")
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.NUMBER]


def test_lexer_function_call():
    tokens = tokenize("sma(close, 20)")
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.IDENTIFIER, TokenType.LPAREN, TokenType.IDENTIFIER,
                     TokenType.COMMA, TokenType.NUMBER, TokenType.RPAREN]


def test_lexer_arithmetic():
    tokens = tokenize("a + b * 2")
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.IDENTIFIER, TokenType.PLUS, TokenType.IDENTIFIER,
                     TokenType.STAR, TokenType.NUMBER]


def test_lexer_comparison():
    tokens = tokenize("a >= b")
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.IDENTIFIER, TokenType.GTE, TokenType.IDENTIFIER]


def test_lexer_comment():
    tokens = tokenize("x = 1 // this is a comment\ny = 2")
    ids = [t.value for t in tokens if t.type == TokenType.IDENTIFIER]
    assert ids == ["x", "y"]


def test_lexer_version_directive():
    tokens = tokenize("//@version=1\nx = close")
    ids = [t.value for t in tokens if t.type == TokenType.IDENTIFIER]
    assert ids == ["x", "close"]


def test_lexer_unexpected_char():
    with pytest.raises(SyntaxError, match="Unexpected character"):
        tokenize("x = @")


# ── Parser tests ──

def test_parser_simple_assignment():
    tokens = tokenize("x = 42")
    stmts = Parser(tokens).parse()
    assert len(stmts) == 1
    assert isinstance(stmts[0], Assignment)
    assert stmts[0].name == "x"
    assert isinstance(stmts[0].expr, NumberLiteral)
    assert stmts[0].expr.value == 42.0


def test_parser_function_call():
    tokens = tokenize("sma20 = sma(close, 20)")
    stmts = Parser(tokens).parse()
    assert len(stmts) == 1
    assert stmts[0].name == "sma20"
    assert isinstance(stmts[0].expr, FunctionCall)
    assert stmts[0].expr.name == "sma"
    assert len(stmts[0].expr.args) == 2


def test_parser_binary_ops():
    tokens = tokenize("diff = close - open")
    stmts = Parser(tokens).parse()
    assert isinstance(stmts[0].expr, BinaryOp)
    assert stmts[0].expr.op == "-"


def test_parser_multiple_statements():
    tokens = tokenize("a = sma(close, 20)\nb = sma(close, 50)")
    stmts = Parser(tokens).parse()
    assert len(stmts) == 2


def test_parser_nested_expression():
    tokens = tokenize("x = (close + open) / 2")
    stmts = Parser(tokens).parse()
    assert isinstance(stmts[0].expr, BinaryOp)
    assert stmts[0].expr.op == "/"


# ── Compiler tests ──

def test_compiler_simple():
    tokens = tokenize("sma20 = sma(close, 20)")
    stmts = Parser(tokens).parse()
    ops = compile_ast(stmts)
    assert len(ops) >= 1
    builtin_ops = [o for o in ops if o.op_type == "builtin"]
    assert len(builtin_ops) == 1
    assert builtin_ops[0].func == "sma"


def test_compiler_unknown_function():
    tokens = tokenize("x = unknown_func(close, 20)")
    stmts = Parser(tokens).parse()
    with pytest.raises(NameError, match="Unknown function"):
        compile_ast(stmts)


def test_compiler_undefined_variable():
    tokens = tokenize("x = undefined_var + 1")
    stmts = Parser(tokens).parse()
    with pytest.raises(NameError, match="Undefined variable"):
        compile_ast(stmts)


def test_compiler_wrong_arg_count():
    tokens = tokenize("x = sma(close)")
    stmts = Parser(tokens).parse()
    with pytest.raises(TypeError, match="expects 2 args"):
        compile_ast(stmts)


# ── Runtime tests ──

_SAMPLE_PRICES = [
    {"trade_date": f"2026-01-{i+1:02d}", "open": 100 + i, "high": 102 + i,
     "low": 99 + i, "close": 101 + i, "volume": 1000 * (i + 1)}
    for i in range(30)
]


def test_runtime_sma():
    tokens = tokenize("sma5 = sma(close, 5)")
    ops = compile_ast(Parser(tokens).parse())
    result = execute(ops, _SAMPLE_PRICES)
    assert "sma5" in result
    # First 4 values should be None (not enough data), 5th should be average
    assert result["sma5"][0] is None
    assert result["sma5"][4] is not None
    expected = sum(101 + i for i in range(5)) / 5
    assert result["sma5"][4] == pytest.approx(expected, abs=0.01)


def test_runtime_ema():
    tokens = tokenize("ema5 = ema(close, 5)")
    ops = compile_ast(Parser(tokens).parse())
    result = execute(ops, _SAMPLE_PRICES)
    assert "ema5" in result
    assert result["ema5"][4] is not None


def test_runtime_rsi():
    tokens = tokenize("rsi14 = rsi(close, 14)")
    ops = compile_ast(Parser(tokens).parse())
    result = execute(ops, _SAMPLE_PRICES)
    assert "rsi14" in result
    # For monotonically increasing close, RSI should be high (>50)
    last_val = result["rsi14"][-1]
    assert last_val is not None
    assert last_val > 50


def test_runtime_crossover():
    tokens = tokenize("sma5 = sma(close, 5)\nsma10 = sma(close, 10)\ncross = crossover(sma5, sma10)")
    ops = compile_ast(Parser(tokens).parse())
    result = execute(ops, _SAMPLE_PRICES)
    assert "cross" in result


def test_runtime_arithmetic():
    tokens = tokenize("spread = high - low")
    ops = compile_ast(Parser(tokens).parse())
    result = execute(ops, _SAMPLE_PRICES)
    assert "spread" in result
    # high - low should be 3 for all bars (102+i - 99+i = 3)
    assert all(v == 3.0 for v in result["spread"])


def test_runtime_division_by_zero():
    """Division by zero produces NaN (None in output)."""
    tokens = tokenize("x = close / 0")
    ops = compile_ast(Parser(tokens).parse())
    result = execute(ops, _SAMPLE_PRICES)
    assert "x" in result
    assert all(v is None for v in result["x"])


def test_runtime_highest_lowest():
    tokens = tokenize("h5 = highest(high, 5)\nl5 = lowest(low, 5)")
    ops = compile_ast(Parser(tokens).parse())
    result = execute(ops, _SAMPLE_PRICES)
    assert "h5" in result
    assert "l5" in result
    # At index 4: highest of high[0:5] = 102,103,104,105,106 = 106
    assert result["h5"][4] == 106.0


# ── Integration: end-to-end via API ──

def test_pine_execute_api(test_client):
    """Execute Pine Script via API."""
    resp = test_client.post("/api/pine/execute", json={
        "script": "sma2 = sma(close, 2)",
        "symbol": "NIFTY50",
        "limit": 10,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "NIFTY50"
    assert "sma2" in data["indicators"]


def test_pine_execute_syntax_error(test_client):
    """Syntax error returns 400."""
    resp = test_client.post("/api/pine/execute", json={
        "script": "x = @invalid",
        "symbol": "NIFTY50",
    })
    assert resp.status_code == 400


def test_pine_execute_unknown_symbol(test_client):
    """Unknown symbol returns 404."""
    resp = test_client.post("/api/pine/execute", json={
        "script": "x = sma(close, 2)",
        "symbol": "NONEXISTENT",
    })
    assert resp.status_code == 404


def test_pine_builtins(test_client):
    """Builtins endpoint lists all available functions."""
    resp = test_client.get("/api/pine/builtins")
    assert resp.status_code == 200
    data = resp.json()
    assert "sma" in data["builtins"]
    assert "ema" in data["builtins"]
    assert "rsi" in data["builtins"]
    assert "crossover" in data["builtins"]
