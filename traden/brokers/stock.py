import logging

from traden.brokers.base import Broker
from traden.models import AssetClass, Order, OrderResult, Position, Quote, Side

logger = logging.getLogger(__name__)


class StockBroker(Broker):
    """Live US stocks via Alpaca API."""

    name = "stock"

    def __init__(self, api_key: str, api_secret: str, base_url: str):
        from alpaca.trading.client import TradingClient
        from alpaca.data.historical import StockHistoricalDataClient

        self.trading = TradingClient(api_key, api_secret, paper="paper" in base_url)
        self.data = StockHistoricalDataClient(api_key, api_secret)

    def get_balance(self) -> float:
        account = self.trading.get_account()
        return float(account.cash)

    def get_quote(self, symbol: str) -> Quote:
        from alpaca.data.requests import StockLatestQuoteRequest

        req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
        quotes = self.data.get_stock_latest_quote(req)
        q = quotes[symbol]
        bid = float(q.bid_price)
        ask = float(q.ask_price)
        last = (bid + ask) / 2 if bid and ask else bid or ask
        return Quote(
            symbol=symbol,
            asset_class=AssetClass.STOCK,
            bid=bid,
            ask=ask,
            last=last,
        )

    def get_positions(self) -> list[Position]:
        positions = self.trading.get_all_positions()
        result: list[Position] = []
        for p in positions:
            result.append(
                Position(
                    symbol=p.symbol,
                    asset_class=AssetClass.STOCK,
                    quantity=float(p.qty),
                    avg_entry=float(p.avg_entry_price),
                    current_price=float(p.current_price),
                )
            )
        return result

    def place_order(self, order: Order) -> OrderResult:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        side = OrderSide.BUY if order.side == Side.BUY else OrderSide.SELL
        try:
            req = MarketOrderRequest(
                symbol=order.symbol,
                qty=order.quantity,
                side=side,
                time_in_force=TimeInForce.DAY,
            )
            result = self.trading.submit_order(req)
            return OrderResult(
                success=True,
                order_id=str(result.id),
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                fill_price=float(result.filled_avg_price or 0) or None,
                message="Live stock order geplaatst",
            )
        except Exception as exc:
            logger.exception("Stock order mislukt")
            return OrderResult(
                success=False,
                order_id="",
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                message=str(exc),
            )

    def close_position(self, symbol: str) -> OrderResult:
        try:
            self.trading.close_position(symbol)
            return OrderResult(
                success=True,
                order_id="",
                symbol=symbol,
                side=Side.SELL,
                quantity=0,
                message="Positie gesloten",
            )
        except Exception as exc:
            return OrderResult(
                success=False,
                order_id="",
                symbol=symbol,
                side=Side.SELL,
                quantity=0,
                message=str(exc),
            )
