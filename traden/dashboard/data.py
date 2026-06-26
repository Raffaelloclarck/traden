"""Dashboard data helpers."""

import json
from pathlib import Path

import ccxt
import yfinance as yf

from traden.config import load_settings
from traden.dashboard.tv_symbols import chart_url, to_tradingview_symbol
from traden.webhook.tradingview import get_tv_trades

DATA_DIR = Path("data")
MODELS_DIR = Path("models")
INITIAL_BALANCE = 10_000.0


def _read_tv_webhook_url() -> str:
    path = DATA_DIR / "tv_webhook_url.txt"
    if path.exists():
        return path.read_text().strip()
    secret = load_settings().tv_webhook_secret or "traden-live-secret"
    return f"http://127.0.0.1:8080/webhook/tradingview?secret={secret}"


def _load_portfolio(name: str) -> dict:
    path = DATA_DIR / f"paper_{name}.json"
    if not path.exists():
        return {
            "balance": INITIAL_BALANCE,
            "order_counter": 0,
            "positions": {},
            "trades": [],
        }
    return json.loads(path.read_text())


def _live_crypto_price(symbol: str) -> float | None:
    try:
        exchange = ccxt.binance({"enableRateLimit": True})
        ticker = exchange.fetch_ticker(symbol)
        return float(ticker.get("last") or 0) or None
    except Exception:
        return None


def _live_stock_price(symbol: str) -> float | None:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = getattr(info, "last_price", None) or getattr(info, "lastPrice", None)
        return float(price) if price else None
    except Exception:
        return None


def _enrich_portfolio(name: str, is_crypto: bool) -> dict:
    data = _load_portfolio(name)
    positions_out = []
    positions_value = 0.0
    unrealized_pnl = 0.0

    for symbol, pos in data.get("positions", {}).items():
        current = (
            _live_crypto_price(symbol)
            if is_crypto
            else _live_stock_price(symbol)
        )
        if current is None:
            current = pos.get("current_price", pos["avg_entry"])

        qty = pos["quantity"]
        entry = pos["avg_entry"]
        value = qty * current
        pnl = (current - entry) * qty
        positions_value += value
        unrealized_pnl += pnl
        positions_out.append(
            {
                "symbol": symbol,
                "quantity": qty,
                "entry": entry,
                "current": current,
                "value": value,
                "pnl": pnl,
                "pnl_pct": ((current - entry) / entry * 100) if entry else 0,
            }
        )

    balance = data.get("balance", INITIAL_BALANCE)
    equity = balance + positions_value
    total_pnl = equity - INITIAL_BALANCE

    return {
        "balance": balance,
        "equity": equity,
        "positions_value": positions_value,
        "unrealized_pnl": unrealized_pnl,
        "total_pnl": total_pnl,
        "total_pnl_pct": (total_pnl / INITIAL_BALANCE) * 100,
        "positions": positions_out,
        "trades": list(reversed(data.get("trades", [])[-20:])),
        "trade_count": data.get("order_counter", 0),
    }


def _load_model_meta(symbol: str, market: str) -> dict:
    key = symbol.replace("/", "_").replace(".", "_")
    path = MODELS_DIR / f"{market}_{key}.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def _build_charts(settings) -> list[dict]:
    charts = []
    for sym in settings.crypto_symbol_list():
        meta = _load_model_meta(sym, "crypto")
        charts.append(
            {
                "symbol": sym,
                "market": "crypto",
                "tv_symbol": to_tradingview_symbol(sym, "crypto"),
                "tv_url": chart_url(sym, "crypto"),
                "model_type": meta.get("model_type", "—"),
                "win_rate": meta.get("win_rate"),
                "optimal_confidence": meta.get("optimal_confidence"),
                "accuracy": meta.get("accuracy"),
            }
        )
    for sym in settings.stock_symbol_list():
        meta = _load_model_meta(sym, "stock")
        charts.append(
            {
                "symbol": sym,
                "market": "stock",
                "tv_symbol": to_tradingview_symbol(sym, "stock"),
                "tv_url": chart_url(sym, "stock"),
                "model_type": meta.get("model_type", "—"),
                "win_rate": meta.get("win_rate"),
                "optimal_confidence": meta.get("optimal_confidence"),
                "accuracy": meta.get("accuracy"),
            }
        )
    return charts


def get_live_data() -> dict:
    live_file = DATA_DIR / "live.json"
    if not live_file.exists():
        return {"last_scan": None, "symbols": {}, "events": []}
    try:
        return json.loads(live_file.read_text())
    except json.JSONDecodeError:
        return {"last_scan": None, "symbols": {}, "events": []}


def get_dashboard_data() -> dict:
    settings = load_settings()
    crypto = _enrich_portfolio("crypto", is_crypto=True)
    stock = _enrich_portfolio("stock", is_crypto=False)

    activity: list[dict] = []
    activity_path = DATA_DIR / "activity.json"
    if activity_path.exists():
        try:
            activity = list(reversed(json.loads(activity_path.read_text())[-20:]))
        except json.JSONDecodeError:
            activity = []

    combined_equity = crypto["equity"] + stock["equity"]
    combined_pnl = combined_equity - (INITIAL_BALANCE * 2)

    return {
        "mode": settings.trading_mode.value,
        "updated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "crypto_symbols": settings.crypto_symbol_list(),
        "stock_symbols": settings.stock_symbol_list(),
        "summary": {
            "combined_equity": combined_equity,
            "combined_pnl": combined_pnl,
            "combined_pnl_pct": (combined_pnl / (INITIAL_BALANCE * 2)) * 100,
            "initial_per_market": INITIAL_BALANCE,
        },
        "crypto": crypto,
        "stock": stock,
        "activity": activity,
        "charts": _build_charts(settings),
        "live": get_live_data(),
        "tradingview": {
            "trades": get_tv_trades()[:10],
            "webhook_path": "/webhook/tradingview",
            "webhook_url": _read_tv_webhook_url(),
            "mode": settings.tv_mode,
        },
    }
