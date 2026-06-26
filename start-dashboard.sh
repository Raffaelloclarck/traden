#!/bin/bash
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Virtual env aanmaken..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -q -r requirements.txt
else
  source .venv/bin/activate
fi

echo ""
echo "  Dashboard starten..."
echo "  Open in browser: http://127.0.0.1:8080"
echo ""
echo "  Laat dit venster OPEN staan!"
echo "  Stoppen met Ctrl+C"
echo ""

python dashboard.py
