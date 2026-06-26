"""Sequence neural network (LSTM-alternatief zonder TensorFlow)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler


class SequenceModel:
    """
    Sequence classifier: laatste N candles → MLP.
    Werkt op elke Python versie (geen TensorFlow nodig).
    """

    model_type = "sequence"

    def __init__(self, seq_len: int = 20):
        self.seq_len = seq_len
        self.scaler = StandardScaler()
        self.model = MLPClassifier(
            hidden_layer_sizes=(128, 64, 32),
            activation="relu",
            max_iter=500,
            early_stopping=True,
            validation_fraction=0.1,
            random_state=42,
        )
        self.feature_columns: list[str] = []

    def _to_sequences(
        self, features: pd.DataFrame, labels: pd.Series | None = None
    ) -> tuple[np.ndarray, np.ndarray | None]:
        cols = self.feature_columns or list(features.columns)
        values = features[cols].values
        scaled = self.scaler.fit_transform(values) if labels is not None else self.scaler.transform(values)

        xs, ys = [], []
        for i in range(self.seq_len, len(scaled)):
            xs.append(scaled[i - self.seq_len : i].flatten())
            if labels is not None:
                ys.append(labels.iloc[i])

        x_arr = np.array(xs)
        if labels is None:
            return x_arr, None
        return x_arr, np.array(ys)

    def fit(self, features: pd.DataFrame, labels: pd.Series) -> None:
        self.feature_columns = list(features.columns)
        x, y = self._to_sequences(features, labels)
        if len(x) < 50:
            raise ValueError(f"Te weinig sequences: {len(x)}")
        self.model.fit(x, y)

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        x, _ = self._to_sequences(features, None)
        if len(x) == 0:
            return np.array([0])
        return self.model.predict(x)

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        x, _ = self._to_sequences(features, None)
        if len(x) == 0:
            return np.array([[0.5, 0.5]])
        return self.model.predict_proba(x)

    def predict_last_proba(self, features: pd.DataFrame) -> np.ndarray:
        proba = self.predict_proba(features)
        return proba[[-1]]
