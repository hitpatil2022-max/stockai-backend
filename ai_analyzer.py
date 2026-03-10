"""
🤖 AI Analyzer — Google Gemini (Free API)
Analyses news + technical + fundamental data for intelligent stock insights.
Now includes: business quality, competitive moat, sector outlook, chart pattern context.
"""

from google import genai
from google.genai import types
import json
from config import GEMINI_API_KEY
from datetime import datetime

client = genai.Client(api_key=GEMINI_API_KEY)

ANALYSIS_PROMPT = """
You are a senior Indian equity research analyst at a top-tier institution (like Motilal Oswal or Kotak Securities).
You have 20+ years of experience covering NSE/BSE stocks.
You analyse stocks using BOTH fundamental quality AND technical timing.

TODAY: {date}
MARKET: NSE/BSE India

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1 — TOP NEWS (Latest market-moving events)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{news}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2 — STOCK DATA (Technicals + Fundamentals)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{stock_data}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For each stock that appears in the news OR has a technical score above 60 OR below 40:

FUNDAMENTAL ASSESSMENT:
- Is the company a market leader or a follower in its sector?
- Does it have a competitive moat? (brand, patents, switching costs, cost advantage, network effect)
- Is the sector growing or declining over the next 2–3 years?
- Are the financial ratios (P/E vs sector, ROE, D/E, margins) healthy or concerning?

TECHNICAL TIMING:
- What is the price trend? (uptrend / downtrend / sideways)
- Is it above or below 200 DMA? (key signal)
- Any significant chart patterns detected?
- Is this a good entry point right now?

COMBINED VERDICT:
- Give a BUY / SELL / HOLD / WATCH signal
- Assign confidence 0-100 based on how strong BOTH fundamental AND technical pictures are
  * 80-100: Excellent fundamentals + ideal technical entry
  * 65-79:  Good fundamentals + reasonable entry
  * 50-64:  Mixed picture — either good fundamentals bad technicals or vice versa
  * Below 50: Avoid
- Give time horizon: intraday / swing (3-5 days) / short-term (2-4 weeks) / medium-term (3-6 months)
- Set a realistic target price and stop loss based on support/resistance

MARKET OVERVIEW:
- Overall market sentiment for today
- Single best trade opportunity right now
- Top 3 risks to watch for Indian market

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT — Valid JSON only. No markdown. No text outside the JSON.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{{
  "market_sentiment": "bullish|bearish|neutral",
  "market_summary": "2 sentence market summary",
  "top_opportunity": "SYMBOL: brief reason",
  "risks_to_watch": ["risk1", "risk2", "risk3"],
  "stocks": [
    {{
      "symbol": "RELIANCE",
      "action": "BUY",
      "confidence": 78,
      "reason": "Strong Q3 results + Jio 5G subscriber growth. RSI near oversold zone at 32, trading above 200 DMA.",
      "time_horizon": "swing",
      "target_price": 2850,
      "stop_loss": 2680,
      "risk_level": "MEDIUM",
      "impact_factors": ["Q3 beat", "Jio 5G growth", "Retail expansion"],
      "business_quality": "Market leader in telecom + retail + refining. Strong moat from Jio network effect and retail scale.",
      "sector_outlook": "Telecom sector growing — 5G rollout and data consumption rising steadily.",
      "moat": "Network effect (Jio), scale advantages in retail, integration across energy-to-digital"
    }}
  ]
}}
"""


def analyze_with_ai(news_items, stock_data, tech_signals):
    """Send enriched data to Gemini for intelligent analysis"""

    # ── Prepare news (top 15, highest importance first) ──
    sorted_news = sorted(news_items, key=lambda x: x.get("importance_score", 5), reverse=True)
    news_text = "\n".join([
        f"[{item.get('importance_score', 5):.1f}/10] [{item['source']}] {item['title']}"
        f"  → Stocks: {', '.join(item.get('mentioned_stocks', ['—']))}"
        for item in sorted_news[:15]
    ])

    # ── Prepare stock data (top 25 — technical + fundamental) ──
    stock_lines = []
    for symbol_full, tech in list(tech_signals.items())[:25]:
        stock = stock_data.get(symbol_full, {})
        sym   = symbol_full.replace(".NS", "")

        # Technical summary
        tech_line = (
            f"  Technical: Price=₹{stock.get('current_price','N/A')} "
            f"Change={stock.get('change_pct','N/A')}% "
            f"RSI={tech.get('rsi','N/A')}({tech.get('rsi_signal','')}) "
            f"MACD={tech.get('macd',{}).get('trend','N/A')} "
            f"MA200={'above' if tech.get('ma200_signal')=='above_200dma' else 'below' if tech.get('ma200_signal')=='below_200dma' else 'N/A'} "
            f"TechScore={tech.get('technical_score','N/A')}/100 "
            f"Vol={tech.get('volume_spike',1):.1f}x"
        )

        # Chart patterns
        patterns = tech.get("patterns", [])
        pat_line = ""
        if patterns:
            pat_names = [f"{p['pattern']}({p['type']})" for p in patterns[:3]]
            pat_line = f"\n  Patterns: {', '.join(pat_names)}"

        # Fundamental summary
        pe      = stock.get("pe_ratio")
        sec_pe  = stock.get("sector_pe")
        pe_str  = f"P/E={pe:.1f}(sector:{sec_pe})" if pe and sec_pe else "P/E=N/A"
        eps_g   = stock.get("eps_growth_pct")
        rev_g   = stock.get("revenue_growth_pct")
        roe     = stock.get("roe_pct")
        de      = stock.get("debt_to_equity")
        pm      = stock.get("profit_margin_pct")
        sector  = stock.get("sector", "")

        fund_line = (
            f"  Fundamental: {pe_str} "
            f"EPS_growth={f'{eps_g:.1f}%' if eps_g is not None else 'N/A'} "
            f"Rev_growth={f'{rev_g:.1f}%' if rev_g is not None else 'N/A'} "
            f"ROE={f'{roe:.1f}%' if roe is not None else 'N/A'} "
            f"D/E={f'{de:.2f}' if de is not None else 'N/A'} "
            f"Margin={f'{pm:.1f}%' if pm is not None else 'N/A'} "
            f"Sector={sector}"
        )

        stock_lines.append(f"\n{sym}:\n{tech_line}{pat_line}\n{fund_line}")

    stock_text = "\n".join(stock_lines)

    prompt = ANALYSIS_PROMPT.format(
        date=datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        news=news_text,
        stock_data=stock_text,
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.25,        # lower = more consistent, less hallucination
                max_output_tokens=3000,
            )
        )

        raw = response.text.strip()

        # Strip markdown fences if model adds them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip().rstrip("`").strip()

        insights = json.loads(raw)

        # Validate structure
        if "stocks" not in insights:
            insights["stocks"] = []
        if "market_sentiment" not in insights:
            insights["market_sentiment"] = "neutral"

        return insights

    except json.JSONDecodeError as e:
        print(f"   ⚠️ AI response parse error: {e}")
        print(f"   Raw (first 500): {raw[:500] if 'raw' in locals() else 'N/A'}")
        return {"stocks": [], "market_sentiment": "neutral",
                "market_summary": "Running on technical signals — AI analysis will resume shortly.",
                "ai_powered": False}
    except Exception as e:
        err_str = str(e).lower()
        print(f"   ⚠️ Gemini API error: {e}")

        # Quota / rate limit — daily free tier exhausted
        if any(k in err_str for k in ["quota", "resource_exhausted", "resourceexhausted",
                                       "429", "rate", "limit"]):
            # Gemini free tier resets at midnight Pacific = 1:30 PM IST next day
            from datetime import datetime, timezone, timedelta
            import pytz
            ist = pytz.timezone("Asia/Kolkata")
            now_ist = datetime.now(ist)
            # Next midnight Pacific = next midnight UTC-8
            pacific = pytz.timezone("US/Pacific")
            now_pac = datetime.now(pacific)
            next_midnight_pac = (now_pac + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0)
            reset_ist = next_midnight_pac.astimezone(ist)
            reset_str = reset_ist.strftime("%-I:%M %p IST")

            print(f"   ℹ️ Gemini daily quota exhausted. Resets at {reset_str}")
            return {
                "stocks": [],
                "market_sentiment": "neutral",
                "market_summary": f"Technical analysis mode — AI quota resets at {reset_str}.",
                "ai_powered": False,
                "quota_exhausted": True,
            }

        return {"stocks": [], "market_sentiment": "neutral",
                "market_summary": "Running on technical signals only.",
                "ai_powered": False}
