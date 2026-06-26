"""Train and evaluate ML trading models — full pipeline."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, precision_score

from traden.ml.data import fetch_ohlcv
from traden.ml.features import build_features, build_labels, get_feature_columns
from traden.ml.precision import (
    backtest_with_confidence,
    find_aggressive_confidence,
    find_best_confidence,
)
from traden.ml.lstm_model import SequenceModel
from traden.ml.tuning import tune_gradient_boosting

logger = logging.getLogger(__name__)
MODELS_DIR = Path("models")
TRAINING_LOG = Path("data/training_history.json")


@dataclass
class TrainResult:
    symbol: str
    market: str
    model_path: Path
    model_type: str
    train_samples: int
    test_samples: int
    candles: int
    months: int
    accuracy: float
    precision: float
    backtest_return_pct: float
    win_rate: float
    optimal_confidence: float
    precision_trades: int
    report: str


def _symbol_key(symbol: str) -> str:
    return symbol.replace("/", "_").replace(".", "_")


def _prepare_dataset(
    df: pd.DataFrame,
    symbol: str,
    market: str,
    forward_bars: int,
    threshold: float,
) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    featured = build_features(df, symbol=symbol, market=market, with_sentiment=True)
    labels = build_labels(featured, forward_bars=forward_bars, threshold=threshold)
    feature_cols = get_feature_columns(with_sentiment=True)
    dataset = featured[feature_cols].copy()
    dataset["label"] = labels
    dataset = dataset.dropna()
    dataset = dataset[dataset["label"].isin([0.0, 1.0])]
    return dataset, dataset["label"].astype(int), feature_cols


def _backtest_on_test(
    test_df: pd.DataFrame,
    y_true: pd.Series,
    y_pred: np.ndarray,
) -> float:
    returns = test_df["return_1"].shift(-1).fillna(0)
    aligned = returns.loc[y_true.index]
    strategy_returns = aligned * y_pred
    return float(strategy_returns.sum() * 100)


def _save_training_log(entry: dict) -> None:
    TRAINING_LOG.parent.mkdir(parents=True, exist_ok=True)
    history: list[dict] = []
    if TRAINING_LOG.exists():
        try:
            history = json.loads(TRAINING_LOG.read_text())
        except json.JSONDecodeError:
            history = []
    history.append(entry)
    TRAINING_LOG.write_text(json.dumps(history[-100:], indent=2))


def _train_gb(
    train_x: pd.DataFrame,
    train_y: pd.Series,
    test_x: pd.DataFrame,
    test_y: pd.Series,
    test_featured: pd.DataFrame,
    tune: bool,
) -> tuple[object, float, float, float, str]:
    if tune and len(train_x) >= 200:
        model = tune_gradient_boosting(train_x, train_y)
    else:
        model = GradientBoostingClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42
        )
        model.fit(train_x, train_y)

    y_pred = model.predict(test_x)
    accuracy = accuracy_score(test_y, y_pred)
    precision = precision_score(test_y, y_pred, zero_division=0)
    report = classification_report(test_y, y_pred, zero_division=0)
    backtest = _backtest_on_test(test_featured, test_y, y_pred)
    return model, accuracy, precision, backtest, report


def _train_sequence(
    train_x: pd.DataFrame,
    train_y: pd.Series,
    test_x: pd.DataFrame,
    test_y: pd.Series,
    test_featured: pd.DataFrame,
    feature_cols: list[str],
) -> tuple[object, float, float, float, str]:
    model = SequenceModel(seq_len=20)
    model.fit(train_x[feature_cols], train_y)
    y_pred = model.predict(test_x[feature_cols])
    test_y_aligned = test_y.iloc[model.seq_len : model.seq_len + len(y_pred)]
    min_len = min(len(y_pred), len(test_y_aligned))
    y_pred = y_pred[:min_len]
    test_y_aligned = test_y_aligned.iloc[:min_len]
    test_featured_aligned = test_featured.iloc[model.seq_len : model.seq_len + min_len]

    accuracy = accuracy_score(test_y_aligned, y_pred)
    precision = precision_score(test_y_aligned, y_pred, zero_division=0)
    report = classification_report(test_y_aligned, y_pred, zero_division=0)
    backtest = _backtest_on_test(test_featured_aligned, test_y_aligned, y_pred)
    return model, accuracy, precision, backtest, report


def train_model(
    symbol: str,
    market: str = "crypto",
    timeframe: str = "15m",
    months: int = 12,
    forward_bars: int = 4,
    threshold: float = 0.003,
    test_ratio: float = 0.2,
    tune: bool = True,
    use_sequence: bool = True,
    use_cache: bool = True,
    precision_mode: bool = True,
    aggressive_mode: bool = False,
) -> TrainResult:
    if aggressive_mode:
        timeframe = "5m"
        forward_bars = 2
        threshold = 0.0015
        precision_mode = False
    label_threshold = 0.005 if precision_mode else threshold
    df = fetch_ohlcv(
        symbol, market=market, months=months, timeframe=timeframe, use_cache=use_cache
    )

    if len(df) < 300:
        raise ValueError(f"Te weinig data voor {symbol}: {len(df)} candles")

    dataset, labels, feature_cols = _prepare_dataset(
        df, symbol, market, forward_bars, label_threshold
    )
    split_idx = int(len(dataset) * (1 - test_ratio))
    val_idx = int(split_idx * 0.85)
    train_x = dataset[feature_cols].iloc[:val_idx]
    train_y = labels.iloc[:val_idx]
    val_x = dataset[feature_cols].iloc[val_idx:split_idx]
    val_y = labels.iloc[val_idx:split_idx]
    test_x = dataset[feature_cols].iloc[split_idx:]
    test_y = labels.iloc[split_idx:]
    val_featured = build_features(df, symbol=symbol, market=market).loc[val_y.index]
    test_featured = build_features(df, symbol=symbol, market=market).loc[test_y.index]

    candidates: list[tuple[str, object, float, float, float, str]] = []

    gb_model, gb_acc, gb_prec, gb_bt, gb_report = _train_gb(
        train_x, train_y, test_x, test_y, test_featured, tune
    )
    candidates.append(("gradient_boosting", gb_model, gb_acc, gb_prec, gb_bt, gb_report))

    if use_sequence and len(train_x) >= 100:
        try:
            seq_model, seq_acc, seq_prec, seq_bt, seq_report = _train_sequence(
                train_x, train_y, test_x, test_y, test_featured, feature_cols
            )
            candidates.append(
                ("sequence", seq_model, seq_acc, seq_prec, seq_bt, seq_report)
            )
        except Exception as exc:
            logger.warning("Sequence model mislukt voor %s: %s", symbol, exc)

    # Kies model met beste backtest op testdata
    best = max(candidates, key=lambda c: c[4])
    model_type, model, accuracy, precision, backtest_return, report = best

    optimal_conf = 0.75
    win_rate = 0.0
    precision_trades = 0
    if aggressive_mode:
        optimal_conf, val_stats = find_aggressive_confidence(
            model, model_type, val_x, val_y, val_featured, feature_cols
        )
        test_stats = backtest_with_confidence(
            model, model_type, test_x, test_y, test_featured, feature_cols, optimal_conf
        )
        win_rate = test_stats["win_rate"]
        precision_trades = test_stats["trades"]
        logger.info(
            "%s AGGRESSIVE: conf=%.0f%% → return %+.2f%% | win rate %.1f%% (%d trades)",
            symbol,
            optimal_conf * 100,
            test_stats["return_pct"],
            win_rate * 100,
            precision_trades,
        )
    elif precision_mode:
        optimal_conf, val_stats = find_best_confidence(
            model, model_type, val_x, val_y, val_featured, feature_cols
        )
        test_stats = backtest_with_confidence(
            model,
            model_type,
            test_x,
            test_y,
            test_featured,
            feature_cols,
            optimal_conf,
        )
        win_rate = test_stats["win_rate"]
        precision_trades = test_stats["trades"]
        logger.info(
            "%s precision: conf=%.0f%% → win rate %.1f%% (%d trades)",
            symbol,
            optimal_conf * 100,
            win_rate * 100,
            precision_trades,
        )

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / f"{market}_{_symbol_key(symbol)}.joblib"
    meta = {
        "symbol": symbol,
        "market": market,
        "timeframe": timeframe,
        "months": months,
        "model_type": model_type,
        "forward_bars": forward_bars,
        "threshold": threshold,
        "feature_columns": feature_cols,
        "candles": len(df),
        "accuracy": accuracy,
        "precision": precision,
        "backtest_return_pct": backtest_return,
        "precision_mode": precision_mode,
        "aggressive_mode": aggressive_mode,
        "optimal_confidence": optimal_conf,
        "win_rate": win_rate,
        "precision_trades": precision_trades,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "all_candidates": [
            {"type": c[0], "accuracy": c[2], "precision": c[3], "backtest": c[4]}
            for c in candidates
        ],
    }
    joblib.dump({"model": model, "meta": meta}, model_path)
    model_path.with_suffix(".json").write_text(json.dumps(meta, indent=2))

    _save_training_log(
        {
            "timestamp": meta["trained_at"],
            "symbol": symbol,
            "market": market,
            "model_type": model_type,
            "accuracy": accuracy,
            "backtest_return_pct": backtest_return,
            "candles": len(df),
        }
    )

    return TrainResult(
        symbol=symbol,
        market=market,
        model_path=model_path,
        model_type=model_type,
        train_samples=len(train_x),
        test_samples=len(test_x),
        candles=len(df),
        months=months,
        accuracy=accuracy,
        precision=precision,
        backtest_return_pct=backtest_return,
        win_rate=win_rate,
        optimal_confidence=optimal_conf,
        precision_trades=precision_trades,
        report=report,
    )


def load_model(symbol: str, market: str = "crypto"):
    path = MODELS_DIR / f"{market}_{_symbol_key(symbol)}.joblib"
    if not path.exists():
        return None
    return joblib.load(path)
