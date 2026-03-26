"""
India Stock AI Intelligence Engine
Runs every 30 minutes, analyses news + stocks, sends Telegram alerts
"""

import schedule
import time
import json
import os
import glob
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

# ── Flask app ────────────────────────────────────────────
app = Flask(__name__)
CORS(app, supports_credentials=True)

# ── Logging ──────────────────────────────────────────────
IST = pytz.timezone('Asia/Kolkata')

def log(msg):
    timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    line = f"[{timestamp}] {msg}"
    print(line)
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ── Load HTML files into memory ──────────────────────────
_login_html     = None
_dashboard_html = None

def _find_file(filename):
    """
    Search for a file in multiple locations.
    Returns full path if found, None otherwise.
    """
    # 1. Same directory as this script (most reliable)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 2. Current working directory
    cwd = os.getcwd()
    # 3. /app (Railway default)
    # 4. Plain relative path
    candidates = [
        os.path.join(script_dir, filename),
        os.path.join(cwd, filename),
        os.path.join('/app', filename),
        filename,
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

def _load_html_files():
    global _login_html, _dashboard_html

    script_dir = os.path.dirname(os.path.abspath(__file__))
    cwd        = os.getcwd()
    log(f"  📁 script_dir: {script_dir}")
    log(f"  📁 cwd: {cwd}")

    # List all files Railway can see
    all_files = glob.glob(os.path.join(script_dir, '*'))
    log(f"  📄 Files in script_dir: {[os.path.basename(f) for f in all_files]}")

    for fname, varname in [('login.html', 'login'), ('index.html', 'dashboard')]:
        path = _find_file(fname)
        if path:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            if varname == 'login':
                _login_html = content
            else:
                _dashboard_html = content
            log(f"  ✅ {fname} loaded from: {path}")
        else:
            log(f"  ❌ {fname} NOT FOUND — searched: {script_dir}, {cwd}, /app")

def get_login_html():
    return _login_html or '<h1>Login page not found</h1>'

def get_dashboard_html():
    if _dashboard_html is None:
        return None
    gemini_key = os.environ.get('GEMINI_API_KEY', '')
    return _dashboard_html.replace(
        "const GEMINI_API_KEY = '';",
        f"const GEMINI_API_KEY = '{gemini_key}';"
    )

# ── Register auth routes ─────────────────────────────────
register_auth_routes(app, get_login_html, get_dashboard_html)

# ── Protected data API ───────────────────────────────────
@app.route('/data.json')
@require_auth
def serve_data():
    try:
        return send_file('./data.json', mimetype='application/json')
    except Exception:
        return jsonify({
            "signals": [], "top_news": [], "last_updated": "Starting up...",
            "news_count": 0, "stocks_analyzed": 0, "ai_powered": False,
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

# ── Health check (PUBLIC — debug info) ──────────────────
@app.route('/health')
def health():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cwd        = os.getcwd()
    all_files  = [os.path.basename(f) for f in glob.glob(os.path.join(script_dir, '*'))]
    return jsonify({
        "status":           "ok",
        "time":             datetime.now(IST).isoformat(),
        "script_dir":       script_dir,
        "cwd":              cwd,
        "index_found":      _find_file('index.html'),
        "login_found":      _find_file('login.html'),
        "dashboard_loaded": _dashboard_html is not None,
        "login_loaded":     _login_html is not None,
        "files_visible":    all_files,
    }), 200

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

# ═══════════════════════════════════════════════════════════════════
# LIVE INDEX FETCH
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
        if 'nifty' in indices and 'sensex' in indices:
            return indices
        raise ValueError(f"Incomplete: {list(indices.keys())}")
    except Exception as e:
        log(f"   ⚠️  NSE failed ({e}) — falling back to yfinance")
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

        log("Cycle complete.\n")
    except Exception as e:
        log(f"Error in analysis cycle: {e}")

def morning_briefing():
    if not is_pre_market() and not is_market_open():
        return
    run_analysis()
    send_daily_summary()

# ── Mutual Fund Discovery ─────────────────────────────────
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

# ── Entry point ───────────────────────────────────────────
def main():
    _load_html_files()

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
