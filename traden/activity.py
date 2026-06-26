import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
ACTIVITY_FILE = DATA_DIR / "activity.json"


def log_scan(
    market: str,
    balance: float,
    positions: int,
    signals: list[dict],
    trades: list[dict],
    scores: list[dict] | None = None,
) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    if ACTIVITY_FILE.exists():
        try:
            entries = json.loads(ACTIVITY_FILE.read_text())
        except json.JSONDecodeError:
            entries = []

    entries.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "market": market,
            "balance": balance,
            "positions": positions,
            "signals": signals,
            "trades": trades,
            "scores": scores or [],
        }
    )
    ACTIVITY_FILE.write_text(json.dumps(entries[-50:], indent=2))

    _write_live_state(market, balance, positions, signals, trades, scores)


def _write_live_state(
    market: str,
    balance: float,
    positions: int,
    signals: list[dict],
    trades: list[dict],
    scores: list[dict] | None,
) -> None:
    live_file = DATA_DIR / "live.json"
    existing: dict = {}
    if live_file.exists():
        try:
            existing = json.loads(live_file.read_text())
        except json.JSONDecodeError:
            existing = {}

    symbols = existing.get("symbols", {})
    for s in scores or []:
        symbols[s["symbol"]] = {
            **s,
            "market": market,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    events = existing.get("events", [])
    for t in trades:
        events.append(
            {
                "type": "trade",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "market": market,
                **t,
            }
        )
    for sig in signals:
        if not any(
            e.get("type") == "signal"
            and e.get("symbol") == sig.get("symbol")
            and e.get("side") == sig.get("side")
            for e in events[-5:]
        ):
            events.append(
                {
                    "type": "signal",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "market": market,
                    **sig,
                }
            )

    live_file.write_text(
        json.dumps(
            {
                "last_scan": datetime.now(timezone.utc).isoformat(),
                "balance": {**existing.get("balance", {}), market: balance},
                "positions_count": positions,
                "symbols": symbols,
                "events": events[-30:],
            },
            indent=2,
        )
    )
