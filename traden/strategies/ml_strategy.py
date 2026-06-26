import logging

import pandas as pd

from traden.brokers.base import Broker
from traden.config import load_settings
from traden.ml.data import fetch_crypto_ohlcv, fetch_stock_ohlcv
from traden.ml.features import build_features, get_feature_columns
from traden.ml.train import load_model
from traden.models import AssetClass, Side, Signal
from traden.strategies.base import Strategy

logger = logging.getLogger(__name__)


class MLStrategy(Strategy):
    """Trades op basis van getraind ML model (GB of Sequence NN)."""

    name = "ml"

    def __init__(
        self,
        asset_class: AssetClass,
        timeframe: str = "15m",
        buy_threshold: float | None = None,
        sell_threshold: float | None = None,
    ):
        settings = load_settings()
        self.asset_class = asset_class
        self.timeframe = timeframe
        self.buy_threshold = buy_threshold or settings.ml_buy_threshold
        self.sell_threshold = sell_threshold or settings.ml_sell_threshold
        self.market = "crypto" if asset_class == AssetClass.CRYPTO else "stock"
        self.last_scores: list[dict] = []

    def _fetch_df(self, broker: Broker, symbol: str) -> pd.DataFrame:
        if self.market == "crypto":
            df = fetch_crypto_ohlcv(symbol, timeframe=self.timeframe, limit=200)
        else:
            df = fetch_stock_ohlcv(symbol, interval=self.timeframe)

        if hasattr(broker, "set_market_price") and not df.empty:
            broker.set_market_price(symbol, float(df["close"].iloc[-1]))
        return df

    def _predict_proba(self, bundle: dict, featured: pd.DataFrame) -> float:
        model = bundle["model"]
        meta = bundle["meta"]
        cols = meta.get("feature_columns", get_feature_columns(with_sentiment=True))

        if meta.get("model_type") == "sequence":
            return float(model.predict_last_proba(featured[cols])[0][1])

        row = featured[cols].iloc[[-1]]
        return float(model.predict_proba(row)[0][1])

    def scan(self, broker: Broker, symbols: list[str]) -> list[Signal]:
        self.last_scores = []
        signals: list[Signal] = []
        positions = {p.symbol for p in broker.get_positions()}

        for symbol in symbols:
            bundle = load_model(symbol, market=self.market)
            if bundle is None:
                logger.warning("Geen model voor %s — run: python train.py --all", symbol)
                continue

            meta = bundle["meta"]
            buy_at = meta.get("optimal_confidence", self.buy_threshold)

            try:
                df = self._fetch_df(broker, symbol)
            except Exception as exc:
                logger.warning("Data ophalen mislukt voor %s: %s", symbol, exc)
                continue

            if df.empty or "close" not in df.columns:
                logger.warning("Geen prijsdata voor %s — overslaan", symbol)
                continue

            featured = build_features(
                df, symbol=symbol, market=self.market, with_sentiment=True
            ).dropna()
            if len(featured) < 25:
                continue

            proba_up = self._predict_proba(bundle, featured)
            price = float(df["close"].iloc[-1])
            atr = float(featured["atr_14"].iloc[-1]) if "atr_14" in featured else 0.01
            stop = price * (1 - max(atr * 2, 0.005))
            in_position = symbol in positions
            action = "hold"
            if not in_position and proba_up >= buy_at:
                action = "buy"
            elif in_position and proba_up <= self.sell_threshold:
                action = "sell"

            self.last_scores.append(
                {
                    "symbol": symbol,
                    "score": round(proba_up, 4),
                    "threshold": round(buy_at, 4),
                    "price": round(price, 2),
                    "action": action,
                    "in_position": in_position,
                    "model": meta.get("model_type", "?"),
                }
            )

            if action == "buy":
                win_rate = meta.get("win_rate", 0)
                signals.append(
                    Signal(
                        symbol=symbol,
                        asset_class=self.asset_class,
                        side=Side.BUY,
                        strength=proba_up,
                        reason=(
                            f"AI koop {proba_up:.0%} (drempel {buy_at:.0%}, "
                            f"win rate {win_rate:.0%})"
                        ),
                        stop_loss=stop,
                        take_profit=price * (1 + max(atr * 3, 0.01)),
                    )
                )
            elif action == "sell":
                signals.append(
                    Signal(
                        symbol=symbol,
                        asset_class=self.asset_class,
                        side=Side.SELL,
                        strength=1 - proba_up,
                        reason=f"AI verkoop ({proba_up:.0%})",
                    )
                )

            logger.info(
                "%s AI [%s]: %.1f%% | acc %.1f%% | %d candles training",
                symbol,
                meta.get("model_type", "?"),
                proba_up * 100,
                meta.get("accuracy", 0) * 100,
                meta.get("candles", 0),
            )

        return signals
