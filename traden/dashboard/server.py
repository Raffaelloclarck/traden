from flask import Flask, jsonify, render_template, request

from traden.config import load_settings
from traden.dashboard.data import get_dashboard_data
from traden.webhook.tradingview import execute_tradingview_alert, get_tv_trades

app = Flask(__name__, template_folder="templates")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/live")
def api_live():
    from traden.dashboard.data import get_live_data
    return jsonify(get_live_data())


@app.route("/api/tradingview/trades")
def api_tv_trades():
    return jsonify(get_tv_trades())


@app.route("/webhook/tradingview", methods=["POST"])
def webhook_tradingview():
    """TradingView alert webhook — zie scripts/tradingview_alert.pine"""
    settings = load_settings()
    secret = request.args.get("secret") or request.headers.get("X-Webhook-Secret", "")
    if settings.tv_webhook_secret and secret != settings.tv_webhook_secret:
        return jsonify({"success": False, "message": "Ongeldig secret"}), 403

    payload = request.get_json(silent=True) or request.get_data(as_text=True)
    result = execute_tradingview_alert(payload, settings)
    status = 200 if result.get("success") else 400
    return jsonify(result), status


@app.route("/api/status")
def api_status():
    return jsonify(get_dashboard_data())


def run(host: str = "127.0.0.1", port: int = 8080) -> None:
    app.run(host=host, port=port, debug=False)
