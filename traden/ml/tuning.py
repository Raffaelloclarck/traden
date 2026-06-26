"""Hyperparameter tuning voor ML modellen."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit

logger = logging.getLogger(__name__)

PARAM_DIST = {
    "n_estimators": [100, 200, 300, 400],
    "max_depth": [3, 4, 5, 6],
    "learning_rate": [0.01, 0.03, 0.05, 0.1],
    "min_samples_leaf": [2, 5, 10, 20],
    "subsample": [0.7, 0.8, 0.9, 1.0],
}


def tune_gradient_boosting(
    train_x: pd.DataFrame,
    train_y: pd.Series,
    n_iter: int = 20,
) -> GradientBoostingClassifier:
    base = GradientBoostingClassifier(random_state=42)
    tscv = TimeSeriesSplit(n_splits=3)
    search = RandomizedSearchCV(
        base,
        PARAM_DIST,
        n_iter=n_iter,
        cv=tscv,
        scoring="precision",
        random_state=42,
        n_jobs=-1,
        error_score=0,
    )
    logger.info("Hyperparameter tuning (%d iteraties)...", n_iter)
    search.fit(train_x, train_y)
    logger.info(
        "Beste params: %s (score %.3f)",
        search.best_params_,
        search.best_score_,
    )
    return search.best_estimator_
