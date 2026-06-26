#!/bin/bash
# Wekelijkse hertraining — installeer via: ./install-weekly-retrain.sh
cd "$(dirname "$0")"
source .venv/bin/activate
python retrain.py >> logs/retrain.log 2>&1
