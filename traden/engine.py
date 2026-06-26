import logging
from dataclasses import dataclass

from traden.activity import log_scan
from traden.brokers.base import Broker
from traden.brokers.crypto import CryptoBroker
from traden.brokers.paper import PaperBroker
from traden.brokers.stock import StockBroker
from traden.config import Settings
from traden.models import AssetClass, Side
from traden.risk import RiskManager
from traden.strategies.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class MarketRunner:
    broker: Broker
    strategy: Strategy
    symbols: list[str]
    risk: RiskManager


def create_brokers(settings: Settings) -> dict[AssetClass, Broker]:
    brokers: dict[AssetClass, Broker] = {}

    if settings.is_live:
        if settings.crypto_api_key and settings.crypto_api_secret:
            brokers[AssetClass.CRYPTO] = CryptoBroker(
                exchange_id=settings.crypto_exchange,
                api_key=settings.crypto_api_key,
                api_secret=settings.crypto_api_secret,
                sandbox=settings.crypto_sandbox,
            )
        if settings.alpaca_api_key and settings.alpaca_api_secret:
            brokers[AssetClass.STOCK] = StockBroker(
                api_key=settings.alpaca_api_key,
                api_secret=settings.alpaca_api_secret,
                base_url=settings.alpaca_base_url,
            )
    else:
        brokers[AssetClass.CRYPTO] = PaperBroker(AssetClass.CRYPTO)
        brokers[AssetClass.STOCK] = PaperBroker(AssetClass.STOCK)

    return brokers


class TradingEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.risk = RiskManager(settings)
        self.brokers = create_brokers(settings)
        self.runners: list[MarketRunner] = []

    def setup(self, strategies: dict[AssetClass, Strategy]) -> None:
        symbol_map = {
            AssetClass.CRYPTO: self.settings.crypto_symbol_list(),
            AssetClass.STOCK: self.settings.stock_symbol_list(),
        }
        for asset_class, strategy in strategies.items():
            broker = self.brokers.get(asset_class)
            if broker is None:
                continue
            self.runners.append(
                MarketRunner(
                    broker=broker,
                    strategy=strategy,
                    symbols=symbol_map[asset_class],
                    risk=self.risk,
                )
            )

    def run_once(self) -> None:
        mode = "LIVE" if self.settings.is_live else "PAPER"
        logger.info("=== Scan gestart (%s) ===", mode)

        for runner in self.runners:
            try:
                self._run_market(runner)
            except Exception as exc:
                logger.exception(
                    "Scan mislukt voor %s — bot blijft draaien: %s",
                    runner.strategy.asset_class.value,
                    exc,
                )

    def _run_market(self, runner: MarketRunner) -> None:
        logger.info(
            "Markt: %s | Broker: %s | Symbolen: %s",
            runner.strategy.asset_class.value,
            runner.broker.name,
            ", ".join(runner.symbols),
        )

        signals = runner.strategy.scan(runner.broker, runner.symbols)
        scan_signals: list[dict] = []
        scan_trades: list[dict] = []

        for signal in signals:
            scan_signals.append(
                {
                    "side": signal.side.value,
                    "symbol": signal.symbol,
                    "reason": signal.reason,
                }
            )
            logger.info(
                "Signaal: %s %s %s — %s",
                signal.side.value.upper(),
                signal.symbol,
                signal.asset_class.value,
                signal.reason,
            )

            if signal.side == Side.SELL:
                result = runner.broker.close_position(signal.symbol)
            else:
                order = runner.risk.build_order(runner.broker, signal)
                if order is None:
                    continue
                result = runner.broker.place_order(order)

            if result.success:
                scan_trades.append(
                    {
                        "id": result.order_id,
                        "symbol": result.symbol,
                        "side": result.side.value,
                        "quantity": result.quantity,
                        "price": result.fill_price,
                    }
                )
                logger.info(
                    "Order OK: %s qty=%.4f price=%s",
                    result.order_id,
                    result.quantity,
                    result.fill_price,
                )
            else:
                logger.error("Order mislukt: %s", result.message)

        balance = runner.broker.get_balance()
        positions = runner.broker.get_positions()
        logger.info("Saldo: %.2f | Open posities: %d", balance, len(positions))
        for pos in positions:
            logger.info(
                "  %s: qty=%.4f entry=%.4f pnl=%.2f",
                pos.symbol,
                pos.quantity,
                pos.avg_entry,
                pos.unrealized_pnl,
            )

        log_scan(
            market=runner.strategy.asset_class.value,
            balance=balance,
            positions=len(positions),
            signals=scan_signals,
            trades=scan_trades,
            scores=getattr(runner.strategy, "last_scores", []),
        )
