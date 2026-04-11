"""
Optimized query helpers.

The best_prices view uses a correlated subquery that's O(n²) on 594K rows.
These helpers use direct queries with window functions on price_history for speed.
Also handles classification deduplication (multiple active rows per stock from versioning).
"""


def latest_prices_sql(instrument_filter: str = "1=1") -> str:
    """
    Get latest price per instrument using ROW_NUMBER on price_history directly.
    Much faster than JOINing with best_prices view.

    Args:
        instrument_filter: SQL condition to filter instruments (e.g., "i.instrument_type = 'index'")
    """
    return f"""
        WITH target_instruments AS (
            SELECT instrument_id FROM instruments i WHERE {instrument_filter}
        ),
        ranked AS (
            SELECT ph.instrument_id, ph.trade_date, ph.open, ph.high, ph.low,
                   ph.close, ph.volume, ph.delivery_qty, ph.source,
                   ROW_NUMBER() OVER (
                       PARTITION BY ph.instrument_id
                       ORDER BY ph.trade_date DESC,
                           CASE ph.source
                               WHEN 'nse_bhavcopy' THEN 1
                               WHEN 'bse_bhavcopy' THEN 2
                               WHEN 'nse_index' THEN 3
                               WHEN 'yahoo_finance' THEN 4
                               ELSE 5
                           END
                   ) AS rn
            FROM price_history ph
            WHERE ph.instrument_id IN (SELECT instrument_id FROM target_instruments)
        )
        SELECT * FROM ranked WHERE rn = 1
    """


def prev_prices_sql(instrument_filter: str = "1=1") -> str:
    """
    Get second-latest price per instrument for change calculation.
    """
    return f"""
        WITH target_instruments AS (
            SELECT instrument_id FROM instruments i WHERE {instrument_filter}
        ),
        ranked AS (
            SELECT ph.instrument_id, ph.trade_date, ph.close,
                   ROW_NUMBER() OVER (
                       PARTITION BY ph.instrument_id
                       ORDER BY ph.trade_date DESC,
                           CASE ph.source
                               WHEN 'nse_bhavcopy' THEN 1
                               WHEN 'bse_bhavcopy' THEN 2
                               WHEN 'nse_index' THEN 3
                               WHEN 'yahoo_finance' THEN 4
                               ELSE 5
                           END
                   ) AS rn
            FROM price_history ph
            WHERE ph.instrument_id IN (SELECT instrument_id FROM target_instruments)
        )
        SELECT instrument_id, close AS prev_close, trade_date AS prev_date
        FROM ranked WHERE rn = 2
    """


def deduped_classifications_sql(classification_type: str, classification_name_param: str = "?") -> str:
    """
    Get distinct instrument_ids for a classification, deduped across version rows.
    Uses GROUP BY to collapse multiple active classification rows per stock.
    """
    return f"""
        SELECT cl.instrument_id, MIN(cl.sort_order) AS sort_order
        FROM classifications cl
        WHERE cl.classification_type = '{classification_type}'
          AND cl.classification_name = {classification_name_param}
          AND (cl.effective_to IS NULL OR cl.effective_to >= date('now'))
        GROUP BY cl.instrument_id
    """
