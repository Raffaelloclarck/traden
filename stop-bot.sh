#!/bin/bash
# ENIGE manier om de bot te stoppen
cd "$(dirname "$0")"
touch data/STOP
echo "Stop signaal verstuurd..."

pkill -f "supervisor.py" 2>/dev/null
pkill -f "main.py --strategy ml" 2>/dev/null
pkill -f "main.py --loop" 2>/dev/null
pkill -f "dashboard.py" 2>/dev/null
pkill -f "ngrok http" 2>/dev/null

sleep 2
echo ""
echo "  Bot gestopt."
echo "  Opnieuw starten: ./start-forever.sh"
echo ""
