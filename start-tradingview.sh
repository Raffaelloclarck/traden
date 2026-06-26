#!/bin/bash
# TradingView setup — dashboard + webhook + ngrok + supervisor
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
mkdir -p logs data

# Stop oude processen
./stop-bot.sh 2>/dev/null || true
rm -f data/STOP
sleep 2

# TradingView modus: trades komen van JOUW TV alerts (webhook)
if grep -q "^TV_MODE=" .env 2>/dev/null; then
  sed -i '' 's/^TV_MODE=.*/TV_MODE=true/' .env
else
  echo "TV_MODE=true" >> .env
fi

SECRET=$(grep "^TV_WEBHOOK_SECRET=" .env 2>/dev/null | cut -d= -f2)
SECRET=${SECRET:-traden-live-secret}

# ngrok installeren indien nodig
if ! command -v ngrok &>/dev/null; then
  echo "ngrok installeren..."
  brew install ngrok/ngrok/ngrok 2>/dev/null || brew install ngrok 2>/dev/null || true
fi

# Supervisor op achtergrond (dashboard + webhook, geen ML-bot in TV mode)
nohup python supervisor.py >> logs/supervisor.log 2>&1 &
echo $! > data/supervisor.pid
sleep 5

# ngrok voor publieke URL (TradingView vereist dit)
NGROK_URL=""
if command -v ngrok &>/dev/null; then
  pkill -f "ngrok http" 2>/dev/null || true
  sleep 1
  nohup ngrok http 8080 --log=stdout >> logs/ngrok.log 2>&1 &
  echo $! > data/ngrok.pid
  sleep 4
  NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    for t in d.get('tunnels', []):
        if t.get('proto') == 'https':
            print(t['public_url']); break
except: pass
" 2>/dev/null || true)
fi

WEBHOOK_PATH="/webhook/tradingview?secret=$SECRET"
LOCAL_URL="http://127.0.0.1:8080$WEBHOOK_PATH"
PUBLIC_URL="${NGROK_URL}${WEBHOOK_PATH}"

echo "$PUBLIC_URL" > data/tv_webhook_url.txt
echo "$LOCAL_URL" > data/tv_webhook_url_local.txt

echo ""
echo "  ══════════════════════════════════════════════════════"
echo "  TRADINGVIEW GEKOPPELD — gebruik JOUW TradingView account"
echo "  ══════════════════════════════════════════════════════"
echo ""
echo "  Jij logt in op tradingview.com (jouw account)."
echo "  De bot heeft je wachtwoord NIET nodig."
echo "  Alerts van jouw chart → webhook → bot voert uit."
echo ""
echo "  Dashboard:     http://127.0.0.1:8080"
echo ""
if [ -n "$NGROK_URL" ]; then
  echo "  WEBHOOK URL (plak in TradingView Alert):"
  echo "  $PUBLIC_URL"
else
  echo "  ngrok niet actief — run handmatig: ngrok http 8080"
  echo "  Lokale URL (werkt NIET in TradingView):"
  echo "  $LOCAL_URL"
fi
echo ""
echo "  ── STAP 2: Pine Script ──"
echo "  Open: scripts/tradingview_alert.pine"
echo "  TradingView → Pine Editor → plakken → Add to chart"
echo "  Chart: BINANCE:ETHUSDT of NASDAQ:AAPL"
echo ""
echo "  ── STAP 3: Alert ──"
echo "  TradingView → Alarmklok → Create Alert"
echo "  Condition: Traden Bot Bridge → Any alert() function call"
echo "  Webhook URL: (zie hierboven)"
echo "  Frequency: Once per bar"
echo ""
echo "  Stoppen: ./stop-bot.sh"
echo "  ══════════════════════════════════════════════════════"
echo ""
