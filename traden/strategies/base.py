from abc import ABC, abstractmethod

from traden.brokers.base import Broker
from traden.models import Signal


class Strategy(ABC):
    name: str

    @abstractmethod
    def scan(self, broker: Broker, symbols: list[str]) -> list[Signal]:
        ...
