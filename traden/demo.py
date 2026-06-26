"""Plaats demo paper trades zodat dashboard direct activiteit toont."""

import logging

import ccxt
import yfinance as yf

from traden.activity import log_scan
from traden.brokers.paper import PaperBroker
from traden.models import AssetClass, Order, Side

logger = logging.getLogger(__name__)


def _crypto_price(symbol: str) -> float:
    exchange = ccxt.binance({"enableRateLimit": True})
    ticker = exchange.fetch_ticker(symbol)
    return float(ticker["last"])


def _stock_price(symbol: str) -> float:
    info = yf.Ticker(symbol).fast_info
    return float(getattr(info, "last_price", None) or info.last_price)


def run_demo_trades(crypto_symbol: str = "BTC/USDT", stock_symbol: str = "AAPL") -> None:
    crypto = PaperBroker(AssetClass.CRYPTO)
    stock = PaperBroker(AssetClass.STOCK)

    btc_price = _crypto_price(crypto_symbol)
    aapl_price = _stock_price(stock_symbol)

    crypto.set_market_price(crypto_symbol, btc_price)
    stock.set_market_price(stock_symbol, aapl_price)

    btc_qty = round(100 / btc_price, 6)
    aapl_qty = max(1, int(100 / aapl_price))

    crypto_result = crypto.place_order(
        Order(
            symbol=crypto_symbol,
            asset_class=AssetClass.CRYPTO,
            side=Side.BUY,
            quantity=btc_qty,
        )
    )
    stock_result = stock.place_order(
        Order(
            symbol=stock_symbol,
            asset_class=AssetClass.STOCK,
            side=Side.BUY,
            quantity=aapl_qty,
        )
    )

    log_scan(
        market="crypto",
        balance=crypto.get_balance(),
        positions=len(crypto.get_positions()),
        signals=[{"side": "buy", "symbol": crypto_symbol, "reason": "Demo start trade"}],
        trades=[
            {
                "id": crypto_result.order_id,
                "symbol": crypto_symbol,
                "side": "buy",
                "quantity": btc_qty,
                "price": btc_price,
            }
        ],
    )
    log_scan(
        market="stock",
        balance=stock.get_balance(),
        positions=len(stock.get_positions()),
        signals=[{"side": "buy", "symbol": stock_symbol, "reason": "Demo start trade"}],
        trades=[
            {
                "id": stock_result.order_id,
                "symbol": stock_symbol,
                "side": "buy",
                "quantity": aapl_qty,
                "price": aapl_price,
            }
        ],
    )

    logger.info(
        "Demo trades: BUY %s (%.6f) @ $%.2f | BUY %s (%d) @ $%.2f",
        crypto_symbol,
        btc_qty,
        btc_price,
        stock_symbol,
        aapl_qty,
        aapl_price,
    )
