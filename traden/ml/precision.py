"""High-precision backtest — win rate op zekerheidstrades."""

from __future__ import annotations

import numpy as np
import pandas as pd


def backtest_with_confidence(
    model,
    model_type: str,
    test_x: pd.DataFrame,
    test_y: pd.Series,
    test_featured: pd.DataFrame,
    feature_cols: list[str],
    min_confidence: float = 0.75,
) -> dict:
    """
    Trade alleen wanneer model >= min_confidence voorspelt.
    Meet win rate op die gefilterde trades.
    """
    if model_type == "sequence":
        proba = model.predict_proba(test_x[feature_cols])[:, 1]
        aligned_y = test_y.iloc[model.seq_len : model.seq_len + len(proba)]
        aligned_feat = test_featured.iloc[model.seq_len : model.seq_len + len(proba)]
        min_len = min(len(proba), len(aligned_y))
        proba = proba[:min_len]
        aligned_y = aligned_y.iloc[:min_len]
        aligned_feat = test_featured.iloc[model.seq_len : model.seq_len + min_len]
    else:
        proba = model.predict_proba(test_x[feature_cols])[:, 1]
        aligned_y = test_y
        aligned_feat = test_featured

    returns = aligned_feat["return_1"].shift(-1).fillna(0).values
    take = proba >= min_confidence

    if take.sum() == 0:
        return {
            "min_confidence": min_confidence,
            "trades": 0,
            "win_rate": 0.0,
            "return_pct": 0.0,
        }

    wins = (aligned_y.values[take] == 1).sum()
    trade_returns = returns[take] * (proba[take] >= min_confidence).astype(float)
    # Long only when confident up
    strategy_ret = np.where(take, returns, 0)

    return {
        "min_confidence": min_confidence,
        "trades": int(take.sum()),
        "win_rate": float(wins / take.sum()),
        "return_pct": float(strategy_ret[take].sum() * 100),
    }


def find_best_confidence(
    model,
    model_type: str,
    val_x: pd.DataFrame,
    val_y: pd.Series,
    val_featured: pd.DataFrame,
    feature_cols: list[str],
    min_trades: int = 15,
) -> tuple[float, dict]:
    """Zoek confidence drempel met hoogste win rate (min. min_trades)."""
    best_conf = 0.75
    best_stats = {"win_rate": 0.0, "trades": 0}

    for conf in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
        stats = backtest_with_confidence(
            model, model_type, val_x, val_y, val_featured, feature_cols, conf
        )
        if stats["trades"] >= min_trades and stats["win_rate"] > best_stats.get(
            "win_rate", 0
        ):
            best_conf = conf
            best_stats = stats

    return best_conf, best_stats


def find_aggressive_confidence(
    model,
    model_type: str,
    val_x: pd.DataFrame,
    val_y: pd.Series,
    val_featured: pd.DataFrame,
    feature_cols: list[str],
) -> tuple[float, dict]:
    """Agressief: laagste confidence met hoogste backtest return (meer trades)."""
    best_conf = 0.55
    best_stats = {"return_pct": -999.0, "trades": 0, "win_rate": 0.0}

    for conf in [0.52, 0.55, 0.58, 0.60, 0.62, 0.65, 0.68, 0.70]:
        stats = backtest_with_confidence(
            model, model_type, val_x, val_y, val_featured, feature_cols, conf
        )
        if stats["trades"] >= 20 and stats["return_pct"] > best_stats["return_pct"]:
            best_conf = conf
            best_stats = stats

    return best_conf, best_stats
