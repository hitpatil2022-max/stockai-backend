"""
Configuration - Edit this file to customize your system
When running locally: put your keys directly below
When running on Railway: keys come from environment variables automatically
"""

import os

# ============================================================
# API KEYS
# ============================================================

GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY",     "YOUR_GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "YOUR_TELEGRAM_CHAT_ID")

# ============================================================
# NIFTY 50 - All 50 stocks (as of 2026)
# ============================================================

NIFTY_50 = [
    # Banking & Finance
    "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS",
    "AXISBANK.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS",
    "SBILIFE.NS", "INDUSINDBK.NS",

    # IT & Tech
    "TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS",
    "LTI.NS",

    # Industrial & Infrastructure
    "RELIANCE.NS", "LT.NS", "ADANIENT.NS", "ADANIPORTS.NS",
    "ULTRACEMCO.NS", "GRASIM.NS", "SHREECEM.NS",

    # Auto
    "MARUTI.NS", "TATAMOTORS.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS",
    "HEROMOTOCO.NS", "M&M.NS",

    # Pharma & Healthcare
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS",
    "APOLLOHOSP.NS",

    # Telecom & Media
    "BHARTIARTL.NS",

    # Consumer & FMCG
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS",
    "TATACONSUM.NS",

    # Energy & Utilities
    "NTPC.NS", "POWERGRID.NS", "ONGC.NS", "COALINDIA.NS",
    "BPCL.NS",

    # Metals & Mining
    "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS",

    # Paint & Specialty
    "ASIANPAINT.NS",

    # Tobacco / Consumer
    # (ITC already above)
]

# ============================================================
# NIFTY NEXT 50 - 50 additional large-caps
# ============================================================

NIFTY_NEXT_50 = [
    # Banking & Finance
    "BANDHANBNK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "PNB.NS",
    "CANBK.NS", "BANKBARODA.NS", "MUTHOOTFIN.NS", "CHOLAFIN.NS",

    # IT & Tech
    "MPHASIS.NS", "LTTS.NS", "PERSISTENT.NS", "COFORGE.NS",

    # Auto & Auto Ancillary
    "MOTHERSUMI.NS", "BALKRISIND.NS", "TVSMOTOR.NS", "ASHOKLEY.NS",

    # Pharma
    "TORNTPHARM.NS", "AUROPHARMA.NS", "BIOCON.NS", "LUPIN.NS",

    # Consumer & Retail
    "DMART.NS", "PAGEIND.NS", "TRENT.NS", "NYKAA.NS", "ZOMATO.NS",

    # Energy & Power
    "ADANIGREEN.NS", "TATAPOWER.NS", "CESC.NS", "NHPC.NS",

    # Industrial & Capital Goods
    "SIEMENS.NS", "ABB.NS", "HAVELLS.NS", "VOLTAS.NS", "BHEL.NS",

    # Metals & Chemicals
    "VEDL.NS", "SAIL.NS", "NMDC.NS", "PIIND.NS", "UPL.NS",

    # Telecom & Media
    "IDEA.NS", "ZEEL.NS",

    # Real Estate
    "DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS",

    # Specialty
    "PIDILITIND.NS", "BERGEPAINT.NS", "CONCOR.NS",
]

# ============================================================
# INDEXES (for market sentiment — not used in signal engine)
# ============================================================

INDEXES = [
    "^NSEI",   # Nifty 50
    "^BSESN",  # Sensex
    "^NSMIDCP", # Nifty Midcap
]

# ============================================================
# FULL WATCHLIST = Nifty 50 + Next 50 + Indexes
# ============================================================

WATCHLIST = NIFTY_50 + NIFTY_NEXT_50 + INDEXES

# ============================================================
# SIGNAL THRESHOLDS
# ============================================================

ALERT_CONFIDENCE_THRESHOLD = 75   # Minimum % to send Telegram alert
RSI_OVERSOLD               = 30   # Below = potential BUY
RSI_OVERBOUGHT             = 70   # Above = potential SELL
VOLUME_SPIKE_MULTIPLIER    = 2.0  # x times average volume

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

LOG_FILE      = "logs/system.log"
DATA_FILE     = "../dashboard/data.json"
HISTORY_DAYS  = 90
