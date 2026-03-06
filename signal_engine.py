"""
⚡ Signal Engine - Combines AI + Technical analysis for final signals
Fixed: technical-only mode now generates visible signals even without AI
"""

from datetime import datetime
from config import ALERT_CONFIDENCE_THRESHOLD

# When AI is available, require 75% confidence
# When technical-only, use 62% — AI normally boosts scores so raw tech needs lower bar
TECH_ONLY_THRESHOLD = 62

def generate_signals(ai_insights, tech_signals, stock_data):
    """
    Combine AI + technical signals into final recommendations.
    
    With AI:    confidence = (AI × 60%) + (technical × 40%)  → threshold 75%
    Without AI: confidence = technical score directly          → threshold 62%
    """

    final_signals = []
    ai_stocks     = {s["symbol"]: s for s in ai_insights.get("stocks", [])}
    ai_available  = bool(ai_stocks)

    for symbol_full, tech in tech_signals.items():
        symbol    = symbol_full.replace(".NS", "").replace("^", "")
        stock     = stock_data.get(symbol_full, {})
        ai        = ai_stocks.get(symbol)
        tech_score = tech.get("technical_score", 50)

        # ── Confidence calculation ──────────────────────────────────────────
        if ai:
            # Full AI + technical blend
            combined_confidence = round((ai["confidence"] * 0.6) + (tech_score * 0.4))
        else:
            # Technical-only: use raw score but apply a soft boost
            # RSI, MACD and volume together — if all agree, score is reliable
            rsi        = tech.get("rsi", 50)
            rsi_signal = tech.get("rsi_signal", "neutral")
            macd_trend = tech.get("macd", {}).get("trend", "neutral")
            vol_spike  = tech.get("volume_spike", 1)

            # Boost score if multiple indicators agree
            alignment_bonus = 0
            if rsi_signal == "oversold" and macd_trend == "bullish":
                alignment_bonus = 8
            elif rsi_signal == "overbought" and macd_trend == "bearish":
                alignment_bonus = 8
            elif (rsi_signal in ("oversold","bullish")) and macd_trend == "bullish":
                alignment_bonus = 5
            elif (rsi_signal in ("overbought","bearish")) and macd_trend == "bearish":
                alignment_bonus = 5

            if vol_spike >= 2:
                alignment_bonus += 4   # High volume confirms the move

            combined_confidence = min(85, tech_score + alignment_bonus)

        # ── Action ─────────────────────────────────────────────────────────
        if ai:
            action = ai["action"]
        else:
            rsi_signal = tech.get("rsi_signal", "neutral")
            macd_trend = tech.get("macd", {}).get("trend", "neutral")
            if tech_score >= 70 or rsi_signal == "oversold":
                action = "BUY"
            elif tech_score <= 32 or rsi_signal == "overbought":
                action = "SELL"
            elif tech_score >= 58:
                action = "WATCH"
            else:
                action = "HOLD"

        # ── Threshold filter ────────────────────────────────────────────────
        threshold = ALERT_CONFIDENCE_THRESHOLD if ai_available else TECH_ONLY_THRESHOLD
        if combined_confidence < threshold:
            continue

        # ── Build reason ────────────────────────────────────────────────────
        if ai:
            reason = ai.get("reason", f"Technical score: {tech_score}/100")
        else:
            rsi    = tech.get("rsi", "N/A")
            macd   = tech.get("macd", {}).get("trend", "N/A")
            trend  = tech.get("trend", "N/A")
            vol    = tech.get("volume_spike", 1)
            reason = (
                f"Technical analysis: RSI {rsi} ({tech.get('rsi_signal','')}) · "
                f"MACD {macd} · Trend {trend} · Volume spike {vol}x · "
                f"Score {tech_score}/100"
            )

        signal = {
            "symbol":        symbol,
            "full_symbol":   symbol_full,
            "name":          stock.get("name", symbol),
            "current_price": stock.get("current_price", 0),
            "change_pct":    stock.get("change_pct", 0),
            "action":        action,
            "confidence":    combined_confidence,
            "time_horizon":  ai.get("time_horizon", "swing") if ai else "swing",
            "target_price":  ai.get("target_price") if ai else calculate_target(stock, tech, action),
            "stop_loss":     ai.get("stop_loss") if ai else calculate_stop_loss(stock, tech, action),
            "risk_level":    ai.get("risk_level", "MEDIUM") if ai else assess_risk(tech),
            "reason":        reason,
            "impact_factors":  ai.get("impact_factors", []) if ai else [],
            "signal_sources":  ai.get("signal_sources", ["technical"]) if ai else ["technical"],
            "technical": {
                "rsi":           tech.get("rsi"),
                "rsi_signal":    tech.get("rsi_signal"),
                "macd_trend":    tech.get("macd", {}).get("trend"),
                "volume_spike":  tech.get("volume_spike"),
                "technical_score": tech_score,
                "trend":         tech.get("trend"),
            },
            "ai_powered":  bool(ai),
            "timestamp":   datetime.now().isoformat(),
            "is_strong":   combined_confidence >= ALERT_CONFIDENCE_THRESHOLD,
        }
        final_signals.append(signal)

    # Sort by confidence
    final_signals.sort(key=lambda x: x["confidence"], reverse=True)

    # Market summary card
    meta = {
        "symbol":          "MARKET",
        "action":          ai_insights.get("market_sentiment", "neutral").upper(),
        "confidence":      100,
        "reason":          ai_insights.get("market_summary", "Technical-only mode — AI quota exhausted, resets at midnight IST"),
        "top_opportunity": ai_insights.get("top_opportunity", ""),
        "risks":           ai_insights.get("risks_to_watch", []),
        "hidden_connections": ai_insights.get("hidden_connections", []),
        "fii_dii_impact":  ai_insights.get("fii_dii_impact", ""),
        "ai_powered":      bool(ai_stocks),
        "timestamp":       datetime.now().isoformat(),
        "is_market_summary": True,
    }
    final_signals.insert(0, meta)

    return final_signals


def calculate_target(stock, tech, action):
    price = stock.get("current_price", 0)
    if not price:
        return None
    sr = tech.get("support_resistance", {})
    if action in ("BUY", "WATCH"):
        resistance = sr.get("resistance", price * 1.05)
        return round(min(resistance, price * 1.08), 2)
    elif action == "SELL":
        support = sr.get("support", price * 0.95)
        return round(max(support, price * 0.93), 2)
    return None


def calculate_stop_loss(stock, tech, action):
    price = stock.get("current_price", 0)
    if not price:
        return None
    if action in ("BUY", "WATCH"):
        return round(price * 0.97, 2)   # 3% stop loss
    elif action == "SELL":
        return round(price * 1.03, 2)   # 3% stop loss on short
    return None


def assess_risk(tech):
    score      = tech.get("technical_score", 50)
    vol_spike  = tech.get("volume_spike", 1)
    if vol_spike > 3 or abs(score - 50) > 30:
        return "HIGH"
    elif abs(score - 50) > 15:
        return "MEDIUM"
    return "LOW"
