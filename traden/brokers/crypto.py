import logging

import ccxt

from traden.brokers.base import Broker
from traden.models import AssetClass, Order, OrderResult, Position, Quote, Side

logger = logging.getLogger(__name__)


class CryptoBroker(Broker):
    """Live crypto via CCXT — ondersteunt 100+ exchanges."""

    name = "crypto"

    def __init__(
        self,
        exchange_id: str,
        api_key: str,
        api_secret: str,
        sandbox: bool = True,
    ):
        exchange_class = getattr(ccxt, exchange_id, None)
        if exchange_class is None:
            raise ValueError(f"Exchange '{exchange_id}' niet gevonden in CCXT")

        config: dict = {"enableRateLimit": True}
        if api_key and api_secret:
            config["apiKey"] = api_key
            config["secret"] = api_secret

        self.exchange: ccxt.Exchange = exchange_class(config)

        if sandbox and hasattr(self.exchange, "set_sandbox_mode"):
            self.exchange.set_sandbox_mode(True)
            logger.info("Crypto sandbox/testnet actief voor %s", exchange_id)

        self.exchange.load_markets()

    def get_balance(self) -> float:
        balance = self.exchange.fetch_balance()
        usdt = balance.get("USDT") or balance.get("USD") or {}
        free = usdt.get("free", 0) if isinstance(usdt, dict) else 0
        return float(free or 0)

    def get_quote(self, symbol: str) -> Quote:
        ticker = self.exchange.fetch_ticker(symbol)
        last = float(ticker.get("last") or ticker.get("close") or 0)
        bid = float(ticker.get("bid") or last)
        ask = float(ticker.get("ask") or last)
        return Quote(
            symbol=symbol,
            asset_class=AssetClass.CRYPTO,
            bid=bid,
            ask=ask,
            last=last,
        )

    def get_positions(self) -> list[Position]:
        balance = self.exchange.fetch_balance()
        positions: list[Position] = []
        for currency, amounts in balance.get("total", {}).items():
            qty = float(amounts or 0)
            if qty <= 0 or currency in ("USDT", "USD", "EUR"):
                continue
            symbol = f"{currency}/USDT"
            if symbol not in self.exchange.markets:
                continue
            try:
                quote = self.get_quote(symbol)
            except Exception:
                continue
            positions.append(
                Position(
                    symbol=symbol,
                    asset_class=AssetClass.CRYPTO,
                    quantity=qty,
                    avg_entry=quote.last,
                    current_price=quote.last,
                )
            )
        return positions

    def place_order(self, order: Order) -> OrderResult:
        side = order.side.value
        try:
            if order.order_type.value == "market":
                result = self.exchange.create_market_order(
                    order.symbol, side, order.quantity
                )
            else:
                result = self.exchange.create_limit_order(
                    order.symbol,
                    side,
                    order.quantity,
                    order.limit_price,
                )
            fill_price = result.get("average") or result.get("price")
            return OrderResult(
                success=True,
                order_id=str(result.get("id", "")),
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                fill_price=float(fill_price) if fill_price else None,
                message="Live crypto order geplaatst",
            )
        except Exception as exc:
            logger.exception("Crypto order mislukt")
            return OrderResult(
                success=False,
                order_id="",
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                message=str(exc),
            )

    def close_position(self, symbol: str) -> OrderResult:
        positions = self.get_positions()
        pos = next((p for p in positions if p.symbol == symbol), None)
        if not pos:
            return OrderResult(
                success=False,
                order_id="",
                symbol=symbol,
                side=Side.SELL,
                quantity=0,
                message="Geen positie",
            )
        return self.place_order(
            Order(
                symbol=symbol,
                asset_class=AssetClass.CRYPTO,
                side=Side.SELL,
                quantity=pos.quantity,
            )
        )
