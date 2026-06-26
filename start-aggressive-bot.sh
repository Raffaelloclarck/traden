#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
echo ""
echo "  ⚠️  AGRESSIEVE BOT — paper mode, hoog risico"
echo ""
python main.py --strategy aggressive --loop --interval 15
