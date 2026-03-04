"""
Configuration - Edit this file to customize your system
When running locally: put your keys directly below
When running on Railway: keys come from environment variables automatically
"""

import os

# ============================================================
# API KEYS
# ============================================================

# Reads from Railway environment variables when deployed
# Falls back to the string you put here when running locally
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY",     "YOUR_GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "YOUR_TELEGRAM_CHAT_ID")

# ============================================================
# STOCK WATCHLIST - NSE Symbols
# ============================================================

WATCHLIST = [
    # Banking & Finance
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS",
    "AXISBANK.NS", "BAJFINANCE.NS",

    # IT & Tech
    "TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS",

    # Industrial & Conglomerate
    "RELIANCE.NS", "LT.NS", "ADANIENT.NS",

    # Auto
    "MARUTI.NS", "TATAMOTORS.NS", "BAJAJ-AUTO.NS",

    # Pharma
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS",

    # Telecom
    "BHARTIARTL.NS",

    # Consumer
    "HINDUNILVR.NS", "ITC.NS",

    # Energy
    "NTPC.NS", "POWERGRID.NS", "ONGC.NS", "COALINDIA.NS",

    # Metals
    "TATASTEEL.NS", "JSWSTEEL.NS",

    # Index
    "^NSEI",   # Nifty 50
    "^BSESN",  # Sensex
]

# ============================================================
# SIGNAL THRESHOLDS
# ============================================================

ALERT_CONFIDENCE_THRESHOLD = 75   # Minimum % to send Telegram alert
RSI_OVERSOLD                = 30   # Below = potential BUY
RSI_OVERBOUGHT              = 70   # Above = potential SELL
VOLUME_SPIKE_MULTIPLIER     = 2.0  # x times average volume

# ============================================================
# NEWS SOURCES (All Free RSS Feeds)
# ============================================================

NEWS_SOURCES = [
    "https://economictimes.indiatimes.com/markets/stocks/rss.cms",
    "https://www.business-standard.com/rss/markets-106.rss",
    "https://www.moneycontrol.com/rss/latestnews.xml",
    "https://www.financialexpress.com/market/feed/",
]

# ============================================================
# SYSTEM SETTINGS
# ============================================================

LOG_FILE     = "logs/system.log"
DATA_FILE    = "data.json"
HISTORY_DAYS = 90
