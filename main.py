"""
India Stock AI Intelligence Engine
Runs every 30 minutes, analyses news + stocks, sends Telegram alerts
"""

import schedule
import time
import json
import os
import threading
import requests
import pytz
from datetime import datetime
from flask import Flask, send_file, jsonify, request
from flask_cors import CORS

# ── Market Hours Check ──────────────────────────────────
def is_market_open():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    return 9*60+15 <= t <= 15*60+30

def is_pre_market():
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
from mutual_fund_engine import fetch_top_mutual_funds
from auth import register_auth_routes, get_current_user, require_auth

# ── Flask app ───────────────────────────────────────────
app = Flask(__name__)
CORS(app, supports_credentials=True)

# ── Load HTML files into memory once at startup ─────────
# This keeps them off the public filesystem — only served via auth
_login_html     = None
_dashboard_html = None

def _load_html_files():
    global _login_html, _dashboard_html
    try:
        with open('./login.html', 'r', encoding='utf-8') as f:
            _login_html = f.read()
        log('  ✅ login.html loaded')
    except Exception as e:
        log(f'  ⚠️  Could not load login.html: {e}')

    try:
        with open('./index.html', 'r', encoding='utf-8') as f:
            _dashboard_html = f.read()
        log('  ✅ index.html loaded')
    except Exception as e:
        log(f'  ⚠️  Could not load index.html: {e}')

def get_login_html():
    return _login_html or '<h1>Login page not found</h1>'

def get_dashboard_html():
    return _dashboard_html

# ── Register auth routes (/, /login, /auth/google, /auth/callback, /logout)
register_auth_routes(app, get_login_html, get_dashboard_html)

# ── Protected data API ──────────────────────────────────
@app.route('/data.json')
@require_auth
def serve_data():
    try:
        return send_file('./data.json', mimetype='application/json')
    except Exception:
        return jsonify({
            "signals": [],
            "top_news": [],
            "last_updated": "Starting up...",
            "news_count": 0,
            "stocks_analyzed": 0,
            "ai_powered": False,
            "indices": {},
            "market_intel": {
                "fii_dii": {
                    "fii": {"action": "BUYING", "net_cr": 0},
                    "dii": {"action": "BUYING", "net_cr": 0},
                    "sentiment": "neutral"
                },
                "bulk_deals": []
            }
        })

# ── Health check (public — Railway needs this) ──────────
@app.route('/health')
def health():
    return jsonify({"status": "ok", "time": datetime.now(IST).isoformat()}), 200

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ── Logging ─────────────────────────────────────────────
IST = pytz.timezone('Asia/Kolkata')

def log(msg):
    timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    line = f"[{timestamp}] {msg}"
    print(line)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ═══════════════════════════════════════════════════════════════════
# LIVE INDEX FETCH — NSE India official API
# ═══════════════════════════════════════════════════════════════════

def fetch_nse_indices():
    INDEX_MAP = {
        'NIFTY 50':        'nifty',
        'S&P BSE SENSEX':  'sensex',
        'NIFTY MIDCAP 100':'midcap',
    }
    HEADERS = {
        'User-Agent':      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept':          'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer':         'https://www.nseindia.com/',
        'Origin':          'https://www.nseindia.com',
    }
    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        session.get('https://www.nseindia.com', timeout=10)
        resp = session.get('https://www.nseindia.com/api/allIndices', timeout=10)
        resp.raise_for_status()
        data = resp.json()
        indices = {}
        for item in data.get('data', []):
            key = INDEX_MAP.get(item.get('index'))
            if not key:
                continue
            indices[key] = {
                'price':      round(float(item.get('last',      0)), 2),
                'change':     round(float(item.get('variation', 0)), 2),
                'change_pct': round(float(item.get('percentChange', 0)), 2),
                'prev_close': round(float(item.get('previousClose', 0)), 2),
                'open':       round(float(item.get('open',  0)), 2),
                'high':       round(float(item.get('high',  0)), 2),
                'low':        round(float(item.get('low',   0)), 2),
                'source':     'NSE',
            }
            log(f"   ✅ NSE {item.get('index')}: {indices[key]['price']:,.2f} ({indices[key]['change_pct']:+.2f}%)")
        if 'nifty' in indices and 'sensex' in indices:
            return indices
        raise ValueError(f"Incomplete NSE response — got: {list(indices.keys())}")
    except Exception as e:
        log(f"   ⚠️  NSE allIndices failed ({e}) — falling back to yfinance")
        return {}


def extract_yfinance_indices(stock_data):
    SYM_MAP = {'^NSEI': 'nifty', '^BSESN': 'sensex', '^NSMIDCP': 'midcap'}
    indices = {}
    for sym, key in SYM_MAP.items():
        d = stock_data.get(sym)
        if d and d.get('current_price', 0) > 0:
            indices[key] = {
                'price':      d['current_price'],
                'change':     d.get('change', 0),
                'change_pct': d.get('change_pct', 0),
                'prev_close': d.get('prev_close', 0),
                'open':       d.get('open', 0),
                'high':       d.get('high', 0),
                'low':        d.get('low', 0),
                'source':     'yfinance',
            }
    return indices


# ── Main analysis cycle ──────────────────────────────────
def run_analysis():
    log("Starting analysis cycle...")
    try:
        log("Fetching news...")
        news_items = fetch_all_news()
        log(f"   Found {len(news_items)} news items")

        log("Fetching stock data...")
        stock_data = get_stock_data(WATCHLIST)

        log("Calculating technical indicators...")
        tech_signals = calculate_technical_signals(stock_data)

        log("Running AI analysis (Gemini)...")
        ai_insights = analyze_with_ai(news_items, stock_data, tech_signals)

        log("Generating signals...")
        signals = generate_signals(ai_insights, tech_signals, stock_data)

        log("Fetching live indices...")
        indices = fetch_nse_indices()
        if not indices or 'nifty' not in indices:
            indices = extract_yfinance_indices(stock_data)

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
            "indices":         indices,
            "market_intel": {
                "fii_dii": {
                    "fii": {"action": "BUYING" if is_bullish else "SELLING", "net_cr": 0},
                    "dii": {"action": "BUYING" if is_bullish else "SELLING", "net_cr": 0},
                    "sentiment": mkt_tone,
                },
                "bulk_deals": [],
            }
        }

        with open("./data.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, default=str)

        strong_signals = [
            s for s in signals
            if s.get("confidence", 0) >= 75
            and not s.get("is_market_summary", False)
            and s.get("action") in ("BUY", "SELL", "WATCH")
            and s.get("current_price", 0) > 0
        ]
        if is_market_open():
            for signal in strong_signals:
                send_alert(signal)
            log(f"   {len(strong_signals)} alerts sent")
        else:
            log(f"   Market closed — {len(strong_signals)} alerts suppressed")

        log(f"Cycle complete.\n")
    except Exception as e:
        log(f"Error in analysis cycle: {e}")


def morning_briefing():
    if not is_pre_market() and not is_market_open():
        return
    run_analysis()
    send_daily_summary()


# ── Mutual Fund Discovery ────────────────────────────────
def run_mf_discovery():
    log("Starting mutual fund discovery & ranking…")
    try:
        mf_data = fetch_top_mutual_funds()
        if not mf_data or not mf_data.get('categories'):
            log("  ⚠️  MF discovery returned empty result")
            return
        existing = {}
        try:
            with open("./data.json", "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass
        existing['mutual_funds'] = mf_data
        with open("./data.json", "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, default=str)
        total = sum(len(c['funds']) for c in mf_data['categories'])
        log(f"  ✅ MF discovery done — {total} funds across {len(mf_data['categories'])} categories")
    except Exception as e:
        log(f"  ❌ MF discovery failed: {e}")


# ── Entry point ──────────────────────────────────────────
def main():
    _load_html_files()  # load HTML into memory before serving

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    log("Web server started on port " + str(os.environ.get('PORT', 5000)))
    log("=" * 60)
    log("  INDIA STOCK AI — SECURE INTELLIGENCE ENGINE STARTED")
    log("=" * 60)

    run_analysis()

    mf_thread = threading.Thread(target=run_mf_discovery, daemon=True)
    mf_thread.start()

    schedule.every(30).minutes.do(run_analysis)
    schedule.every().day.at("03:30").do(morning_briefing)
    schedule.every().day.at("10:00").do(send_daily_summary)
    schedule.every().day.at("22:00").do(run_mf_discovery)

    log("Scheduler running. Analysis every 30 minutes.")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
