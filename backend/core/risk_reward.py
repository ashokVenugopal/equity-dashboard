"""
Risk/reward computations for the company page.

Pure functions over (date, value) series — no DB access — so every edge
case (negative EPS, missing quarters, sign flips) is unit-testable.

Concepts:
  TTM series      — rolling sum of the trailing 4 quarterly values,
                    effective from each quarter's period_end_date.
  Gauge           — floor/peak of a daily ratio series over a window plus
                    the current value's "altitude" within that range
                    (0% = at floor, 100% = at peak).
  Attribution     — price change decomposed into earnings change and
                    multiple change: P1/P0 = (E1/E0) · (M1/M0). Shares
                    are computed in log space so they sum to 100%.
"""
import math
from bisect import bisect_right
from datetime import date, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

DatedValue = Tuple[str, float]  # (ISO date, value)


def build_ttm_series(quarterly: Sequence[DatedValue]) -> List[DatedValue]:
    """Rolling 4-quarter sums, effective from the 4th quarter's end date.

    Input: (period_end_date, value) — duplicates collapsed keeping the
    last, sorted internally. Returns [] with fewer than 4 quarters.
    """
    dedup: Dict[str, float] = {}
    for d, v in quarterly:
        if v is not None:
            dedup[d] = v
    ordered = sorted(dedup.items())
    out: List[DatedValue] = []
    for i in range(3, len(ordered)):
        window = ordered[i - 3:i + 1]
        out.append((window[-1][0], sum(v for _, v in window)))
    return out


def value_as_of(series: Sequence[DatedValue], iso_date: str) -> Optional[float]:
    """Latest value whose effective date is <= iso_date. None if before all."""
    if not series:
        return None
    dates = [d for d, _ in series]
    idx = bisect_right(dates, iso_date) - 1
    if idx < 0:
        return None
    return series[idx][1]


def daily_ratio_series(
    prices: Sequence[DatedValue],
    denominator: Sequence[DatedValue],
    numerator_extra: float = 0.0,
    price_multiplier: float = 1.0,
) -> List[DatedValue]:
    """Ratio per trading day: (close·multiplier + extra) / denominator-in-effect.

    Days with no denominator in effect, zero, or a negative denominator are
    skipped — a negative-earnings PE is not a meaningful altitude input.
    """
    out: List[DatedValue] = []
    for d, close in prices:
        denom = value_as_of(denominator, d)
        if denom is None or denom <= 0:
            continue
        out.append((d, (close * price_multiplier + numerator_extra) / denom))
    return out


def gauge_from_series(
    series: Sequence[DatedValue],
    max_trend_points: int = 60,
) -> Optional[dict]:
    """Floor / peak / current / altitude for a daily series, plus a
    downsampled trend for the hover sparkline.

    altitude = (current − floor) / (peak − floor), clamped to [0, 1].
    None if the series is empty; peak == floor collapses altitude to 0.5.
    """
    if not series:
        return None
    values = [v for _, v in series]
    floor, peak = min(values), max(values)
    current_date, current = series[-1]
    if peak > floor:
        altitude = (current - floor) / (peak - floor)
    else:
        altitude = 0.5
    altitude = max(0.0, min(1.0, altitude))

    n = len(series)
    if n <= max_trend_points:
        trend = list(series)
    else:
        step = n / max_trend_points
        idx_set = {min(n - 1, int(i * step)) for i in range(max_trend_points)}
        idx_set.add(n - 1)
        trend = [series[i] for i in sorted(idx_set)]

    return {
        "floor": round(floor, 2),
        "peak": round(peak, 2),
        "current": round(current, 2),
        "current_date": current_date,
        "altitude_pct": round(altitude * 100.0, 1),
        "trend": [{"date": d, "value": round(v, 2)} for d, v in trend],
    }


def decompose_price_change(
    p0: Optional[float], p1: Optional[float],
    e0: Optional[float], e1: Optional[float],
) -> Optional[dict]:
    """Split a price change into earnings-driven and multiple-driven parts.

    P1/P0 = (E1/E0) · (M1/M0) with M = P/E. Attribution shares use log
    ratios so the two parts sum to 100% of the (log) move.

    Returns price/earnings/multiple change percentages; the share split is
    None when it is not meaningful (EPS <= 0 at either end, or a ~zero
    price move where shares would explode).
    """
    if not p0 or not p1 or p0 <= 0 or p1 <= 0:
        return None
    price_chg = p1 / p0 - 1.0

    result = {
        "price_change_pct": round(price_chg * 100.0, 1),
        "earnings_change_pct": None,
        "multiple_change_pct": None,
        "earnings_share_pct": None,
        "multiple_share_pct": None,
    }
    if e0 is None or e1 is None or e0 <= 0 or e1 <= 0:
        return result

    earnings_chg = e1 / e0 - 1.0
    m0, m1 = p0 / e0, p1 / e1
    multiple_chg = m1 / m0 - 1.0
    result["earnings_change_pct"] = round(earnings_chg * 100.0, 1)
    result["multiple_change_pct"] = round(multiple_chg * 100.0, 1)

    log_price = math.log(p1 / p0)
    if abs(log_price) > 1e-4:
        earnings_share = math.log(e1 / e0) / log_price
        result["earnings_share_pct"] = round(earnings_share * 100.0, 1)
        result["multiple_share_pct"] = round((1.0 - earnings_share) * 100.0, 1)
    return result


ATTRIBUTION_WINDOWS: Tuple[Tuple[str, int], ...] = (
    ("1W", 7),
    ("1M", 30),
    ("3M", 91),
    ("6M", 182),
    ("1Y", 365),
    ("3Y", 1095),
)


def close_on_or_before(
    prices: Sequence[DatedValue], iso_date: str,
    max_staleness_days: Optional[int] = None,
) -> Optional[float]:
    """Close on iso_date or the nearest earlier trading day.

    max_staleness_days guards against price-history gaps: if the nearest
    earlier close is older than the tolerance, treat the boundary as
    unavailable rather than silently using a months-stale price.
    """
    if not prices:
        return None
    dates = [d for d, _ in prices]
    idx = bisect_right(dates, iso_date) - 1
    if idx < 0:
        return None
    found_date, found_value = prices[idx]
    if max_staleness_days is not None:
        gap = (date.fromisoformat(iso_date) - date.fromisoformat(found_date)).days
        if gap > max_staleness_days:
            return None
    return found_value


def build_attribution_rows(
    prices: Sequence[DatedValue],
    ttm_eps: Sequence[DatedValue],
    annual_eps: Sequence[DatedValue] = (),
) -> List[dict]:
    """One attribution row per window in ATTRIBUTION_WINDOWS.

    prices must be sorted ascending. EPS at each boundary comes from the
    TTM series; when the TTM series doesn't reach back far enough (its
    first effective date is after the window start), fall back to annual
    EPS so long windows (3Y) still decompose.
    """
    if not prices:
        return []
    latest_date_iso, p1 = prices[-1]
    latest = date.fromisoformat(latest_date_iso)
    e1 = value_as_of(ttm_eps, latest_date_iso)
    ttm_start = ttm_eps[0][0] if ttm_eps else None

    rows: List[dict] = []
    for label, days in ATTRIBUTION_WINDOWS:
        start_iso = (latest - timedelta(days=days)).isoformat()
        # Staleness tolerance: ~10% of the window, at least 10 days —
        # so a 1W row needs a close within ~10d of the boundary, while
        # a 3Y row tolerates a few months' drift. Guards against long
        # price-history gaps producing wildly wrong baselines.
        tolerance = max(10, days // 10)
        p0 = close_on_or_before(prices, start_iso, max_staleness_days=tolerance)
        # Don't fabricate a window older than our price history.
        if p0 is None:
            rows.append({"window": label, "available": False})
            continue

        eps_source = "ttm"
        e0 = value_as_of(ttm_eps, start_iso)
        e1_w = e1
        if e0 is None or (ttm_start is not None and start_iso < ttm_start):
            e0 = value_as_of(annual_eps, start_iso)
            e1_w = value_as_of(annual_eps, latest_date_iso) or e1
            eps_source = "annual"

        decomp = decompose_price_change(p0, p1, e0, e1_w)
        if decomp is None:
            rows.append({"window": label, "available": False})
            continue
        rows.append({
            "window": label,
            "available": True,
            "eps_source": eps_source,
            **decomp,
        })
    return rows
