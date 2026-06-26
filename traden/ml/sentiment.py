"""Sentiment & nieuws features."""

from __future__ import annotations

import logging

import pandas as pd
import requests
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_crypto_fear_greed(limit: int = 365) -> pd.DataFrame:
    """Crypto Fear & Greed Index (0–100)."""
    url = f"https://api.alternative.me/fng/?limit={limit}&format=json"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    rows = resp.json().get("data", [])
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="s", utc=True)
    df["sentiment_score"] = df["value"].astype(float) / 100.0
    return df.set_index("timestamp")[["sentiment_score"]].sort_index()


def fetch_stock_sentiment_proxy() -> pd.DataFrame:
    """VIX als angst-proxy — lage VIX = bullish sentiment."""
    vix = yf.Ticker("^VIX").history(period="1y", interval="1d")
    if vix.empty:
        return pd.DataFrame()

    vix.index = pd.to_datetime(vix.index, utc=True)
    close = vix["Close"]
    normalized = 1.0 - (close - close.min()) / (close.max() - close.min() + 1e-9)
    return pd.DataFrame({"sentiment_score": normalized}, index=vix.index)


def fetch_news_buzz(symbol: str, market: str) -> float:
    """Simpele nieuws-buzz score op basis van recente headlines (0–1)."""
    try:
        if market == "crypto":
            query = symbol.split("/")[0]
        else:
            query = symbol
        ticker = yf.Ticker(query if market == "stock" else f"{query}-USD")
        news = ticker.news or []
        if not news:
            return 0.5
        return min(1.0, len(news[:10]) / 10.0)
    except Exception as exc:
        logger.debug("News buzz mislukt voor %s: %s", symbol, exc)
        return 0.5


def merge_sentiment(
    df: pd.DataFrame,
    symbol: str,
    market: str,
) -> pd.DataFrame:
    out = df.copy()
    try:
        if market == "crypto":
            sentiment = fetch_crypto_fear_greed()
        else:
            sentiment = fetch_stock_sentiment_proxy()
    except Exception as exc:
        logger.warning("Sentiment ophalen mislukt: %s", exc)
        out["sentiment_score"] = 0.5
        out["news_buzz"] = 0.5
        return out

    merged = out.join(sentiment, how="left")
    merged["sentiment_score"] = merged["sentiment_score"].ffill().fillna(0.5)
    merged["news_buzz"] = fetch_news_buzz(symbol, market)
    return merged
