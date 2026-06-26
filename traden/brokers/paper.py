import json
from datetime import datetime, timezone
from pathlib import Path

from traden.brokers.base import Broker
from traden.models import (
    AssetClass,
    Order,
    OrderResult,
    Position,
    Quote,
    Side,
)


class PaperBroker(Broker):
    """Simuleert orders lokaal — geen echte API nodig."""

    name = "paper"

    def __init__(
        self,
        asset_class: AssetClass,
        initial_balance: float = 10_000.0,
        state_file: Path | None = None,
    ):
        self.asset_class = asset_class
        self.state_file = state_file or Path(f"data/paper_{asset_class.value}.json")
        self._balance = initial_balance
        self._positions: dict[str, Position] = {}
        self._order_counter = 0
        self._price_cache: dict[str, float] = {}
        self._trades: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.state_file.exists():
            return
        data = json.loads(self.state_file.read_text())
        self._balance = data.get("balance", self._balance)
        self._order_counter = data.get("order_counter", 0)
        self._trades = data.get("trades", [])
        for sym, pos in data.get("positions", {}).items():
            self._positions[sym] = Position(
                symbol=sym,
                asset_class=self.asset_class,
                quantity=pos["quantity"],
                avg_entry=pos["avg_entry"],
                current_price=pos.get("current_price", pos["avg_entry"]),
            )

    def _save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "balance": self._balance,
            "order_counter": self._order_counter,
            "trades": self._trades[-100:],
            "positions": {
                sym: {
                    "quantity": p.quantity,
                    "avg_entry": p.avg_entry,
                    "current_price": p.current_price,
                }
                for sym, p in self._positions.items()
            },
        }
        self.state_file.write_text(json.dumps(payload, indent=2))

    def set_market_price(self, symbol: str, price: float) -> None:
        self._price_cache[symbol] = price
        if symbol in self._positions:
            self._positions[symbol].current_price = price

    def get_balance(self) -> float:
        return self._balance

    def get_quote(self, symbol: str) -> Quote:
        price = self._price_cache.get(symbol, 100.0)
        return Quote(
            symbol=symbol,
            asset_class=self.asset_class,
            bid=price * 0.9999,
            ask=price * 1.0001,
            last=price,
        )

    def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    def place_order(self, order: Order) -> OrderResult:
        quote = self.get_quote(order.symbol)
        fill_price = quote.ask if order.side == Side.BUY else quote.bid
        cost = fill_price * order.quantity

        self._order_counter += 1
        order_id = f"PAPER-{self._order_counter}"

        if order.side == Side.BUY:
            if cost > self._balance:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    message=f"Onvoldoende saldo: {self._balance:.2f} < {cost:.2f}",
                )
            self._balance -= cost
            existing = self._positions.get(order.symbol)
            if existing:
                total_qty = existing.quantity + order.quantity
                avg = (
                    existing.avg_entry * existing.quantity + fill_price * order.quantity
                ) / total_qty
                existing.quantity = total_qty
                existing.avg_entry = avg
                existing.current_price = fill_price
            else:
                self._positions[order.symbol] = Position(
                    symbol=order.symbol,
                    asset_class=self.asset_class,
                    quantity=order.quantity,
                    avg_entry=fill_price,
                    current_price=fill_price,
                )
        else:
            existing = self._positions.get(order.symbol)
            if not existing or existing.quantity < order.quantity:
                return OrderResult(
                    success=False,
                    order_id=order_id,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    message="Geen positie om te verkopen",
                )
            self._balance += cost
            existing.quantity -= order.quantity
            if existing.quantity <= 1e-9:
                del self._positions[order.symbol]

        self._trades.append(
            {
                "id": order_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": order.symbol,
                "side": order.side.value,
                "quantity": order.quantity,
                "price": fill_price,
                "total": fill_price * order.quantity,
            }
        )
        self._save()
        return OrderResult(
            success=True,
            order_id=order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            fill_price=fill_price,
            message="Paper order uitgevoerd",
        )

    def close_position(self, symbol: str) -> OrderResult:
        pos = self._positions.get(symbol)
        if not pos:
            return OrderResult(
                success=False,
                order_id="",
                symbol=symbol,
                side=Side.SELL,
                quantity=0,
                message="Geen open positie",
            )
        return self.place_order(
            Order(
                symbol=symbol,
                asset_class=self.asset_class,
                side=Side.SELL,
                quantity=pos.quantity,
            )
        )
