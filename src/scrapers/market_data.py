"""Production-grade market data fetcher for 10 financial indicators.

Provides async ``fetch_all()`` that returns current prices and (where
available) previous-close values for gold, oil, NASDAQ, China A-share
indices, CNY-centric forex pairs, and domestic gold reference.

Data sources (queried concurrently):
  - open.er-api.com -- forex (USD/CNY, EUR/CNY, JPY/CNY(100))
  - Sina Finance    -- CN indices + gold + oil
  - akshare         -- NASDAQ

Usage:
    from src.scrapers.market_data import fetch_all

    data = await fetch_all()
    print(data["nasdaq"]["price"])       # e.g. 19723.45
    print(data["nasdaq"]["prev_close"])  # e.g. 19650.80

Standalone:
    uv run python src/scrapers/market_data.py
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

FOREX_URL = "https://open.er-api.com/v6/latest/USD"
SINA_URL = "https://hq.sinajs.cn/list={codes}"

SINA_MAP: dict[str, str] = {
    "shanghai": "sh000001",
    "chinext": "sz399006",
    "star50": "sh000688",
    "gold": "hf_XAU",
    "oil": "hf_CL",
}

LABELS: dict[str, tuple[str, str]] = {
    "gold":     ("纽约金",            "COMEX Gold"),
    "oil":      ("WTI 原油",          "WTI Crude Oil"),
    "nasdaq":   ("纳斯达克",          "NASDAQ"),
    "usdcny":   ("美元/人民币",        "USD/CNY"),
    "eurcny":   ("欧元/人民币",        "EUR/CNY"),
    "jpycny":   ("日元/人民币(100)",   "JPY/CNY(100)"),
    "shanghai": ("上证指数",           "Shanghai Composite"),
    "chinext":  ("创业板指",           "ChiNext"),
    "star50":   ("科创 50",           "STAR 50"),
    "domestic_gold": ("国内参考金价",  "Domestic Gold"),
}

TIMEOUT = 15

# ── Forex (open.er-api.com) ───────────────────────────────────────────────


async def fetch_forex() -> dict[str, dict]:
    """Fetch USD/CNY, EUR/CNY, JPY/CNY(100) from open.er-api.com.

    All rates are CNY-centric: how many CNY per foreign currency unit.
    JPY/CNY is per 100 JPY (standard China convention).
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(FOREX_URL)
            resp.raise_for_status()
            rates = resp.json()["rates"]
        usd_cny = rates["CNY"]
        usd_jpy = rates["JPY"]
        usd_eur = rates["EUR"]
        return {
            "usdcny": {"price": round(usd_cny, 4), "prev_close": None},
            "eurcny": {"price": round(usd_cny / usd_eur, 4), "prev_close": None},
            "jpycny": {"price": round(100 * usd_cny / usd_jpy, 4), "prev_close": None},
        }
    except Exception as exc:
        logger.warning("Forex fetch failed: %s", exc)
        return {k: {"error": str(exc)} for k in ("usdcny", "eurcny", "jpycny")}


# ── Sina (CN indices, gold, oil) ──────────────────────────────────────────


async def fetch_sina() -> dict[str, dict]:
    """Fetch Shanghai, ChiNext, STAR 50, gold, oil from Sina Finance."""
    try:
        code_str = ",".join(SINA_MAP.values())
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(
                SINA_URL.format(codes=code_str),
                headers={"Referer": "https://finance.sina.com.cn"},
            )
            resp.raise_for_status()
            raw = resp.text
    except Exception as exc:
        logger.warning("Sina fetch failed: %s", exc)
        return {k: {"error": str(exc)} for k in SINA_MAP}

    results: dict[str, dict] = {}
    for key, code in SINA_MAP.items():
        # Sina CSV field layout for international futures (hf_ prefix):
        #   field 0: current price (最新价)
        #   field 1: previous close (昨收, may be empty for some symbols like CL)
        #   field 2: open, field 3: high, field 4: low, ...
        # For Chinese stock indices (sh/sz prefix):
        #   field 1: open, field 2: prev_close, field 3: current price, ...
        if key in ("gold", "oil"):
            field_idx = 0  # price
            prev_idx = 1   # prev_close
        else:
            field_idx = 3  # current_price
            prev_idx = 2   # prev_close
        for line in raw.split("\n"):
            if code not in line:
                continue
            try:
                parts = line.split('"')[1].split(",")
                price_raw = parts[field_idx].strip() if field_idx < len(parts) else ""
                prev_raw = parts[prev_idx].strip() if prev_idx < len(parts) else ""
                price = round(float(price_raw), 4) if price_raw else None
                prev_close = round(float(prev_raw), 4) if prev_raw else None
                if price is not None:
                    results[key] = {"price": price, "prev_close": prev_close}
                else:
                    results[key] = {"error": f"empty price at field {field_idx}: {parts[:4]}"}
            except (ValueError, IndexError) as exc:
                results[key] = {"error": f"parse: {exc} -- {parts[:4]}"}
            break
        else:
            results[key] = {"error": "no matching line in Sina response"}
    return results


# ── US Indices (akshare) ──────────────────────────────────────────────────


async def _fetch_nasdaq() -> dict:
    """Fetch NASDAQ current price and previous close via akshare daily history."""
    try:
        import akshare as ak  # noqa: PLC0415
    except ImportError as exc:
        return {"error": f"akshare not installed: {exc}"}

    try:
        df = await asyncio.to_thread(ak.index_us_stock_sina, symbol=".IXIC")
        if df is None or df.empty or "close" not in df.columns:
            return {"error": "akshare returned empty/invalid NASDAQ data"}

        price = round(float(df["close"].iloc[-1]), 2)
        prev_close = round(float(df["close"].iloc[-2]), 2) if len(df) >= 2 else None
        return {"price": price, "prev_close": prev_close}
    except Exception as exc:
        return {"error": f"NASDAQ akshare: {exc}"}


async def fetch_nasdaq() -> dict[str, dict]:
    """Fetch NASDAQ via akshare (wraps the internal fetcher)."""
    return {"nasdaq": await _fetch_nasdaq()}


# ── Public API ─────────────────────────────────────────────────────────────


async def fetch_all() -> dict[str, dict]:
    """Fetch current prices for all 10 indicators across 3 data sources.

    Returns a dict keyed by indicator slug (``gold``, ``oil``, ``nasdaq``,
    ``usdcny``, ``eurcny``, ``jpycny``, ``shanghai``, ``chinext``, ``star50``,
    ``domestic_gold``).
    Each value is either:

    - ``{"price": float, "prev_close": float | None}`` on success, or
    - ``{"error": str}`` on failure for that specific indicator.

    Only **nasdaq** includes a meaningful ``prev_close`` (derived from akshare
    daily history). All other indicators set ``prev_close`` to ``None``.

    Sources are queried concurrently; wall-clock time is bounded by the
    slowest source (typically under 10 seconds).
    """
    forex, sina, nasdaq = await asyncio.gather(
        fetch_forex(), fetch_sina(), fetch_nasdaq(),
    )
    all_data = {**forex, **sina, **nasdaq}

    # Compute domestic gold reference price (CNY/gram)
    # Formula: COMEX gold (USD/oz) × USD/CNY rate ÷ 31.1035 (grams per troy oz)
    gold_price = all_data.get("gold", {}).get("price")
    usdcny_rate = all_data.get("usdcny", {}).get("price")
    if gold_price is not None and usdcny_rate is not None:
        all_data["domestic_gold"] = {
            "price": round(gold_price * usdcny_rate / 31.1035, 2),
            "prev_close": None,
        }
    else:
        all_data["domestic_gold"] = {"error": "missing gold or usdcny data"}

    return all_data


# ── Standalone Display ────────────────────────────────────────────────────


def _print_table(all_results: dict, elapsed: float) -> None:
    """Print a formatted table of indicator results."""
    sep = "-" * 80
    header = (
        f"{'#':>2} {'Name':<22} {'Price':>14} {'Prev Close':>14} {'Status':>10}"
    )
    print("\n" + "=" * 80)
    print(f"  MARKET DATA  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print(header)
    print(sep)
    ok = 0
    for i, (key, (name, _ticker)) in enumerate(LABELS.items(), 1):
        r = all_results.get(key, {})
        if "error" in r:
            print(
                f"{i:>2} {name:<22} {'':>14} {'':>14} {'FAIL':>10}  "
                f"| {r['error']}"
            )
        elif r.get("price") is None:
            print(f"{i:>2} {name:<22} {'N/A':>14} {'':>14} {'WARN':>10}")
        else:
            ok += 1
            p = r["price"]
            pc = r.get("prev_close")
            pc_str = f"{pc:>14.2f}" if pc is not None else f"{'N/A':>14}"
            print(f"{i:>2} {name:<22} {p:>14.4f} {pc_str} {'OK':>10}")
    print(sep)
    print(f"\n  {ok}/{len(LABELS)} ok  |  {elapsed:.1f}s\n")


async def _main_standalone() -> None:
    """Entry point when run as ``python src/scrapers/market_data.py``."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    start = time.time()
    print("\n  Fetching: forex + CN/gold/oil (Sina) + NASDAQ (akshare) ...")
    data = await fetch_all()
    _print_table(data, time.time() - start)


if __name__ == "__main__":
    asyncio.run(_main_standalone())
