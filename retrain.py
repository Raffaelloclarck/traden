#!/usr/bin/env python3
"""Wekelijkse hertraining van alle AI modellen."""

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from traden.config import load_settings
from traden.ml.train import train_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)
LOG_FILE = Path("logs/retrain.log")


def retrain_all(months: int = 12, no_cache: bool = True) -> int:
    settings = load_settings()
    jobs = [(s, "crypto") for s in settings.crypto_symbol_list()]
    jobs += [(s, "stock") for s in settings.stock_symbol_list()]

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logger.info("=== Wekelijkse hertraining gestart ===")

    ok, fail = 0, 0
    for symbol, market in jobs:
        try:
            result = train_model(
                symbol=symbol,
                market=market,
                months=months,
                tune=True,
                use_sequence=True,
                use_cache=not no_cache,
            )
            logger.info(
                "%s OK — %s acc=%.1f%% backtest=%+.2f%%",
                symbol,
                result.model_type,
                result.accuracy * 100,
                result.backtest_return_pct,
            )
            ok += 1
        except Exception as exc:
            logger.error("%s MISLUKT: %s", symbol, exc)
            fail += 1

    summary = f"{datetime.now(timezone.utc).isoformat()} — {ok} OK, {fail} mislukt\n"
    with LOG_FILE.open("a") as f:
        f.write(summary)

    logger.info("Hertraining klaar: %d OK, %d mislukt", ok, fail)
    return 0 if fail == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Wekelijkse AI hertraining")
    parser.add_argument("--months", type=int, default=12)
    parser.add_argument("--use-cache", action="store_true")
    args = parser.parse_args()
    return retrain_all(months=args.months, no_cache=not args.use_cache)


if __name__ == "__main__":
    sys.exit(main())
