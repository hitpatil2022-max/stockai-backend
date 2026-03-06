"""
India Stock AI Intelligence Engine
Runs every 90 minutes to stay within Gemini free tier (20 RPD)

Quota budget:
  16 cycles × 1 call = 16 AI calls/day
  + 1 morning briefing call = 17 total → safely under 20 RPD ✅

IMPORTANT: Railway runs in UTC. All schedule times below are UTC.
  UTC+5:30 = IST, so subtract 5:30 from IST time to get UTC time.
  9:00 AM IST = 03:30 UTC
  3:30 PM IST = 10:00 UTC
  8:30 AM IST = 03:00 UTC  (pre-market briefing)
"""

import schedule
import time
import json
import os
import threading
from datetime import datetime, timezone, timedelta
from flask import Flask, send_file, jsonify
from flask_cors import CORS

from news_scraper           import fetch_all_news
from stock_analyzer         import get_stock_data, calculate_technical_signals
from ai_analyzer            import analyze_with_full_intelligence
from political_analyzer     import scan_for_figures
from market_intelligence    import fetch_all_market_intelligence
from telegram_notifier      import send_alert, send_daily_summary, send_morning_briefing, send_startup_message
from signal_engine          import generate_signals
from config                 import WATCHLIST, LOG_FILE

# ── Flask web server ───────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)

@app.route('/data.json')
def serve_data():
    try:
        return send_file('../dashboard/data.json', mimetype='application/json')
    except Exception:
        return jsonify({
            "signals":         [],
            "top_news":        [],
            "last_updated":    "No data yet",
            "news_count":      0,
            "stocks_analyzed": 0,
        })

@app.route('/')
def home():
    return "India Stock AI is running!", 200

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

# ── Logging ────────────────────────────────────────────────────────────────────
def log(msg):
    # Show both UTC and IST in logs for clarity
    utc_now = datetime.now(timezone.utc)
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    line    = f"[{ist_now.strftime('%Y-%m-%d %H:%M:%S')} IST] {msg}"
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ── Main analysis cycle ────────────────────────────────────────────────────────
def run_analysis(use_ai=True):
    log("Starting analysis cycle...")

    try:
        # Step 1: News
        log("Fetching news...")
        news_items = fetch_all_news()
        log(f"   Found {len(news_items)} news items")

        # Step 2: Stock data
        log("Fetching NSE/BSE stock data...")
        stock_data = get_stock_data(WATCHLIST)
        log(f"   Successfully loaded {len(stock_data)} stocks")

        # Step 3: Technical indicators
        log("Calculating technical indicators...")
        tech_signals = calculate_technical_signals(stock_data)

        # Step 4: Political/business intelligence (no AI needed)
        log("Scanning for political/business intelligence...")
        political_findings = scan_for_figures(news_items)
        log(f"   Found {len(political_findings)} political/business connections")

        # Step 5: Market intelligence (no AI needed)
        log("Fetching market intelligence (FII/DII, bulk deals, insider trades)...")
        market_intel = fetch_all_market_intelligence()

        # Step 6: AI analysis — ONE call using all intel
        if use_ai:
            log("Running AI analysis (Gemini) with full intelligence...")
            ai_insights = analyze_with_full_intelligence(
                news_items, stock_data, tech_signals,
                political_findings=political_findings,
                market_intel=market_intel,
            )
        else:
            log("Skipping AI (night cycle — preserving quota for market hours)")
            ai_insights = {
                "stocks": [], "market_sentiment": "neutral",
                "market_summary": "Pre-market technical scan",
                "top_opportunity": "", "risks_to_watch": [],
            }

        # Step 7: Generate signals
        log("Generating trading signals...")
        signals = generate_signals(ai_insights, tech_signals, stock_data)

        # Step 8: Save data.json
        output = {
            "last_updated":    datetime.now(timezone.utc).astimezone(
                                   timezone(timedelta(hours=5, minutes=30))
                               ).isoformat(),
            "signals":         signals,
            "news_count":      len(news_items),
            "stocks_analyzed": len(stock_data),
            "top_news":        news_items[:10],
            "tech_signals":    tech_signals,
            "political_intel": political_findings[:5],
            "market_intel":    {
                "fii_dii":    market_intel.get("fii_dii", {}),
                "bulk_deals": market_intel.get("bulk_deals", [])[:5],
            },
            "ai_powered": bool(ai_insights.get("stocks")),
        }

        os.makedirs('../dashboard', exist_ok=True)
        with open("../dashboard/data.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, default=str)
        log("   data.json saved successfully")

        # Step 9: Telegram alerts for strong signals
        strong_signals = [s for s in signals
                          if s.get("confidence", 0) >= 75
                          and not s.get("is_market_summary")]
        for signal in strong_signals:
            send_alert(signal)
            log(f"   Alert sent: {signal['symbol']} - {signal['action']}")

        log(f"Cycle complete. {len(strong_signals)} strong signals found.\n")
        return ai_insights

    except Exception as e:
        log(f"❌ Error in analysis cycle: {e}")
        import traceback
        traceback.print_exc()


def morning_briefing():
    """Runs at 8:30 AM IST (03:00 UTC) — uses 1 AI call"""
    log("📋 Sending morning briefing...")
    ai_insights = run_analysis(use_ai=True) or {}
    send_morning_briefing(
        market_sentiment = ai_insights.get("market_sentiment", "neutral"),
        top_opportunity  = ai_insights.get("top_opportunity", ""),
        risks            = ai_insights.get("risks_to_watch", []),
        ai_powered       = bool(ai_insights.get("stocks")),
    )


def night_cycle():
    """Runs during night hours — no AI call to preserve quota"""
    run_analysis(use_ai=False)


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    # Start Flask
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    utc_now = datetime.now(timezone.utc)
    ist_now = utc_now + timedelta(hours=5, minutes=30)
    log(f"Web server started on port {os.environ.get('PORT', 8080)}")
    log("=" * 60)
    log("  INDIA STOCK AI - INTELLIGENCE ENGINE STARTED")
    log(f"  Server time: {utc_now.strftime('%H:%M UTC')} = {ist_now.strftime('%H:%M IST')}")
    log(f"  Gemini quota: 20 requests/day → 1 call per 90-min cycle")
    log("=" * 60)

    # Notify on startup
    send_startup_message()

    # Run immediately on start (with AI)
    run_analysis(use_ai=True)

    # ── Scheduler (ALL TIMES IN UTC) ──────────────────────────────────────────
    # 90-min cycles during market + pre/post hours (with AI)
    # IST 7:00 AM = UTC 01:30
    # IST 8:30 AM = UTC 03:00  ← morning briefing
    # IST 3:30 PM = UTC 10:00  ← market close
    # IST 5:00 PM = UTC 11:30  ← last post-market cycle

    schedule.every(90).minutes.do(run_analysis, use_ai=True)

    # Morning briefing at 8:30 AM IST = 03:00 UTC
    schedule.every().day.at("03:00").do(morning_briefing)

    # Evening summary at 3:30 PM IST = 10:00 UTC
    schedule.every().day.at("10:00").do(send_daily_summary)

    log("Scheduler running. Analysis every 90 minutes.")
    log("Morning briefing: 8:30 AM IST | Market close summary: 3:30 PM IST")
    log(f"Quota usage: ~17 AI calls/day (limit: 20/day)")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
