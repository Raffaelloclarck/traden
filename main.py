#!/usr/bin/env python3
"""Start de trading engine — één scan of doorlopend."""

import argparse
import logging
import sys
import time

from traden.config import TradingMode, load_settings
from traden.demo import run_demo_trades
from traden.engine import TradingEngine
from traden.models import AssetClass
from traden.strategies.ml_strategy import MLStrategy
from traden.strategies.momentum import MomentumStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def confirm_live() -> bool:
    print("\n⚠️  LIVE MODE — echte orders worden geplaatst!")
    print("Typ 'JA LIVE' om door te gaan: ", end="", flush=True)
    answer = input().strip()
    return answer == "JA LIVE"


def main() -> int:
    parser = argparse.ArgumentParser(description="Traden — multi-asset bot")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Blijf scannen (interval in seconden via --interval)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Seconden tussen scans (default: 300 = 5 min)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Forceer live mode (override .env)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Plaats direct demo paper trades (zichtbaar op dashboard)",
    )
    parser.add_argument(
        "--strategy",
        choices=["momentum", "ml", "aggressive"],
        default="momentum",
        help="Trading strategie",
    )
    args = parser.parse_args()

    settings = load_settings()
    if args.live:
        settings.trading_mode = TradingMode.LIVE

    if settings.is_live and not confirm_live():
        logger.error("Live trading geannuleerd.")
        return 1

    engine = TradingEngine(settings)
    if args.strategy in ("ml", "aggressive"):
        kwargs = {"timeframe": "5m"} if args.strategy == "aggressive" else {}
        strategies = {
            AssetClass.CRYPTO: MLStrategy(AssetClass.CRYPTO, **kwargs),
            AssetClass.STOCK: MLStrategy(AssetClass.STOCK, **kwargs),
        }
        if args.strategy == "aggressive":
            logger.warning(
                "AGGRESSIVE MODE — hoog risico, geen verdubbel-garantie, paper aanbevolen"
            )
    else:
        strategies = {
            AssetClass.CRYPTO: MomentumStrategy(AssetClass.CRYPTO),
            AssetClass.STOCK: MomentumStrategy(AssetClass.STOCK, timeframe="15m"),
        }

    engine.setup(strategies)

    if args.demo:
        run_demo_trades()

    if args.loop:
        logger.info("Loop mode: scan elke %d seconden — stopt alleen met stop-bot.sh", args.interval)
        while True:
            try:
                engine.run_once()
            except KeyboardInterrupt:
                logger.info("Gestopt door gebruiker (Ctrl+C).")
                break
            except Exception as exc:
                logger.exception("Scan fout — bot blijft draaien: %s", exc)
            time.sleep(args.interval)
    else:
        engine.run_once()

    return 0


if __name__ == "__main__":
    sys.exit(main())
