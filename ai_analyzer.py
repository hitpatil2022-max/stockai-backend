"""
AI Analyzer - Uses Google Gemini (Free API)
Combines news + technicals + FII/DII + bulk deals + insider trades + political intel
Auto-fallback through multiple models if one fails
"""

from google import genai
from google.genai import types
import json
import time
from config import GEMINI_API_KEY
from datetime import datetime

client = genai.Client(api_key=GEMINI_API_KEY)

# Model fallback chain — tries each in order until one works
# If one is quota-exhausted or not found, automatically moves to next
GEMINI_MODELS = [
    "gemini-2.0-flash-lite",       # Most generous free quota, try first
    "gemini-1.5-flash-latest",     # Fallback 1
    "gemini-1.5-flash",            # Fallback 2
    "gemini-2.0-flash",            # Fallback 3
    "gemini-1.5-flash-8b",         # Fallback 4 — smallest/fastest model
]

PROMPT_INSTRUCTIONS = """
Analyze ALL the data above together — news, technicals, FII/DII flows, bulk deals, insider trades, and political/business intelligence.

IMPORTANT — Find hidden connections:
- If a politician is linked to a company, factor that into confidence
- If FII is selling but insiders are buying, flag this conflict
- If bulk deal buyer matches a known operator pattern, increase signal strength
- If indirect sector policy affects a stock not in the news, still flag it
- Cross-reference all data sources to find non-obvious opportunities

Respond in valid JSON only. No markdown. No text outside JSON.

JSON structure:
{
  "market_sentiment": "bullish/bearish/neutral",
  "market_summary": "1-2 sentences",
  "fii_dii_impact": "1 sentence on what FII/DII data means for market",
  "top_opportunity": "SYMBOL: one line reason including any hidden connections",
  "risks_to_watch": ["risk1", "risk2", "risk3"],
  "hidden_connections": [
    {
      "connection": "brief description of indirect link found",
      "affected_stocks": ["SYM1", "SYM2"],
      "impact": "bullish/bearish",
      "confidence": 70
    }
  ],
  "stocks": [
    {
      "symbol": "SYMBOL",
      "action": "BUY/SELL/HOLD/WATCH",
      "confidence": 75,
      "reason": "one sentence including any political/insider angle",
      "time_horizon": "swing",
      "target_price": 1000,
      "stop_loss": 950,
      "risk_level": "MEDIUM",
      "signal_sources": ["technical", "fii_buying", "insider_buy", "political"]
    }
  ]
}
"""

def build_prompt(date, news_text, tech_text, political_text, intel_text):
    return (
        "You are an expert Indian stock market analyst with deep knowledge of "
        "political-business nexus, institutional flows, and insider activity.\n"
        "Market: NSE/BSE India | Date: " + date + "\n\n"
        "=== KEY NEWS ===\n" + news_text + "\n\n"
        "=== TECHNICAL SIGNALS (strongest) ===\n" + tech_text + "\n\n"
        "=== POLITICAL & BUSINESS INTELLIGENCE ===\n" + political_text + "\n\n"
        "=== FII/DII + BULK DEALS + INSIDER TRADES ===\n" + intel_text + "\n"
        + PROMPT_INSTRUCTIONS
    )

def try_model(model_name, prompt):
    """Try a single model — returns (success, result_or_error)"""
    try:
        response = client.models.generate_content(
            model=model_name,
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
                raw = raw[4:]
        raw = raw.strip()
        insights = json.loads(raw)
        return True, insights

    except json.JSONDecodeError as e:
        # Response came back but wasn't valid JSON — skip to next model
        return False, "json_error: " + str(e)
    except Exception as e:
        return False, str(e)

def analyze_with_ai(news_items, stock_data, tech_signals, political_findings=None, market_intel=None):
    """Send enriched data to Gemini with automatic model fallback"""

    from political_analyzer import format_for_ai as format_political
    from market_intelligence import format_for_ai as format_intel

    # Top 8 news — compact
    news_lines = []
    for item in news_items[:8]:
        stocks = ", ".join(item.get("mentioned_stocks", ["None"])[:3])
        news_lines.append("- " + item["title"][:120] + " [" + stocks + "]")
    news_text = "\n".join(news_lines)

    # Top 10 strongest technical signals
    sorted_signals = sorted(
        tech_signals.items(),
        key=lambda x: abs(x[1].get("technical_score", 50) - 50),
        reverse=True
    )
    tech_lines = []
    for symbol, data in sorted_signals[:10]:
        stock = stock_data.get(symbol, {})
        tech_lines.append(
            symbol.replace(".NS", "") + ":"
            + " P=" + str(stock.get("current_price", "N/A"))
            + " Chg=" + str(stock.get("change_pct", "N/A")) + "%"
            + " RSI=" + str(data.get("rsi", "N/A"))
            + " MACD=" + str(data.get("macd", {}).get("trend", "N/A"))
            + " Score=" + str(data.get("technical_score", "N/A"))
        )
    tech_text = "\n".join(tech_lines)

    political_text = format_political(political_findings or [])
    intel_text     = format_intel(market_intel or {})
    date           = datetime.now().strftime("%Y-%m-%d %H:%M IST")
    prompt         = build_prompt(date, news_text, tech_text, political_text, intel_text)

    # Try each model in fallback chain
    for model in GEMINI_MODELS:
        print("   Trying model: " + model + "...")
        success, result = try_model(model, prompt)

        if success:
            print("   AI analysis complete using " + model
                  + " | Stocks: " + str(len(result.get("stocks", [])))
                  + " | Hidden connections: " + str(len(result.get("hidden_connections", []))))
            return result

        err = str(result)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            print("   " + model + " quota exhausted — trying next model...")
            continue
        elif "404" in err or "NOT_FOUND" in err:
            print("   " + model + " not available — trying next model...")
            continue
        elif "json_error" in err:
            print("   " + model + " returned invalid JSON — trying next model...")
            continue
        else:
            print("   " + model + " error: " + err + " — trying next model...")
            continue

    # All models failed
    print("   Warning: All Gemini models failed. Using technical-only signals.")
    return {
        "stocks":             [],
        "market_sentiment":   "neutral",
        "market_summary":     "AI unavailable — technical signals only",
        "hidden_connections": [],
        "fii_dii_impact":     "",
        "risks_to_watch":     [],
        "top_opportunity":    ""
    }
