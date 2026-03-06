"""
🤖 AI Analyzer - Google Gemini (Free Tier, Single Model)
ONE call per cycle. No fallback chain. Fits within 20 RPD free tier limit.

Free tier limits for gemini-2.5-flash:
  RPM = 5   (requests per minute)
  RPD = 20  (requests per day)
  
With 90-min cycles = 16 calls/day → safely under 20 RPD ✅
"""

from google import genai
from google.genai import types
import json
from config import GEMINI_API_KEY
from datetime import datetime

client = genai.Client(api_key=GEMINI_API_KEY)

# ── ONLY model confirmed working on free tier ─────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"

# Compact prompt — fewer tokens = faster + cheaper on quota
ANALYSIS_PROMPT = """\
You are an expert Indian stock market analyst. Today: {date}

NEWS (top 10):
{news}

TECHNICAL DATA:
{technicals}

FII/DII: {fii_dii}
POLITICAL: {political}
BULK/INSIDER: {market_intel}

Analyze all data. Return ONLY valid JSON, no markdown, no explanation.
Include stocks from news OR with tech_score>65. Max 12 stocks. Reasons under 15 words.

{{"market_sentiment":"bullish/bearish/neutral","market_summary":"2 sentences","top_opportunity":"SYMBOL: reason","risks_to_watch":["r1","r2","r3"],"stocks":[{{"symbol":"RELIANCE","action":"BUY","confidence":82,"reason":"Short reason","time_horizon":"swing","target_price":2850,"stop_loss":2700,"risk_level":"MEDIUM","impact_factors":["f1","f2"],"signal_sources":["technical","fii_buying"]}}]}}"""


def _call_gemini(prompt):
    """Single model call — no fallback chain to preserve RPD quota."""
    try:
        print(f"     Calling {GEMINI_MODEL}...")
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=1500,
            )
        )
        raw = response.text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:].strip()
        result = json.loads(raw)
        print(f"     ✅ Gemini succeeded")
        return result

    except Exception as e:
        err = str(e).lower()
        if "429" in err or "quota" in err or "resource_exhausted" in err:
            print(f"     ⚠️  Gemini quota exhausted for today. Technical-only mode active.")
        elif "404" in err or "not found" in err:
            print(f"     ⚠️  Model {GEMINI_MODEL} not found. Check API key project.")
        else:
            print(f"     ⚠️  Gemini error: {e}")
        return None


def analyze_with_full_intelligence(news_items, stock_data, tech_signals,
                                   political_findings=None, market_intel=None):
    """Full analysis — all intel sources combined into ONE Gemini call."""

    # News (top 10, compact)
    news_text = "\n".join([
        f"- [{item['source']}] {item['title'][:80]} | stocks:{','.join(item.get('mentioned_stocks',[])[:3])} | score:{item.get('importance_score',5)}"
        for item in news_items[:10]
    ])

    # Technicals (top 15, compact)
    tech_text = "\n".join([
        f"- {sym.replace('.NS','')}: ₹{data.get('current_price','?')} rsi={data.get('rsi','?')}({data.get('rsi_signal','')}) macd={data.get('macd',{}).get('trend','?')} score={data.get('technical_score','?')}/100 vol={data.get('volume_spike',1)}x"
        for sym, data in list(tech_signals.items())[:15]
    ])

    # FII/DII one-liner
    fii_dii_text = "No data"
    if market_intel and market_intel.get("fii_dii"):
        fd = market_intel["fii_dii"]
        fii = fd.get("fii", {})
        dii = fd.get("dii", {})
        fii_dii_text = (
            f"FII:{fii.get('action','?')} ₹{fii.get('net_cr',0)}Cr | "
            f"DII:{dii.get('action','?')} ₹{dii.get('net_cr',0)}Cr | "
            f"Sentiment:{fd.get('sentiment','?')}"
        )

    # Political (top 3)
    pol_text = "None"
    if political_findings:
        pol_text = " | ".join([
            f"{p.get('figures_mentioned',[('?','?')])[0][1] if p.get('figures_mentioned') else 'sector'}→{','.join(p.get('potentially_affected_stocks',[])[:3])}"
            for p in political_findings[:3]
        ])

    # Bulk + insider (top 3 each)
    intel_text = "None"
    if market_intel:
        bulk    = market_intel.get("bulk_deals", [])
        insider = market_intel.get("insider_trades", [])
        parts   = []
        for d in bulk[:3]:
            parts.append(f"Bulk:{d.get('symbol','?')} {d.get('action','?')} by {str(d.get('client','?'))[:20]}")
        for t in insider[:3]:
            parts.append(f"Insider:{t.get('symbol','?')} {t.get('action','?')} by {str(t.get('insider','?'))[:20]}")
        intel_text = " | ".join(parts) if parts else "None"

    prompt = ANALYSIS_PROMPT.format(
        date=datetime.now().strftime("%Y-%m-%d %H:%M IST"),
        news=news_text,
        technicals=tech_text,
        fii_dii=fii_dii_text,
        political=pol_text,
        market_intel=intel_text,
    )

    result = _call_gemini(prompt)
    if result:
        return result

    return {
        "stocks": [],
        "market_sentiment": "neutral",
        "market_summary": "AI quota exhausted — showing technical signals only. Resets midnight Pacific (1:30 PM IST).",
        "top_opportunity": "",
        "risks_to_watch": [],
    }


# Keep backward-compatible alias
def analyze_with_ai(news_items, stock_data, tech_signals):
    return analyze_with_full_intelligence(news_items, stock_data, tech_signals)
