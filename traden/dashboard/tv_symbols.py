"""TradingView symbol mapping."""

CRYPTO_EXCHANGE = "BINANCE"


def to_tradingview_symbol(symbol: str, market: str) -> str:
    if market == "crypto":
        pair = symbol.replace("/", "")
        return f"{CRYPTO_EXCHANGE}:{pair}"
    # US stocks — NASDAQ default; AAPL, MSFT, NVDA zijn NASDAQ
    return f"NASDAQ:{symbol}"


def chart_url(symbol: str, market: str, interval: str = "15") -> str:
    tv = to_tradingview_symbol(symbol, market)
    return f"https://www.tradingview.com/chart/?symbol={tv}&interval={interval}"
