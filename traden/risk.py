import logging
from dataclasses import dataclass, field
from datetime import date

from traden.brokers.base import Broker
from traden.config import Settings
from traden.models import Order, Side, Signal

logger = logging.getLogger(__name__)


@dataclass
class RiskState:
    starting_balance: float
    daily_pnl: float = 0.0
    trades_today: int = 0
    last_reset: date = field(default_factory=date.today)


class RiskManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._states: dict[str, RiskState] = {}

    def _state_for(self, broker: Broker) -> RiskState:
        if broker.name not in self._states:
            balance = broker.get_balance()
            self._states[broker.name] = RiskState(starting_balance=balance)
        state = self._states[broker.name]
        today = date.today()
        if state.last_reset != today:
            state.daily_pnl = 0.0
            state.trades_today = 0
            state.starting_balance = broker.get_balance()
            state.last_reset = today
        return state

    def can_trade(self, broker: Broker) -> tuple[bool, str]:
        state = self._state_for(broker)
        balance = broker.get_balance()
        if balance <= 0:
            return False, "Geen saldo"

        max_loss = state.starting_balance * (self.settings.max_daily_loss_pct / 100)
        if state.daily_pnl <= -max_loss:
            return False, f"Dagelijkse verlieslimiet bereikt ({state.daily_pnl:.2f})"

        open_count = len(broker.get_positions())
        if open_count >= self.settings.max_open_positions:
            return False, f"Max open posities ({open_count})"

        return True, "OK"

    def position_size(
        self,
        broker: Broker,
        entry_price: float,
        stop_loss: float,
    ) -> float:
        balance = broker.get_balance()
        risk_amount = balance * (self.settings.max_risk_per_trade_pct / 100)
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0:
            return 0.0
        size = risk_amount / risk_per_unit
        max_affordable = (balance * 0.95) / entry_price
        return min(size, max_affordable)

    def build_order(self, broker: Broker, signal: Signal) -> Order | None:
        allowed, reason = self.can_trade(broker)
        if not allowed:
            logger.warning("Trade geblokkeerd: %s", reason)
            return None

        quote = broker.get_quote(signal.symbol)
        entry = quote.ask if signal.side == Side.BUY else quote.bid

        stop = signal.stop_loss
        if stop is None:
            stop = entry * (0.98 if signal.side == Side.BUY else 1.02)

        qty = self.position_size(broker, entry, stop)
        if qty <= 0:
            logger.warning("Positiegrootte te klein voor %s", signal.symbol)
            return None

        # Afronden voor stocks (hele aandelen)
        if signal.asset_class.value == "stock":
            qty = max(1, int(qty))

        return Order(
            symbol=signal.symbol,
            asset_class=signal.asset_class,
            side=signal.side,
            quantity=qty,
            stop_loss=stop,
            take_profit=signal.take_profit,
        )

    def record_fill(self, broker: Broker, pnl: float) -> None:
        state = self._state_for(broker)
        state.daily_pnl += pnl
        state.trades_today += 1
