"""
📲 Telegram Notifier - Free, instant alerts to your phone
Setup: Create bot via @BotFather on Telegram (completely free)
"""

import requests
import pytz
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
IST       = pytz.timezone('Asia/Kolkata')

def now_ist():
    """Always returns current time in IST — Railway servers run UTC"""
    return datetime.now(IST)

def _is_market_open():
    """Safety-net check — Mon–Fri, 9:15 AM to 3:30 PM IST only"""
    now = now_ist()
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    return 9*60+15 <= t <= 15*60+30

def send_message(text, parse_mode="HTML"):
    """Send a message via Telegram"""
    try:
        response = requests.post(
            f"{BASE_URL}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"   ⚠️ Telegram error: {e}")
        return False

def send_alert(signal):
    """Send a trading signal alert — only during market hours"""
    if not _is_market_open():
        return False   # silent drop — main.py logs this already

    action = signal["action"]
    symbol = signal["symbol"]
    confidence = signal["confidence"]
    price = signal.get("current_price", "N/A")
    target = signal.get("target_price", "N/A")
    stop_loss = signal.get("stop_loss", "N/A")
    risk = signal.get("risk_level", "MEDIUM")
    reason = signal.get("reason", "")
    horizon = signal.get("time_horizon", "swing")

    emoji = {
        "BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "WATCH": "👀",
    }.get(action, "⚪")
    risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(risk, "⚪")

    # Score breakdown if available
    sb = signal.get("score_breakdown", {})
    score_line = ""
    if sb:
        tech_s  = sb.get("technical",   {}).get("score", "—")
        fund_s  = sb.get("fundamental", {}).get("score", "—")
        ai_s    = sb.get("ai_sentiment",{}).get("score", "—")
        score_line = f"\n📐 <b>Score:</b> Tech {tech_s} · Fundamental {fund_s} · AI {ai_s}"

    ist_now = now_ist()
    message = f"""
{emoji} <b>SIGNAL: {action} {symbol}</b>

💰 <b>Price:</b> ₹{price}
🎯 <b>Target:</b> ₹{target}
🛑 <b>Stop Loss:</b> ₹{stop_loss}
📊 <b>Confidence:</b> {confidence}%
⏱ <b>Time Horizon:</b> {horizon.upper()}
{risk_emoji} <b>Risk:</b> {risk}{score_line}

💡 <b>Reason:</b> {reason}

🕐 {ist_now.strftime('%d %b %Y, %I:%M %p IST')}
    """.strip()
    return send_message(message)

def send_daily_summary():
    """Send end-of-day performance summary"""
    ist_now = now_ist()
    message = f"""
📋 <b>DAILY MARKET SUMMARY</b>
{ist_now.strftime('%d %B %Y')}

🇮🇳 Indian Market Session Closed

✅ Analysis complete for today.
📊 Check your dashboard for full signal history.

<i>Next analysis: Pre-market tomorrow at 8:30 AM IST</i>
    """.strip()
    return send_message(message)

def send_morning_briefing(market_sentiment, top_opportunity, risks):
    """Send pre-market morning briefing"""
    sentiment_emoji = {
        "bullish": "📈", "bearish": "📉", "neutral": "➡️"
    }.get(market_sentiment.lower(), "📊")

    risks_text = "\n".join([f"  ⚠️ {r}" for r in risks[:3]])
    ist_now    = now_ist()

    message = f"""
🌅 <b>MORNING BRIEFING</b>
{ist_now.strftime('%d %B %Y, %A')}

{sentiment_emoji} <b>Market Outlook:</b> {market_sentiment.upper()}

🎯 <b>Top Opportunity:</b>
{top_opportunity}

⚠️ <b>Risks to Watch:</b>
{risks_text}

Market opens at 9:15 AM IST
Good luck today! 🚀
    """.strip()
    return send_message(message)

def send_startup_message():
    """Send message when system starts"""
    ist_now = now_ist()
    message = f"""
🚀 <b>Stock AI System Started!</b>
{ist_now.strftime('%d %b %Y, %I:%M %p IST')}

Your 24/7 India market intelligence is now active.
Analysing NSE/BSE stocks + news every 30 minutes.

You'll receive alerts for:
🟢 Strong BUY signals (75%+ confidence)
🔴 Strong SELL signals (75%+ confidence)
🌅 Morning briefing at 9:00 AM IST
📋 Evening summary at 3:30 PM IST

<i>System is running and monitoring markets...</i>
    """.strip()
    return send_message(message)
