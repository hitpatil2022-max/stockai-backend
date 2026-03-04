"""
India Stock AI Intelligence Engine
Full version: News + Technicals + FII/DII + Bulk Deals + Insider Trades + Political Intel
"""

import sys
import schedule
import time
import json
import os
import threading
from datetime import datetime
from flask import Flask, send_file, jsonify
from flask_cors import CORS

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from news_scraper import fetch_all_news
from stock_analyzer import get_stock_data, calculate_technical_signals
from ai_analyzer import analyze_with_ai
from telegram_notifier import send_alert, send_daily_summary, send_morning_briefing, send_startup_message
from signal_engine import generate_signals
from political_analyzer import scan_for_figures
from market_intelligence import fetch_all_market_intelligence
from config import WATCHLIST, LOG_FILE

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data.json")
LOG_PATH  = os.path.join(BASE_DIR, "logs", "system.log")

app = Flask(__name__)
CORS(app)

@app.route('/data.json')
def serve_data():
    try:
        if os.path.exists(DATA_PATH):
            return send_file(DATA_PATH, mimetype='application/json')
        else:
            return jsonify({
                "signals": [], "top_news": [],
                "last_updated": "First analysis still running...",
                "news_count": 0, "stocks_analyzed": 0
            })
    except Exception as e:
        return jsonify({"signals": [], "top_news": [], "last_updated": f"Error: {str(e)}", "news_count": 0, "stocks_analyzed": 0})

@app.route('/health')
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()}), 200

@app.route('/')
def home():
    return "India Stock AI is running! Visit /data.json for signals.", 200

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False, debug=False)

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def run_analysis():
    log("Starting analysis cycle...")
    try:
        # Step 1: News
        log("Fetching news...")
        news_items = fetch_all_news()
        log(f"   Found {len(news_items)} news items")

        # Step 2: Stock data
        log("Fetching NSE/BSE stock data...")
        stock_data = get_stock_data(WATCHLIST)

        # Step 3: Technical indicators
        log("Calculating technical indicators...")
        tech_signals = calculate_technical_signals(stock_data)

        # Step 4: Political & business intelligence
        log("Scanning for political/business intelligence...")
        political_findings = scan_for_figures(news_items)
        log(f"   Found {len(political_findings)} political/business connections")

        # Step 5: FII/DII + Bulk deals + Insider trades
        log("Fetching market intelligence (FII/DII, bulk deals, insider trades)...")
        market_intel = fetch_all_market_intelligence()

        # Step 6: AI analysis with all data sources
        log("Running AI analysis (Gemini) with full intelligence...")
        ai_insights = analyze_with_ai(
            news_items, stock_data, tech_signals,
            political_findings, market_intel
        )

        # Step 7: Generate signals
        log("Generating trading signals...")
        signals = generate_signals(ai_insights, tech_signals, stock_data)

        # Step 8: Save output
        output = {
            "last_updated":         datetime.now().isoformat(),
            "signals":              signals,
            "news_count":           len(news_items),
            "stocks_analyzed":      len(stock_data),
            "top_news":             news_items[:10],
            "tech_signals":         tech_signals,
            "political_intel":      political_findings,
            "fii_dii":              market_intel.get("fii_dii", {}),
            "bulk_deals":           market_intel.get("bulk_deals", [])[:10],
            "insider_trades":       market_intel.get("insider_trades", [])[:10],
            "hidden_connections":   ai_insights.get("hidden_connections", []),
            "fii_dii_impact":       ai_insights.get("fii_dii_impact", ""),
        }

        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, default=str)

        log("   data.json saved successfully")

        # Step 9: Send alerts
        strong_signals = [s for s in signals if s.get("confidence", 0) >= 75 and not s.get("is_market_summary")]
        for signal in strong_signals:
            send_alert(signal)
            log(f"   Alert sent: {signal['symbol']} - {signal['action']}")

        hidden = ai_insights.get("hidden_connections", [])
        if hidden:
            log(f"   Hidden connections found: {len(hidden)}")
            for h in hidden[:3]:
                log(f"     -> {h.get('connection', '')} | Stocks: {h.get('affected_stocks', [])}")

        log(f"Cycle complete. {len(strong_signals)} strong signals found.\n")
        return ai_insights

    except Exception as e:
        log(f"ERROR in analysis cycle: {e}")
        import traceback
        log(traceback.format_exc())
        return {}

def morning_briefing():
    log("Sending morning briefing...")
    ai_insights = run_analysis()
    send_morning_briefing(
        market_sentiment = ai_insights.get("market_sentiment", "neutral"),
        top_opportunity  = ai_insights.get("top_opportunity", ""),
        risks            = ai_insights.get("risks_to_watch", [])
    )

def main():
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    log("Web server started on port " + str(os.environ.get('PORT', 5000)))

    log("=" * 60)
    log("  INDIA STOCK AI - INTELLIGENCE ENGINE STARTED")
    log("  Full Intel: News + Tech + FII/DII + Bulk + Insider + Political")
    log("  Python 3.14 compatible · Railway ready")
    log("=" * 60)

    send_startup_message()
    run_analysis()

    schedule.every(30).minutes.do(run_analysis)
    schedule.every().day.at("09:00").do(morning_briefing)
    schedule.every().day.at("15:30").do(send_daily_summary)

    log("Scheduler running. Analysis every 30 minutes.")

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
