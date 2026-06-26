from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class AssetClass(str, Enum):
    CRYPTO = "crypto"
    STOCK = "stock"


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


@dataclass
class Quote:
    symbol: str
    asset_class: AssetClass
    bid: float
    ask: float
    last: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Position:
    symbol: str
    asset_class: AssetClass
    quantity: float
    avg_entry: float
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.avg_entry) * self.quantity


@dataclass
class Order:
    symbol: str
    asset_class: AssetClass
    side: Side
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


@dataclass
class OrderResult:
    success: bool
    order_id: str
    symbol: str
    side: Side
    quantity: float
    fill_price: Optional[float] = None
    message: str = ""


@dataclass
class Signal:
    symbol: str
    asset_class: AssetClass
    side: Side
    strength: float  # 0.0 - 1.0
    reason: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
