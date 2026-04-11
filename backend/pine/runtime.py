"""
Pine Script Runtime.

Executes a compiled plan against price_history data.
Each variable is a numpy array (Series) indexed by trade_date.
"""
import logging
from typing import Dict, List, Optional

import numpy as np

from .compiler import BUILTIN_SERIES, Op

logger = logging.getLogger(__name__)


def execute(
    ops: List[Op],
    price_data: List[Dict],
) -> Dict[str, List[Optional[float]]]:
    """
    Execute a compiled plan against price data.

    Args:
        ops: Compiled execution plan
        price_data: List of dicts with keys: trade_date, open, high, low, close, volume

    Returns:
        Dict mapping variable names to lists of values (one per bar).
        Includes built-in series (open, high, low, close, volume) and all computed variables.
    """
    n = len(price_data)
    if n == 0:
        return {}

    # Initialize built-in series
    env: Dict[str, np.ndarray] = {}
    for key in BUILTIN_SERIES:
        env[key] = np.array([float(d.get(key) or 0) for d in price_data], dtype=np.float64)

    dates = [d["trade_date"] for d in price_data]

    # Execute operations
    for op in ops:
        if op.op_type == "literal":
            env[op.target] = np.full(n, op.literal_value, dtype=np.float64)

        elif op.op_type == "alias":
            env[op.target] = env[op.args[0]].copy()

        elif op.op_type == "builtin":
            args = [env[a] if a in env else np.full(n, float(a)) for a in op.args]
            env[op.target] = _run_builtin(op.func, args, n)

        elif op.op_type == "binary":
            left = _resolve(env, op.args[0], n)
            right = _resolve(env, op.args[1], n)
            env[op.target] = _binary_op(op.func, left, right)

        elif op.op_type == "ternary":
            cond = _resolve(env, op.args[0], n)
            true_val = _resolve(env, op.args[1], n)
            false_val = _resolve(env, op.args[2], n)
            env[op.target] = np.where(cond != 0, true_val, false_val)

        elif op.op_type == "unary_minus":
            operand = _resolve(env, op.args[0], n)
            env[op.target] = -operand

    # Build result: dates + all user-defined variables (exclude temps and builtins)
    result = {"dates": dates}
    for op in ops:
        if not op.target.startswith("_t"):
            arr = env.get(op.target)
            if arr is not None:
                result[op.target] = [None if np.isnan(v) else round(float(v), 4) for v in arr]

    return result


def _resolve(env: Dict[str, np.ndarray], key: str, n: int) -> np.ndarray:
    """Resolve a variable name or literal number to a numpy array."""
    if key in env:
        return env[key]
    try:
        return np.full(n, float(key), dtype=np.float64)
    except ValueError:
        raise NameError(f"Undefined variable: '{key}'")


def _binary_op(op: str, left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Execute a binary operation."""
    if op == "+": return left + right
    if op == "-": return left - right
    if op == "*": return left * right
    if op == "/":
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(right != 0, left / right, np.nan)
    if op == ">": return (left > right).astype(np.float64)
    if op == "<": return (left < right).astype(np.float64)
    if op == ">=": return (left >= right).astype(np.float64)
    if op == "<=": return (left <= right).astype(np.float64)
    if op == "==": return (left == right).astype(np.float64)
    if op == "!=": return (left != right).astype(np.float64)
    if op == "and": return ((left != 0) & (right != 0)).astype(np.float64)
    if op == "or": return ((left != 0) | (right != 0)).astype(np.float64)
    raise ValueError(f"Unknown binary operator: '{op}'")


def _run_builtin(name: str, args: List[np.ndarray], n: int) -> np.ndarray:
    """Execute a built-in function."""
    if name == "sma":
        return _sma(args[0], int(args[1][0]))
    if name == "ema":
        return _ema(args[0], int(args[1][0]))
    if name == "rsi":
        return _rsi(args[0], int(args[1][0]))
    if name == "cross":
        return _cross(args[0], args[1])
    if name == "crossover":
        return _crossover(args[0], args[1])
    if name == "crossunder":
        return _crossunder(args[0], args[1])
    if name == "highest":
        return _rolling_max(args[0], int(args[1][0]))
    if name == "lowest":
        return _rolling_min(args[0], int(args[1][0]))
    if name == "abs":
        return np.abs(args[0])
    if name == "max":
        return np.maximum(args[0], args[1])
    if name == "min":
        return np.minimum(args[0], args[1])
    raise ValueError(f"Unknown builtin: '{name}'")


def _sma(source: np.ndarray, length: int) -> np.ndarray:
    """Simple Moving Average."""
    result = np.full_like(source, np.nan)
    if length <= 0 or length > len(source):
        return result
    cumsum = np.cumsum(source)
    result[length - 1:] = (cumsum[length - 1:] - np.concatenate([[0], cumsum[:-length]])) / length
    return result


def _ema(source: np.ndarray, length: int) -> np.ndarray:
    """Exponential Moving Average."""
    result = np.full_like(source, np.nan)
    if length <= 0 or length > len(source):
        return result
    alpha = 2.0 / (length + 1)
    result[length - 1] = np.mean(source[:length])
    for i in range(length, len(source)):
        result[i] = alpha * source[i] + (1 - alpha) * result[i - 1]
    return result


def _rsi(source: np.ndarray, length: int) -> np.ndarray:
    """Relative Strength Index."""
    result = np.full_like(source, np.nan)
    if length <= 0 or length >= len(source):
        return result
    deltas = np.diff(source)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:length])
    avg_loss = np.mean(losses[:length])

    if avg_loss == 0:
        result[length] = 100.0
    else:
        result[length] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    for i in range(length, len(deltas)):
        avg_gain = (avg_gain * (length - 1) + gains[i]) / length
        avg_loss = (avg_loss * (length - 1) + losses[i]) / length
        if avg_loss == 0:
            result[i + 1] = 100.0
        else:
            result[i + 1] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    return result


def _cross(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """True when a crosses b in either direction."""
    return (_crossover(a, b) + _crossunder(a, b)).clip(0, 1)


def _crossover(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """True when a crosses above b (a[i-1] <= b[i-1] and a[i] > b[i])."""
    result = np.zeros_like(a)
    for i in range(1, len(a)):
        if a[i - 1] <= b[i - 1] and a[i] > b[i]:
            result[i] = 1.0
    return result


def _crossunder(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """True when a crosses below b."""
    result = np.zeros_like(a)
    for i in range(1, len(a)):
        if a[i - 1] >= b[i - 1] and a[i] < b[i]:
            result[i] = 1.0
    return result


def _rolling_max(source: np.ndarray, length: int) -> np.ndarray:
    result = np.full_like(source, np.nan)
    for i in range(length - 1, len(source)):
        result[i] = np.max(source[i - length + 1:i + 1])
    return result


def _rolling_min(source: np.ndarray, length: int) -> np.ndarray:
    result = np.full_like(source, np.nan)
    for i in range(length - 1, len(source)):
        result[i] = np.min(source[i - length + 1:i + 1])
    return result
