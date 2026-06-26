import logging

from traden.brokers.base import Broker
from traden.models import AssetClass, Side, Signal
from traden.strategies.base import Strategy

logger = logging.getLogger(__name__)


class MomentumStrategy(Strategy):
    """
    Eenvoudige momentum-strategie:
    - Haalt OHLCV candles op
    - Koopt bij breakout boven recent high
    - Verkoopt bij breakdown onder recent low
    """

    name = "momentum"

    def __init__(
        self,
        asset_class: AssetClass,
        lookback: int = 20,
        timeframe: str = "5m",
    ):
        self.asset_class = asset_class
        self.lookback = lookback
        self.timeframe = timeframe

    def _fetch_ohlcv(self, broker: Broker, symbol: str) -> list[list]:
        if hasattr(broker, "exchange"):
            return broker.exchange.fetch_ohlcv(
                symbol, timeframe=self.timeframe, limit=self.lookback + 1
            )

        if self.asset_class == AssetClass.STOCK:
            return self._fetch_stock_ohlcv(broker, symbol)

        import ccxt

        public = ccxt.binance({"enableRateLimit": True})
        candles = public.fetch_ohlcv(
            symbol, timeframe=self.timeframe, limit=self.lookback + 1
        )
        if hasattr(broker, "set_market_price") and candles:
            broker.set_market_price(symbol, candles[-1][4])
        return candles

    def _fetch_stock_ohlcv(self, broker: Broker, symbol: str) -> list[list]:
        import yfinance as yf

        interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}
        interval = interval_map.get(self.timeframe, "15m")
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="5d", interval=interval)
        if df.empty:
            return []

        candles = []
        for ts, row in df.iterrows():
            candles.append(
                [
                    int(ts.timestamp() * 1000),
                    float(row["Open"]),
                    float(row["High"]),
                    float(row["Low"]),
                    float(row["Close"]),
                    float(row["Volume"]),
                ]
            )
        candles = candles[-(self.lookback + 1) :]
        if hasattr(broker, "set_market_price") and candles:
            broker.set_market_price(symbol, candles[-1][4])
        return candles

    def scan(self, broker: Broker, symbols: list[str]) -> list[Signal]:
        signals: list[Signal] = []

        for symbol in symbols:
            try:
                candles = self._fetch_ohlcv(broker, symbol)
            except Exception as exc:
                logger.warning("Geen data voor %s: %s", symbol, exc)
                continue

            if len(candles) < self.lookback + 1:
                continue

            closes = [c[4] for c in candles]
            highs = [c[2] for c in candles[:-1]]
            lows = [c[3] for c in candles[:-1]]
            current = closes[-1]
            recent_high = max(highs)
            recent_low = min(lows)

            positions = {p.symbol for p in broker.get_positions()}

            if symbol not in positions and current > recent_high:
                signals.append(
                    Signal(
                        symbol=symbol,
                        asset_class=self.asset_class,
                        side=Side.BUY,
                        strength=0.7,
                        reason=f"Breakout boven {recent_high:.4f}",
                        stop_loss=recent_low,
                        take_profit=current + (current - recent_low),
                    )
                )
            elif symbol in positions and current < recent_low:
                signals.append(
                    Signal(
                        symbol=symbol,
                        asset_class=self.asset_class,
                        side=Side.SELL,
                        strength=0.7,
                        reason=f"Breakdown onder {recent_low:.4f}",
                    )
                )

        return signals
