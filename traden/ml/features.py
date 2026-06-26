"""Technische features voor ML model."""

from __future__ import annotations

import numpy as np
import pandas as pd

from traden.ml.sentiment import merge_sentiment

FEATURE_COLUMNS = [
    "return_1",
    "return_3",
    "return_5",
    "rsi_14",
    "ema_ratio",
    "macd",
    "macd_signal",
    "macd_hist",
    "volume_ratio",
    "range_pct",
    "atr_14",
]

SENTIMENT_COLUMNS = ["sentiment_score", "news_buzz"]


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def build_features(
    df: pd.DataFrame,
    symbol: str = "",
    market: str = "crypto",
    with_sentiment: bool = True,
) -> pd.DataFrame:
    out = df.copy()
    close = out["close"]
    high = out["high"]
    low = out["low"]
    volume = out["volume"]

    out["return_1"] = close.pct_change(1)
    out["return_3"] = close.pct_change(3)
    out["return_5"] = close.pct_change(5)
    out["rsi_14"] = _rsi(close, 14)
    out["ema_9"] = _ema(close, 9)
    out["ema_21"] = _ema(close, 21)
    out["ema_ratio"] = out["ema_9"] / out["ema_21"] - 1
    out["macd"] = _ema(close, 12) - _ema(close, 26)
    out["macd_signal"] = _ema(out["macd"], 9)
    out["macd_hist"] = out["macd"] - out["macd_signal"]
    out["volume_ratio"] = volume / volume.rolling(20).mean()
    out["range_pct"] = (high - low) / close
    out["atr_14"] = (
        pd.concat(
            [
                high - low,
                (high - close.shift()).abs(),
                (low - close.shift()).abs(),
            ],
            axis=1,
        )
        .max(axis=1)
        .rolling(14)
        .mean()
        / close
    )
    if with_sentiment and symbol:
        out = merge_sentiment(out, symbol, market)
    elif with_sentiment:
        out["sentiment_score"] = 0.5
        out["news_buzz"] = 0.5
    return out


def get_feature_columns(with_sentiment: bool = True) -> list[str]:
    cols = list(FEATURE_COLUMNS)
    if with_sentiment:
        cols.extend(SENTIMENT_COLUMNS)
    return cols


def build_labels(
    df: pd.DataFrame,
    forward_bars: int = 4,
    threshold: float = 0.003,
) -> pd.Series:
    """1 = prijs stijgt > threshold binnen forward_bars, 0 = daalt."""
    future_return = df["close"].shift(-forward_bars) / df["close"] - 1
    labels = pd.Series(index=df.index, dtype="float64")
    labels[future_return > threshold] = 1.0
    labels[future_return < -threshold] = 0.0
    return labels
