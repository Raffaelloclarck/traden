"""Fetch historical OHLCV — including 6–12 maanden met cache."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import ccxt
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)
CACHE_DIR = Path("data/cache")


def _symbol_key(symbol: str) -> str:
    return symbol.replace("/", "_").replace(".", "_")


def _cache_path(market: str, symbol: str, timeframe: str, months: int) -> Path:
    return CACHE_DIR / f"{market}_{_symbol_key(symbol)}_{timeframe}_{months}m.parquet"


def _fetch_crypto_paginated(
    symbol: str,
    timeframe: str,
    months: int,
) -> pd.DataFrame:
    exchange = ccxt.binance({"enableRateLimit": True})
    ms_per_bar = exchange.parse_timeframe(timeframe) * 1000
    since = exchange.milliseconds() - (months * 30 * 24 * 60 * 60 * 1000)
    all_rows: list[list] = []

    while since < exchange.milliseconds():
        batch = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if not batch:
            break
        all_rows.extend(batch)
        since = batch[-1][0] + ms_per_bar
        if len(batch) < 1000:
            break
        time.sleep(exchange.rateLimit / 1000)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    return df.set_index("timestamp")


def _stock_params(months: int, timeframe: str) -> tuple[str, str]:
    if months <= 2 and timeframe in ("1m", "5m", "15m"):
        return timeframe, f"{min(months * 30, 59)}d"
    if months <= 12:
        return "1h", f"{months}mo"
    return "1d", "2y"


def _fetch_stock(symbol: str, months: int, timeframe: str) -> pd.DataFrame:
    interval, period = _stock_params(months, timeframe)
    df = yf.Ticker(symbol).history(period=period, interval=interval)
    if df.empty:
        return pd.DataFrame()

    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    df.index = pd.to_datetime(df.index, utc=True)
    return df[["open", "high", "low", "close", "volume"]].dropna()


def fetch_ohlcv(
    symbol: str,
    market: str = "crypto",
    months: int = 12,
    timeframe: str = "15m",
    use_cache: bool = True,
) -> pd.DataFrame:
    cache = _cache_path(market, symbol, timeframe, months)
    if use_cache and cache.exists():
        df = pd.read_parquet(cache)
        logger.info("Cache hit: %s (%d candles)", cache.name, len(df))
        return df

    logger.info("Ophalen %s %s — %d maanden...", symbol, market, months)
    if market == "crypto":
        df = _fetch_crypto_paginated(symbol, timeframe, months)
    else:
        df = _fetch_stock(symbol, months, timeframe)

    if df.empty:
        raise ValueError(f"Geen data voor {symbol}")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache)
    logger.info("Opgeslagen: %d candles → %s", len(df), cache.name)
    return df


def fetch_crypto_ohlcv(
    symbol: str,
    timeframe: str = "15m",
    limit: int = 200,
) -> pd.DataFrame:
    """Korte fetch voor live scanning (geen cache)."""
    exchange = ccxt.binance({"enableRateLimit": True})
    raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(
        raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("timestamp")


def fetch_stock_ohlcv(
    symbol: str,
    interval: str = "15m",
    period: str = "60d",
) -> pd.DataFrame:
    """Korte fetch voor live scanning."""
    df = yf.Ticker(symbol).history(period=period, interval=interval)
    if df.empty:
        return pd.DataFrame()
    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    df.index = pd.to_datetime(df.index, utc=True)
    return df[["open", "high", "low", "close", "volume"]].dropna()
