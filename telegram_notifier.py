"""
📲 Telegram Notifier - Rich signal alerts matching dashboard format
"""

import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def send_message(text, parse_mode="HTML"):
    try:
        response = requests.post(
            f"{BASE_URL}/sendMessage",
            json={
                "chat_id":               TELEGRAM_CHAT_ID,
                "text":                  text,
                "parse_mode":            parse_mode,
                "disable_web_page_preview": True,
            },
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"   ⚠️ Telegram error: {e}")
        return False

def send_alert(signal):
    """Send a trading signal alert with full price range, upside %, R:R ratio"""

    action     = signal.get("action",        "BUY")
    symbol     = signal.get("symbol",        "—")
    confidence = signal.get("confidence",    0)
    price      = signal.get("current_price", 0)
    target     = signal.get("target_price",  0)
    stop_loss  = signal.get("stop_loss",     0)
    risk       = signal.get("risk_level",    "MEDIUM")
    reason     = signal.get("reason",        "")
    horizon    = signal.get("time_horizon",  "swing")
    change_pct = signal.get("change_pct",    0)
    sources    = signal.get("signal_sources", [])
    impacts    = signal.get("impact_factors", [])

    # Upside / downside %
    upside_pct = round(((target - price) / price) * 100, 1) if price and target else None
    risk_pct   = round(((price - stop_loss) / price) * 100, 1) if price and stop_loss else None
    rr_ratio   = round(abs(upside_pct) / risk_pct, 1) if upside_pct and risk_pct and risk_pct > 0 else None

    # Emojis
    action_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "WATCH": "👀"}.get(action, "⚪")
    risk_emoji   = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(risk, "⚪")
    chg_emoji    = "📈" if (change_pct or 0) >= 0 else "📉"
    dir_arrow    = "▲" if action in ("BUY", "WATCH") else "▼"

    # Price range block
    price_block = ""
    if price or target or stop_loss:
        price_block = (
            f"\n\n┌─────────────────────────┐"
            f"\n│ {'BUY BELOW' if action in ('BUY','WATCH') else 'SELL AT':^9}  {'TARGET':^9}  {'STOP LOSS':^9} │"
            f"\n│ {'₹'+str(price):^9}  {'₹'+str(target):^9}  {'₹'+str(stop_loss):^9} │"
            f"\n└─────────────────────────┘"
        )

    # Upside / risk / R:R line
    stats_line = ""
    parts = []
    if upside_pct is not None:
        parts.append(f"{dir_arrow} {abs(upside_pct)}% {'upside' if action in ('BUY','WATCH') else 'downside'}")
    if risk_pct is not None:
        parts.append(f"🛑 Risk: {risk_pct}%")
    if rr_ratio is not None:
        parts.append(f"R:R = {rr_ratio}x")
    if parts:
        stats_line = "\n" + "  ·  ".join(parts)

    # Signal sources line
    sources_line = ""
    if sources:
        source_tags = {
            "technical":    "📊 Technical",
            "fii_buying":   "🌍 FII Buying",
            "fii_selling":  "🌍 FII Selling",
            "insider_buy":  "🔑 Insider Buy",
            "insider_sell": "🔑 Insider Sell",
            "political":    "🏛️ Political Link",
            "bulk_deal":    "🐋 Bulk Deal",
        }
        tags = [source_tags.get(s, s) for s in sources[:4]]
        sources_line = f"\n🔍 <b>Signals:</b> {' · '.join(tags)}"

    # Impact factors
    impacts_line = ""
    if impacts:
        impacts_line = f"\n🏷 <b>Factors:</b> {' · '.join(impacts[:3])}"

    message = (
        f"{action_emoji} <b>SIGNAL: {action} {symbol}</b>\n"
        f"{chg_emoji} Today: {'+' if (change_pct or 0) >= 0 else ''}{change_pct}%  |  "
        f"📊 Confidence: <b>{confidence}%</b>\n"
        f"⏱ Horizon: {horizon.upper()}  |  {risk_emoji} Risk: {risk}"
        f"{price_block}"
        f"{stats_line}"
        f"\n\n💡 <b>Analysis:</b> {reason}"
        f"{sources_line}"
        f"{impacts_line}"
        f"\n\n🕐 {datetime.now().strftime('%d %b %Y, %I:%M %p IST')}"
    )

    return send_message(message)

def send_morning_briefing(market_sentiment, top_opportunity, risks):
    sentiment_emoji = {"bullish": "📈", "bearish": "📉", "neutral": "➡️"}.get(
        market_sentiment.lower(), "📊")
    risks_text = "\n".join([f"  ⚠️ {r}" for r in risks[:3]])

    message = (
        f"🌅 <b>MORNING BRIEFING</b>\n"
        f"{datetime.now().strftime('%d %B %Y, %A')}\n\n"
        f"{sentiment_emoji} <b>Market Outlook:</b> {market_sentiment.upper()}\n\n"
        f"🎯 <b>Top Opportunity:</b>\n{top_opportunity}\n\n"
        f"⚠️ <b>Risks to Watch:</b>\n{risks_text}\n\n"
        f"Market opens at 9:15 AM IST\nGood luck today! 🚀"
    )
    return send_message(message)

def send_daily_summary():
    message = (
        f"📋 <b>DAILY MARKET SUMMARY</b>\n"
        f"{datetime.now().strftime('%d %B %Y')}\n\n"
        f"🇮🇳 Indian Market Session Closed\n\n"
        f"✅ Analysis complete for today.\n"
        f"📊 Check your dashboard for full signal history.\n\n"
        f"<i>Next analysis: Pre-market tomorrow at 8:30 AM IST</i>"
    )
    return send_message(message)

def send_startup_message():
    message = (
        f"🚀 <b>India Stock AI Started!</b>\n\n"
        f"24/7 intelligence active — NSE/BSE + News + FII/DII + Political Intel\n\n"
        f"You'll receive:\n"
        f"🟢 BUY signals with target, stop loss & R:R ratio\n"
        f"🔴 SELL signals for your portfolio stocks\n"
        f"🏛️ Political & insider trade alerts\n"
        f"🌅 Morning briefing at 9:00 AM IST\n"
        f"📋 Evening summary at 3:30 PM IST\n\n"
        f"<i>Monitoring markets every 30 minutes...</i>"
    )
    return send_message(message)
