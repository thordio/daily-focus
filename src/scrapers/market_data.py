"""Production-grade market data fetcher for 9 financial indicators.

Provides async ``fetch_all()`` that returns current prices and (where
available) previous-close values for gold, oil, NASDAQ, China A-share
indices, and major forex pairs.

Data sources (queried concurrently):
  - open.er-api.com -- forex (CNY, JPY, EUR vs USD)
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
    "gold":     ("Gold",              "GC=F"),
    "oil":      ("WTI Crude Oil",     "CL=F"),
    "nasdaq":   ("NASDAQ",            "^IXIC"),
    "usdcny":   ("USD/CNY",           "CNY=X"),
    "usdjpy":   ("USD/JPY",           "JPY=X"),
    "eurusd":   ("EUR/USD",           "EURUSD=X"),
    "shanghai": ("Shanghai Composite", "000001.SS"),
    "chinext":  ("ChiNext",           "399006.SZ"),
    "star50":   ("STAR 50",           "000688.SS"),
}

TIMEOUT = 15

# ── Forex (open.er-api.com) ───────────────────────────────────────────────


async def fetch_forex() -> dict[str, dict]:
    """Fetch USD/CNY, USD/JPY, EUR/USD from open.er-api.com."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(FOREX_URL)
            resp.raise_for_status()
            rates = resp.json()["rates"]
        return {
            "usdcny": {"price": round(rates["CNY"], 4), "prev_close": None},
            "usdjpy": {"price": round(rates["JPY"], 4), "prev_close": None},
            "eurusd": {"price": round(1 / rates["EUR"], 4), "prev_close": None},
        }
    except Exception as exc:
        logger.warning("Forex fetch failed: %s", exc)
        return {k: {"error": str(exc)} for k in ("usdcny", "usdjpy", "eurusd")}


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
        field_idx = 0 if key in ("gold", "oil") else 3
        for line in raw.split("\n"):
            if code not in line:
                continue
            try:
                parts = line.split('"')[1].split(",")
                results[key] = {
                    "price": round(float(parts[field_idx]), 4),
                    "prev_close": None,
                }
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
    """Fetch current prices for all 9 indicators across 3 data sources.

    Returns a dict keyed by indicator slug (``gold``, ``oil``, ``nasdaq``,
    ``usdcny``, ``usdjpy``, ``eurusd``, ``shanghai``, ``chinext``, ``star50``).
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
    return {**forex, **sina, **nasdaq}


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
