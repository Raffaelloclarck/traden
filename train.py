#!/usr/bin/env python3
"""Train AI modellen — 12 maanden data, tuning, sentiment, sequence NN."""

import argparse
import logging
import sys

from traden.config import load_settings
from traden.ml.train import train_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Train ML trading modellen (volledig)")
    parser.add_argument("--all", action="store_true", help="Train alle symbolen uit .env")
    parser.add_argument("--symbol", help="Bijv. BTC/USDT of AAPL")
    parser.add_argument("--market", choices=["crypto", "stock"], default="crypto")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--months", type=int, default=12, help="Maanden historische data")
    parser.add_argument("--no-tune", action="store_true", help="Sla hyperparameter tuning over")
    parser.add_argument("--no-cache", action="store_true", help="Forceer verse data download")
    parser.add_argument("--no-sequence", action="store_true", help="Alleen Gradient Boosting")
    parser.add_argument("--no-precision", action="store_true", help="Sla precision mode over")
    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="Agressieve modus: 5m, snelle trades, hoger risico (GEEN 2x garantie)",
    )
    args = parser.parse_args()
    precision_mode = not args.no_precision and not args.aggressive

    settings = load_settings()
    jobs: list[tuple[str, str]] = []

    if args.all:
        jobs.extend((s, "crypto") for s in settings.crypto_symbol_list())
        jobs.extend((s, "stock") for s in settings.stock_symbol_list())
    elif args.symbol:
        jobs.append((args.symbol, args.market))
    else:
        parser.error("Gebruik --all of --symbol BTC/USDT")

    print("\n=== AI TRAINING (volledig) ===")
    print(f"  Data:        {args.months} maanden")
    print(f"  Tuning:      {'ja' if not args.no_tune else 'nee'}")
    print(f"  Sentiment:   ja (Fear&Greed / VIX)")
    print(f"  Sequence NN: {'ja' if not args.no_sequence else 'nee'}")
    print(f"  Modus:        {'AGGRESSIVE ⚠️' if args.aggressive else 'precision'}")
    if args.aggressive:
        print("  Timeframe:    5m · snelle trades · laag confidence drempel")
    print()

    results = []
    for symbol, market in jobs:
        logger.info("Training %s (%s)...", symbol, market)
        try:
            result = train_model(
                symbol=symbol,
                market=market,
                timeframe="5m" if args.aggressive else args.timeframe,
                months=args.months,
                tune=not args.no_tune,
                use_sequence=not args.no_sequence,
                use_cache=not args.no_cache,
                precision_mode=precision_mode,
                aggressive_mode=args.aggressive,
            )
            results.append(result)
            print(f"\n{'='*55}")
            print(f"  {symbol} ({market}) — {result.model_type}")
            print(f"{'='*55}")
            print(f"  Candles:        {result.candles:,}")
            print(f"  Train/Test:     {result.train_samples} / {result.test_samples}")
            print(f"  Accuracy:       {result.accuracy:.1%}")
            print(f"  Precision:      {result.precision:.1%}")
            print(f"  Win rate:       {result.win_rate:.1%} ({result.precision_trades} trades @ {result.optimal_confidence:.0%} conf)")
            print(f"  Backtest:       {result.backtest_return_pct:+.2f}%")
            print(f"  Model:          {result.model_path}")
            print(f"\n{result.report}")
        except Exception as exc:
            logger.error("Training mislukt voor %s: %s", symbol, exc)

    if results:
        avg_acc = sum(r.accuracy for r in results) / len(results)
        avg_bt = sum(r.backtest_return_pct for r in results) / len(results)
        print(f"\n{'='*55}")
        print(f"  GEMIDDELD: accuracy {avg_acc:.1%} | backtest {avg_bt:+.2f}%")
        print(f"{'='*55}")

    print("\nStart bot: python main.py --strategy ml --loop --interval 30\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
