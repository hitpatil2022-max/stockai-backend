"""
India Stock AI Intelligence Engine
Runs every 30 minutes, analyses news + stocks, sends Telegram alerts
"""

import schedule
import time
import json
import os
import threading
import pytz
from datetime import datetime
from flask import Flask, send_file, jsonify
from flask_cors import CORS

# ── Market Hours Check ──────────────────────────────────
def is_market_open():
    """Returns True only during NSE/BSE trading hours (Mon–Fri, 9:15–15:30 IST)"""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    if now.weekday() >= 5:              # Saturday=5, Sunday=6
        return False
    t = now.hour * 60 + now.minute
    return 9*60+15 <= t <= 15*60+30    # 9:15 AM to 3:30 PM

def is_pre_market():
    """Returns True during pre-market window (Mon–Fri, 9:00–9:15 IST)"""
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    return 9*60 <= t < 9*60+15

from news_scraper import fetch_all_news
from stock_analyzer import get_stock_data, calculate_technical_signals
from ai_analyzer import analyze_with_ai
from telegram_notifier import send_alert, send_daily_summary
from signal_engine import generate_signals
from config import WATCHLIST, LOG_FILE

# ── Flask web server (serves data.json to dashboard) ──
app = Flask(__name__)
CORS(app)

@app.route('/data.json')
def serve_data():
    try:
        return send_file('../dashboard/data.json', mimetype='application/json')
    except Exception:
        return jsonify({
            "signals": [],
            "top_news": [],
            "last_updated": "No data yet",
            "news_count": 0,
            "stocks_analyzed": 0
        })

@app.route('/')
def home():
    return "India Stock AI is running!", 200

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ── Logging ──
IST = pytz.timezone('Asia/Kolkata')

def log(msg):
    timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    line = f"[{timestamp}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ── Main analysis cycle ──
def run_analysis():
    log("Starting analysis cycle...")

    try:
        # Step 1: Fetch latest Indian market news
        log("Fetching news from Economic Times, Moneycontrol, BSE...")
        news_items = fetch_all_news()
        log(f"   Found {len(news_items)} news items")

        # Step 2: Get live stock data for watchlist
        log("Fetching NSE/BSE stock data...")
        stock_data = get_stock_data(WATCHLIST)

        # Step 3: Calculate technical signals (RSI, MACD, Volume)
        log("Calculating technical indicators...")
        tech_signals = calculate_technical_signals(stock_data)

        # Step 4: AI analysis of news + technicals combined
        log("Running AI analysis (Gemini)...")
        ai_insights = analyze_with_ai(news_items, stock_data, tech_signals)

        # Step 5: Generate final buy/sell/hold signals
        log("Generating trading signals...")
        signals = generate_signals(ai_insights, tech_signals, stock_data)

        # Step 6: Save to JSON for dashboard
        mkt_sig    = next((s for s in signals if s.get("is_market_summary")), {})
        mkt_tone   = (mkt_sig.get("action") or "neutral").lower()
        is_bullish = mkt_tone == "bullish"

        output = {
            "last_updated":    datetime.now(IST).isoformat(),
            "signals":         signals,
            "news_count":      len(news_items),
            "stocks_analyzed": len(stock_data),
            "ai_powered":      any(s.get("ai_powered") for s in signals),
            "top_news":        news_items[:10],
            "tech_signals":    tech_signals,
            "market_intel": {
                "fii_dii": {
                    "fii": {"action": "BUYING" if is_bullish else "SELLING", "net_cr": 0},
                    "dii": {"action": "BUYING" if is_bullish else "SELLING", "net_cr": 0},
                    "sentiment": mkt_tone,
                },
                "bulk_deals": [],
            }
        }

        os.makedirs('../dashboard', exist_ok=True)
        with open("../dashboard/data.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, default=str)

        # Step 7: Send Telegram alerts — market hours only, real signals only
        # Filter: confidence >= 75 AND not market summary AND not HOLD (noisy)
        strong_signals = [
            s for s in signals
            if s.get("confidence", 0) >= 75
            and not s.get("is_market_summary", False)   # exclude NEUTRAL MARKET meta-signal
            and s.get("symbol", "MARKET") != "MARKET"   # double guard
            and s.get("action") in ("BUY", "SELL", "WATCH")  # skip HOLD alerts
            and s.get("current_price", 0) > 0           # skip signals with no price data
        ]
        if is_market_open():
            for signal in strong_signals:
                send_alert(signal)
                log(f"   Alert sent: {signal['symbol']} - {signal['action']} ({signal['confidence']}%)")
            log(f"   {len(strong_signals)} alerts sent this cycle")
        else:
            log(f"   Market closed — {len(strong_signals)} alerts suppressed (resumes 9:15 AM IST)")

        log(f"Cycle complete. {len(strong_signals)} strong signals found.\n")

    except Exception as e:
        log(f"Error in analysis cycle: {e}")

def morning_briefing():
    if not is_pre_market() and not is_market_open():
        log("Skipping morning briefing — today is a weekend or holiday")
        return
    log("Sending morning briefing...")
    run_analysis()
    send_daily_summary()

# ── Entry point ──
def main():
    # Start Flask web server in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    log("Web server started on port " + str(os.environ.get('PORT', 5000)))

    log("=" * 60)
    log("  INDIA STOCK AI - INTELLIGENCE ENGINE STARTED")
    log("=" * 60)

    # Run immediately on start
    run_analysis()

    # ── Schedule — all times in UTC (Railway server is UTC) ──────────────
    # IST = UTC + 5:30
    # 9:00 AM IST  = 03:30 UTC
    # 9:15 AM IST  = 03:45 UTC
    # 3:30 PM IST  = 10:00 UTC
    schedule.every(30).minutes.do(run_analysis)
    schedule.every().day.at("03:30").do(morning_briefing)   # 9:00 AM IST
    schedule.every().day.at("10:00").do(send_daily_summary) # 3:30 PM IST

    log("Scheduler running. Analysis every 30 minutes.")
    log("Market hours: 9:15 AM - 3:30 PM IST")

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
