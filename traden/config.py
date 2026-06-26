from enum import Enum
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    trading_mode: TradingMode = TradingMode.PAPER

    max_risk_per_trade_pct: float = Field(default=1.0, ge=0.1, le=10.0)
    max_daily_loss_pct: float = Field(default=3.0, ge=0.5, le=20.0)
    max_open_positions: int = Field(default=5, ge=1, le=50)

    crypto_exchange: str = "binance"
    crypto_api_key: str = ""
    crypto_api_secret: str = ""
    crypto_sandbox: bool = True

    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    crypto_symbols: str = "ETH/USDT"
    stock_symbols: str = "AAPL"

    # ML — precision mode: hogere drempel = minder trades, hogere win rate
    ml_buy_threshold: float = Field(default=0.75, ge=0.5, le=0.99)
    ml_sell_threshold: float = Field(default=0.35, ge=0.01, le=0.5)
    ml_precision_mode: bool = True
    ml_months: int = Field(default=12, ge=3, le=24)

    # TradingView webhook
    tv_webhook_secret: str = ""
    tv_mode: bool = False  # true = alleen traden via TradingView alerts

    @property
    def is_live(self) -> bool:
        return self.trading_mode == TradingMode.LIVE

    def crypto_symbol_list(self) -> list[str]:
        return [s.strip() for s in self.crypto_symbols.split(",") if s.strip()]

    def stock_symbol_list(self) -> list[str]:
        return [s.strip() for s in self.stock_symbols.split(",") if s.strip()]


def load_settings() -> Settings:
    return Settings()
