#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate

echo ""
echo "  Bot starten (paper, elke 30 sec scan)..."
echo "  Dashboard: http://127.0.0.1:8080"
echo ""

python main.py --loop --interval 30 --demo
