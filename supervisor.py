#!/usr/bin/env python3
"""
Supervisor — bot + dashboard blijven ALTIJD draaien tot je stop-bot.sh runt.
Herstart automatisch bij crash.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SUPERVISOR] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
STOP_FILE = ROOT / "data" / "STOP"
STATUS_FILE = ROOT / "data" / "supervisor.json"
LOG_DIR = ROOT / "logs"
BOT_LOG = LOG_DIR / "bot.log"
DASH_LOG = LOG_DIR / "dashboard.log"

BOT_CMD = [
    sys.executable,
    "main.py",
    "--strategy",
    "ml",
    "--loop",
    "--interval",
    "30",
]
DASH_CMD = [sys.executable, "dashboard.py"]

bot_proc: subprocess.Popen | None = None
dash_proc: subprocess.Popen | None = None


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def _write_status(running: bool, bot_pid: int | None, dash_pid: int | None) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(
        json.dumps(
            {
                "running": running,
                "bot_pid": bot_pid,
                "dashboard_pid": dash_pid,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "stop_file": str(STOP_FILE),
            },
            indent=2,
        )
    )


def _start_process(cmd: list[str], log_path: Path) -> subprocess.Popen:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("a")
    return subprocess.Popen(
        cmd,
        cwd=ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def _ensure_dashboard() -> subprocess.Popen | None:
    global dash_proc
    if _port_open(8080):
        return dash_proc
    if dash_proc and dash_proc.poll() is None:
        # Proces hangt zonder poort — kill en herstart
        logger.warning("Dashboard reageert niet op :8080 — herstart")
        dash_proc.terminate()
        dash_proc = None
        time.sleep(1)
    logger.info("Dashboard starten...")
    dash_proc = _start_process(DASH_CMD, DASH_LOG)
    for _ in range(15):
        if _port_open(8080):
            break
        time.sleep(1)
    return dash_proc


def _tv_mode_enabled() -> bool:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return False
    for line in env_path.read_text().splitlines():
        if line.strip().startswith("TV_MODE=true"):
            return True
    return False


def _ensure_bot() -> subprocess.Popen | None:
    global bot_proc
    if _tv_mode_enabled():
        return bot_proc  # TradingView modus: alleen webhook, geen ML-loop
    if bot_proc and bot_proc.poll() is None:
        return bot_proc
    logger.info("Bot starten (ML, elke 30s)...")
    bot_proc = _start_process(BOT_CMD, BOT_LOG)
    return bot_proc


def _shutdown(signum=None, frame=None) -> None:
    global bot_proc, dash_proc
    logger.info("Afsluiten...")
    for proc in (bot_proc, dash_proc):
        if proc and proc.poll() is None:
            proc.terminate()
    _write_status(False, None, None)
    sys.exit(0)


def main() -> int:
    os.chdir(ROOT)
    STOP_FILE.unlink(missing_ok=True)
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    print("\n  ══════════════════════════════════════════")
    print("  BOT DRAAIT VOOR ALTIJD")
    print("  Stoppen: ./stop-bot.sh")
    print("  Dashboard: http://127.0.0.1:8080")
    print("  Logs: logs/bot.log · logs/dashboard.log")
    print("  ══════════════════════════════════════════\n")

    bot_restarts = 0
    dash_restarts = 0

    while not STOP_FILE.exists():
        try:
            dash = _ensure_dashboard()
            if dash and dash.poll() is not None:
                dash_restarts += 1
                logger.warning("Dashboard gecrasht — herstart (#%d)", dash_restarts)
                dash_proc = None
                time.sleep(3)
                continue

            bot = _ensure_bot()
            if bot and bot.poll() is not None:
                bot_restarts += 1
                logger.warning("Bot gecrasht — herstart (#%d)", bot_restarts)
                bot_proc = None
                time.sleep(5)
                continue

            _write_status(
                True,
                bot.pid if bot else None,
                dash.pid if dash else None,
            )
            time.sleep(10)

        except Exception as exc:
            logger.exception("Supervisor fout — blijft proberen: %s", exc)
            time.sleep(10)

    logger.info("STOP bestand gevonden — supervisor gestopt.")
    _shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
