"""TradingView webhook → order uitvoering."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from traden.activity import log_scan
from traden.config import load_settings
from traden.engine import create_brokers
from traden.models import AssetClass, Order, Side
from traden.risk import RiskManager

logger = logging.getLogger(__name__)
TV_LOG = Path("data/tradingview_trades.json")


def _normalize_symbol(raw: str) -> tuple[str, str]:
    """ETHUSDT → (ETH/USDT, crypto), AAPL → (AAPL, stock)."""
    s = raw.upper().strip().replace(" ", "")
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}/USDT", "crypto"
    if s.endswith("USD") and len(s) > 3:
        base = s[:-3]
        return f"{base}/USDT", "crypto"
    if "/" in s:
        return s, "crypto"
    return s, "stock"


def parse_tradingview_payload(payload: str | dict) -> dict | None:
    """Parse TradingView alert body (JSON of plain text)."""
    if isinstance(payload, dict):
        data = payload
    else:
        text = payload.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # "BUY ETHUSDT" of "buy ethusdt"
            m = re.match(r"(buy|sell|close)\s+(\w+)", text, re.I)
            if not m:
                return None
            action, sym = m.group(1).lower(), m.group(2)
            symbol, market = _normalize_symbol(sym)
            return {"action": action, "symbol": symbol, "market": market}

    action = str(data.get("action", data.get("side", ""))).lower()
    if action in ("long", "enter_long"):
        action = "buy"
    if action in ("short", "enter_short", "exit"):
        action = "sell"

    raw_sym = data.get("symbol", data.get("ticker", ""))
    if not raw_sym or not action:
        return None

    symbol, market = _normalize_symbol(str(raw_sym).split(":")[-1])
    if data.get("market"):
        market = data["market"]

    return {
        "action": action,
        "symbol": symbol,
        "market": market,
        "price": data.get("price"),
        "source": "tradingview",
    }


def _log_tv_trade(entry: dict) -> None:
    TV_LOG.parent.mkdir(parents=True, exist_ok=True)
    history: list = []
    if TV_LOG.exists():
        try:
            history = json.loads(TV_LOG.read_text())
        except json.JSONDecodeError:
            history = []
    history.append(entry)
    TV_LOG.write_text(json.dumps(history[-50:], indent=2))


def execute_tradingview_alert(
    payload: str | dict,
    settings: Settings | None = None,
) -> dict:
    """Voer TradingView alert uit als paper/live order."""
    settings = settings or load_settings()
    parsed = parse_tradingview_payload(payload)
    if not parsed:
        return {"success": False, "message": "Kon alert niet parsen"}

    action = parsed["action"]
    symbol = parsed["symbol"]
    market = parsed["market"]
    asset = AssetClass.CRYPTO if market == "crypto" else AssetClass.STOCK

    brokers = create_brokers(settings)
    broker = brokers.get(asset)
    if not broker:
        return {"success": False, "message": f"Geen broker voor {market}"}

    risk = RiskManager(settings)

    if action == "close" or action == "sell":
        result = broker.close_position(symbol)
        side = Side.SELL
    elif action == "buy":
        quote = broker.get_quote(symbol)
        price = float(parsed.get("price") or quote.ask)
        stop = price * 0.98
        qty = risk.position_size(broker, price, stop)
        if market == "stock":
            qty = max(1, int(qty))
        if qty <= 0:
            return {"success": False, "message": "Positiegrootte te klein"}
        order = Order(symbol=symbol, asset_class=asset, side=Side.BUY, quantity=qty)
        result = broker.place_order(order)
        side = Side.BUY
    else:
        return {"success": False, "message": f"Onbekende actie: {action}"}

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "tradingview",
        "symbol": symbol,
        "market": market,
        "action": action,
        "success": result.success,
        "order_id": result.order_id,
        "price": result.fill_price,
        "quantity": result.quantity,
        "message": result.message,
    }
    _log_tv_trade(entry)

    log_scan(
        market=market,
        balance=broker.get_balance(),
        positions=len(broker.get_positions()),
        signals=[{"side": action, "symbol": symbol, "reason": "TradingView alert"}],
        trades=[
            {
                "id": result.order_id,
                "symbol": symbol,
                "side": side.value,
                "quantity": result.quantity,
                "price": result.fill_price,
            }
        ]
        if result.success
        else [],
        scores=[{"symbol": symbol, "score": 1.0, "action": action, "source": "tradingview"}],
    )

    return entry


def get_tv_trades() -> list[dict]:
    if not TV_LOG.exists():
        return []
    try:
        return list(reversed(json.loads(TV_LOG.read_text())))
    except json.JSONDecodeError:
        return []
