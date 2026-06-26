#!/usr/bin/env python3
"""Train agressieve modellen — HOOG RISICO."""

import subprocess
import sys

print("\n" + "=" * 60)
print("  ⚠️  AGRESSIEVE MODUS — HOOG RISICO")
print("  Meer trades, snellere 5m candles, laag confidence drempel")
print("  GEEN garantie om geld te verdubbelen — kan alles verliezen")
print("=" * 60 + "\n")

args = ["python", "train.py", "--aggressive"] + sys.argv[1:]
if "--all" not in args and "--symbol" not in args:
    args.insert(2, "--all")

sys.exit(subprocess.call(args))
