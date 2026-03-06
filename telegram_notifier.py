"""
📲 Telegram Notifier - Free, instant alerts to your phone
Setup: Create bot via @BotFather on Telegram (completely free)
"""

import requests
import json
import os
from datetime import datetime, timezone, timedelta
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def _ist_now():
    """Current time in IST"""
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)

def send_message(text, parse_mode="HTML"):
    """Send a message via Telegram"""
    try:
        response = requests.post(
            f"{BASE_URL}/sendMessage",
            json={
                "chat_id":                  TELEGRAM_CHAT_ID,
                "text":                     text,
                "parse_mode":              parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"   ⚠️ Telegram error: {e}")
        return False


def send_alert(signal):
    """Send a trading signal alert"""
    action     = signal.get("action", "")
    symbol     = signal.get("symbol", "")
    confidence = signal.get("confidence", 0)
    price      = signal.get("current_price", "N/A")
    target     = signal.get("target_price", "N/A")
    stop_loss  = signal.get("stop_loss", "N/A")
    risk       = signal.get("risk_level", "MEDIUM")
    reason     = signal.get("reason", "")
    horizon    = signal.get("time_horizon", "swing")
    ai_powered = signal.get("ai_powered", False)
    index_grp  = signal.get("index_group", "")
    sources    = signal.get("signal_sources", ["technical"])

    emoji      = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "WATCH": "👀"}.get(action, "⚪")
    risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(risk, "⚪")
    ai_badge   = "🤖 AI+Technical" if ai_powered else "📊 Technical only"
    group_tag  = f" <i>({index_grp})</i>" if index_grp else ""

    # Price range calculations
    price_line  = ""
    rr_line     = ""
    if isinstance(price, (int, float)) and isinstance(target, (int, float)) and isinstance(stop_loss, (int, float)):
        upside   = round(((target - price) / price) * 100, 1) if action == "BUY" else round(((price - target) / price) * 100, 1)
        risk_pct = round(abs((price - stop_loss) / price) * 100, 1)
        rr       = round(upside / risk_pct, 1) if risk_pct > 0 else "N/A"
        arrow    = "▲" if action in ("BUY", "WATCH") else "▼"
        price_line = (
            f"\n┌──────────┬──────────┬──────────┐\n"
            f"│ {'Buy Below' if action=='BUY' else 'Sell At':^8} │  Target  │ Stop Loss│\n"
            f"│ ₹{str(price):^8} │ ₹{str(target):^8}│ ₹{str(stop_loss):^8}│\n"
            f"└──────────┴──────────┴──────────┘"
        )
        rr_line = f"\n{arrow} {upside}% upside · 🛑 Risk: {risk_pct}% · R:R = {rr}x"

    sources_text = " · ".join([
        {"technical": "📊 Technical", "fii_buying": "🌍 FII Buying",
         "fii_selling": "🌍 FII Selling", "insider_buy": "🔑 Insider Buy",
         "bulk_deal": "🐋 Bulk Deal", "political": "🏛️ Political"
        }.get(s, s) for s in sources
    ])

    message = (
        f"{emoji} <b>SIGNAL: {action} {symbol}</b>{group_tag}\n"
        f"📊 Confidence: {confidence}%  |  ⏱ {horizon.upper()}\n"
        f"{risk_emoji} Risk: {risk}  |  {ai_badge}"
        f"{price_line}"
        f"{rr_line}\n\n"
        f"💡 <b>Reason:</b> {reason}\n"
        f"🔍 <b>Signals:</b> {sources_text}\n\n"
        f"🕐 {_ist_now().strftime('%d %b %Y, %I:%M %p IST')}"
    )
    return send_message(message)


def send_morning_briefing(market_sentiment="neutral", top_opportunity="",
                          risks=None, ai_powered=False):
    """Send pre-market morning briefing at 8:30 AM IST"""
    if risks is None:
        risks = []

    sentiment_emoji = {"bullish": "📈", "bearish": "📉", "neutral": "➡️"}.get(
        market_sentiment.lower(), "📊")

    risks_text  = "\n".join([f"  ⚠️ {r}" for r in risks[:3]]) or "  • No specific risks flagged"
    ai_note     = "🤖 AI-powered analysis" if ai_powered else "📊 Technical analysis (AI quota resets at 1:30 PM IST)"
    top_opp     = top_opportunity or "Scanning for opportunities at market open..."

    message = (
        f"🌅 <b>MORNING BRIEFING</b>\n"
        f"{_ist_now().strftime('%d %B %Y, %A')}\n\n"
        f"{sentiment_emoji} <b>Market Outlook:</b> {market_sentiment.upper()}\n\n"
        f"🎯 <b>Top Opportunity:</b>\n  {top_opp}\n\n"
        f"⚠️ <b>Risks to Watch:</b>\n{risks_text}\n\n"
        f"{ai_note}\n"
        f"Market opens at 9:15 AM IST 🚀"
    )
    return send_message(message)


def send_daily_summary(signals_count=0, strong_count=0):
    """Send end-of-day performance summary at 3:30 PM IST"""

    # Try to read today's signal count from data.json
    try:
        data_path = "../dashboard/data.json"
        if os.path.exists(data_path):
            with open(data_path, "r") as f:
                data = json.load(f)
            sigs = [s for s in data.get("signals", []) if not s.get("is_market_summary")]
            signals_count = len(sigs)
            strong_count  = len([s for s in sigs if s.get("is_strong")])
            ai_powered    = data.get("ai_powered", False)
        else:
            ai_powered = False
    except Exception:
        ai_powered = False

    ai_note = "🤖 AI + Technical signals" if ai_powered else "📊 Technical-only signals today"

    message = (
        f"📋 <b>DAILY MARKET SUMMARY</b>\n"
        f"{_ist_now().strftime('%d %B %Y')}\n\n"
        f"🇮🇳 Indian Market Session Closed\n\n"
        f"✅ Stocks analysed: 100 (Nifty 50 + Next 50)\n"
        f"📊 Total signals today: {signals_count}\n"
        f"🔥 Strong signals (75%+): {strong_count}\n"
        f"{ai_note}\n\n"
        f"📱 Check your dashboard for full signal history.\n\n"
        f"<i>Next pre-market briefing: 8:30 AM IST tomorrow</i>"
    )
    return send_message(message)


def send_startup_message():
    """Send message when system starts"""
    message = (
        f"🚀 <b>Stock AI System Started!</b>\n\n"
        f"Your 24/7 India market intelligence is now active.\n"
        f"Monitoring <b>100 stocks</b> (Nifty 50 + Next 50)\n"
        f"Analysis runs every <b>90 minutes</b>\n\n"
        f"You'll receive alerts for:\n"
        f"🟢 Strong BUY signals (75%+ confidence)\n"
        f"🔴 Strong SELL signals (75%+ confidence)\n"
        f"🌅 Morning briefing at 8:30 AM IST\n"
        f"📋 Evening summary at 3:30 PM IST\n\n"
        f"<i>System is running and monitoring markets...</i>"
    )
    return send_message(message)
