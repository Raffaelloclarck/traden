#!/bin/bash
# Start bot + dashboard — blijft ALTIJD draaien tot je stop-bot.sh runt
cd "$(dirname "$0")"
source .venv/bin/activate
rm -f data/STOP
mkdir -p logs data
echo "Start supervisor — stop met: ./stop-bot.sh"
python supervisor.py
