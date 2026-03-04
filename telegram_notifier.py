"""
Telegram Notifier - Free, instant alerts to your phone
Setup: Create bot via @BotFather on Telegram (completely free)
"""

import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def send_message(text, parse_mode="HTML"):
    """Send a message via Telegram"""
    try:
        response = requests.post(
            f"{BASE_URL}/sendMessage",
            json={
                "chat_id":                 TELEGRAM_CHAT_ID,
                "text":                    text,
                "parse_mode":              parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"   Warning: Telegram error: {e}")
        return False

def send_alert(signal):
    """Send a trading signal alert"""
    action    = signal["action"]
    symbol    = signal["symbol"]
    confidence = signal["confidence"]
    price     = signal.get("current_price", "N/A")
    target    = signal.get("target_price", "N/A")
    stop_loss = signal.get("stop_loss", "N/A")
    risk      = signal.get("risk_level", "MEDIUM")
    reason    = signal.get("reason", "")
    horizon   = signal.get("time_horizon", "swing")

    emoji = {
        "BUY":   "🟢",
        "SELL":  "🔴",
        "HOLD":  "🟡",
        "WATCH": "👀",
    }.get(action, "⚪")

    risk_emoji = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(risk, "⚪")

    message = f"""
{emoji} <b>SIGNAL: {action} {symbol}</b>

💰 <b>Price:</b> ₹{price}
🎯 <b>Target:</b> ₹{target}
🛑 <b>Stop Loss:</b> ₹{stop_loss}
📊 <b>Confidence:</b> {confidence}%
⏱ <b>Time Horizon:</b> {horizon.upper()}
{risk_emoji} <b>Risk:</b> {risk}

💡 <b>Reason:</b> {reason}

🕐 {datetime.now().strftime('%d %b %Y, %I:%M %p IST')}
    """.strip()

    return send_message(message)

def send_daily_summary():
    """Send end-of-day performance summary"""
    message = f"""
📋 <b>DAILY MARKET SUMMARY</b>
{datetime.now().strftime('%d %B %Y')}

🇮🇳 Indian Market Session Closed

✅ Analysis complete for today.
📊 Check your dashboard for full signal history.

<i>Next analysis: Pre-market tomorrow at 8:30 AM IST</i>
    """.strip()

    return send_message(message)

def send_morning_briefing(market_sentiment="neutral", top_opportunity="", risks=None):
    """Send pre-market morning briefing"""
    if risks is None:
        risks = []

    sentiment_emoji = {
        "bullish": "📈",
        "bearish": "📉",
        "neutral": "➡️",
    }.get(market_sentiment.lower(), "📊")

    risks_text = "\n".join([f"  ⚠️ {r}" for r in risks[:3]]) or "  ⚠️ Monitor global cues"

    message = f"""
🌅 <b>MORNING BRIEFING</b>
{datetime.now().strftime('%d %B %Y, %A')}

{sentiment_emoji} <b>Market Outlook:</b> {market_sentiment.upper()}

🎯 <b>Top Opportunity:</b>
{top_opportunity or 'Analysis running...'}

⚠️ <b>Risks to Watch:</b>
{risks_text}

Market opens at 9:15 AM IST
Good luck today! 🚀
    """.strip()

    return send_message(message)

def send_startup_message():
    """Send message when system starts"""
    message = """
🚀 <b>Stock AI System Started!</b>

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
