"""
Pine Script API endpoint.

Executes user-written Pine Script against instrument price data.
"""
import logging
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.connection import get_pipeline_connection
from backend.pine.lexer import tokenize
from backend.pine.parser import Parser
from backend.pine.compiler import compile_ast, BUILTINS
from backend.pine.runtime import execute

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pine", tags=["pine"])


class PineExecuteRequest(BaseModel):
    script: str
    symbol: str
    limit: int = 365


@router.post("/execute")
def pine_execute(body: PineExecuteRequest):
    """
    Execute a Pine Script against an instrument's price history.
    Returns computed indicator values per date.
    """
    t0 = time.time()

    # Compile
    try:
        tokens = tokenize(body.script)
        ast = Parser(tokens).parse()
        ops = compile_ast(ast)
    except (SyntaxError, NameError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Script error: {e}")

    if not ops:
        raise HTTPException(status_code=400, detail="Script produced no outputs")

    # Fetch price data
    conn = get_pipeline_connection()
    try:
        instrument = conn.execute(
            "SELECT instrument_id FROM instruments WHERE symbol = ? AND is_active = 1",
            (body.symbol.upper(),)
        ).fetchone()
        if not instrument:
            raise HTTPException(status_code=404, detail=f"Instrument '{body.symbol}' not found")

        rows = conn.execute("""
            SELECT trade_date, open, high, low, close, volume
            FROM best_prices
            WHERE instrument_id = ?
            ORDER BY trade_date ASC
            LIMIT ?
        """, (instrument["instrument_id"], body.limit)).fetchall()

        price_data = [dict(r) for r in rows]
    finally:
        conn.close()

    if not price_data:
        raise HTTPException(status_code=404, detail=f"No price data for '{body.symbol}'")

    # Execute
    try:
        result = execute(ops, price_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Runtime error: {e}")

    elapsed = time.time() - t0
    logger.info("POST /api/pine/execute — %s, %d bars, %.3fs", body.symbol, len(price_data), elapsed)
    return {
        "symbol": body.symbol.upper(),
        "bars": len(price_data),
        "indicators": result,
        "elapsed_ms": round(elapsed * 1000, 1),
    }


@router.get("/builtins")
def pine_builtins():
    """List all available built-in functions."""
    return {"builtins": BUILTINS}
