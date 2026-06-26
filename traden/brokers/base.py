from abc import ABC, abstractmethod

from traden.models import Order, OrderResult, Position, Quote


class Broker(ABC):
    name: str

    @abstractmethod
    def get_balance(self) -> float:
        """Beschikbaar kapitaal in quote currency (USD/USDT)."""

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        ...

    @abstractmethod
    def get_positions(self) -> list[Position]:
        ...

    @abstractmethod
    def place_order(self, order: Order) -> OrderResult:
        ...

    @abstractmethod
    def close_position(self, symbol: str) -> OrderResult:
        ...
