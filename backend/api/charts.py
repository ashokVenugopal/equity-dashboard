"""
Chart export API.

Generates standalone HTML files containing TradingView lightweight-charts
with embedded data. These HTML files can be opened independently or
embedded in Streamlit via st.components.html().
"""
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from backend.core.connection import get_pipeline_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/charts", tags=["charts"])

_CHART_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #0a0a0a; font-family: monospace; }}
  #chart {{ width: 100%; height: {height}px; }}
  .header {{ color: #666; font-size: 11px; padding: 8px 12px; }}
  .header .symbol {{ color: #00d4aa; font-weight: bold; }}
</style>
</head>
<body>
<div class="header">
  <span class="symbol">{symbol}</span> &mdash; {subtitle}
</div>
<div id="chart"></div>
<script src="https://unpkg.com/lightweight-charts@4.2.2/dist/lightweight-charts.standalone.production.js"></script>
<script>
  const data = {data_json};
  const chart = LightweightCharts.createChart(document.getElementById('chart'), {{
    width: document.getElementById('chart').clientWidth,
    height: {height},
    layout: {{
      background: {{ type: 'solid', color: '#0a0a0a' }},
      textColor: '#666',
      fontSize: 11,
      fontFamily: 'monospace',
    }},
    grid: {{
      vertLines: {{ color: '#1a1a1a' }},
      horzLines: {{ color: '#1a1a1a' }},
    }},
    crosshair: {{
      mode: LightweightCharts.CrosshairMode.Normal,
    }},
    timeScale: {{
      borderColor: '#2a2a2a',
      timeVisible: false,
    }},
    rightPriceScale: {{
      borderColor: '#2a2a2a',
    }},
  }});

  const candleSeries = chart.addCandlestickSeries({{
    upColor: '#00c853',
    downColor: '#ff5252',
    borderUpColor: '#00c853',
    borderDownColor: '#ff5252',
    wickUpColor: '#00c853',
    wickDownColor: '#ff5252',
  }});
  candleSeries.setData(data.candles);

  if (data.volume && data.volume.length > 0) {{
    const volumeSeries = chart.addHistogramSeries({{
      color: '#2a2a2a',
      priceFormat: {{ type: 'volume' }},
      priceScaleId: 'volume',
    }});
    chart.priceScale('volume').applyOptions({{
      scaleMargins: {{ top: 0.8, bottom: 0 }},
    }});
    volumeSeries.setData(data.volume);
  }}

  window.addEventListener('resize', () => {{
    chart.applyOptions({{ width: document.getElementById('chart').clientWidth }});
  }});
</script>
</body>
</html>"""


@router.get("/export", response_class=HTMLResponse)
def export_chart(
    symbol: str = Query(..., description="Instrument symbol"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(365, ge=1, le=2000),
    height: int = Query(400, ge=200, le=800),
):
    """
    Generate a standalone HTML chart for the given instrument.
    Returns complete HTML that can be saved as a file or embedded in Streamlit.
    """
    logger.info("GET /api/charts/export — symbol=%s, start_date=%s, end_date=%s, limit=%d", symbol, start_date, end_date, limit)
    t0 = time.time()
    conn = get_pipeline_connection()
    try:
        instrument = conn.execute(
            "SELECT instrument_id, name FROM instruments WHERE symbol = ? AND is_active = 1",
            (symbol.upper(),)
        ).fetchone()
        if not instrument:
            raise HTTPException(status_code=404, detail=f"Instrument '{symbol}' not found")

        sql = """
            SELECT trade_date, open, high, low, close, volume
            FROM best_prices
            WHERE instrument_id = ?
        """
        params: list = [instrument["instrument_id"]]
        if start_date:
            sql += " AND trade_date >= ?"
            params.append(start_date)
        if end_date:
            sql += " AND trade_date <= ?"
            params.append(end_date)
        sql += " ORDER BY trade_date ASC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail=f"No price data for '{symbol}'")

        candles = []
        volume_data = []
        for r in rows:
            candle = {"time": r["trade_date"], "open": r["open"], "high": r["high"],
                      "low": r["low"], "close": r["close"]}
            candles.append(candle)
            if r["volume"]:
                color = "#00c85340" if r["close"] >= r["open"] else "#ff525240"
                volume_data.append({"time": r["trade_date"], "value": r["volume"], "color": color})

        data_json = json.dumps({"candles": candles, "volume": volume_data})
        inst_name = instrument["name"]

        html = _CHART_HTML_TEMPLATE.format(
            title=f"{symbol.upper()} - {inst_name}",
            symbol=symbol.upper(),
            subtitle=inst_name,
            data_json=data_json,
            height=height,
        )

        elapsed = time.time() - t0
        logger.info("GET /api/charts/export?symbol=%s — %d candles, %.3fs", symbol, len(candles), elapsed)
        return HTMLResponse(content=html)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("GET /api/charts/export?symbol=%s — failed: %s", symbol, e)
        raise
    finally:
        conn.close()
