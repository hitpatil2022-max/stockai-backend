"""
⚡ Signal Engine - Combines AI + Technical analysis for final signals
Uses multi-factor scoring to determine confidence
"""

from datetime import datetime
from config import ALERT_CONFIDENCE_THRESHOLD

def generate_signals(ai_insights, tech_signals, stock_data):
    """
    Combine AI analysis + technical signals into final recommendations
    Uses weighted scoring: AI (60%) + Technical (40%)
    """
    
    final_signals = []
    
    # Get AI stock recommendations
    ai_stocks = {s["symbol"]: s for s in ai_insights.get("stocks", [])}
    
    # Process all stocks with technical data
    for symbol_full, tech in tech_signals.items():
        symbol = symbol_full.replace(".NS", "").replace("^", "")
        stock = stock_data.get(symbol_full, {})
        
        # Get AI insight if available
        ai = ai_stocks.get(symbol, None)
        
        # Calculate combined confidence
        tech_score = tech.get("technical_score", 50)
        ai_confidence = ai.get("confidence", 50) if ai else 50
        
        # Weighted combination
        combined_confidence = round((ai_confidence * 0.6) + (tech_score * 0.4))
        
        # Determine final action
        if ai:
            action = ai["action"]
        else:
            # Fallback to pure technical
            if tech_score >= 70:
                action = "BUY"
            elif tech_score <= 30:
                action = "SELL"
            else:
                action = "HOLD"
        
        # Skip weak signals
        if combined_confidence < 55 and not ai:
            continue
        
        # Build signal
        signal = {
            "symbol": symbol,
            "full_symbol": symbol_full,
            "name": stock.get("name", symbol),
            "current_price": stock.get("current_price", 0),
            "change_pct": stock.get("change_pct", 0),
            "action": action,
            "confidence": combined_confidence,
            "time_horizon": ai.get("time_horizon", "swing") if ai else "swing",
            "target_price": ai.get("target_price") if ai else calculate_target(stock, tech, action),
            "stop_loss": ai.get("stop_loss") if ai else calculate_stop_loss(stock, tech, action),
            "risk_level": ai.get("risk_level", "MEDIUM") if ai else assess_risk(tech),
            "reason": ai.get("reason", f"Technical score: {tech_score}/100") if ai else f"RSI: {tech.get('rsi')} | MACD: {tech.get('macd', {}).get('trend')}",
            "impact_factors": ai.get("impact_factors", []) if ai else [],
            "technical": {
                "rsi": tech.get("rsi"),
                "rsi_signal": tech.get("rsi_signal"),
                "macd_trend": tech.get("macd", {}).get("trend"),
                "volume_spike": tech.get("volume_spike"),
                "technical_score": tech_score,
                "trend": tech.get("trend"),
            },
            "timestamp": datetime.now().isoformat(),
            "is_strong": combined_confidence >= ALERT_CONFIDENCE_THRESHOLD,
        }
        
        final_signals.append(signal)
    
    # Sort by confidence descending
    final_signals.sort(key=lambda x: x["confidence"], reverse=True)
    
    # Add market context
    if ai_insights:
        meta = {
            "symbol": "MARKET",
            "action": ai_insights.get("market_sentiment", "neutral").upper(),
            "confidence": 100,
            "reason": ai_insights.get("market_summary", ""),
            "top_opportunity": ai_insights.get("top_opportunity", ""),
            "risks": ai_insights.get("risks_to_watch", []),
            "timestamp": datetime.now().isoformat(),
            "is_market_summary": True,
        }
        final_signals.insert(0, meta)
    
    return final_signals

def calculate_target(stock, tech, action):
    """Calculate price target based on technical levels"""
    price = stock.get("current_price", 0)
    if not price:
        return None
    
    sr = tech.get("support_resistance", {})
    if action == "BUY":
        resistance = sr.get("resistance", price * 1.05)
        return round(min(resistance, price * 1.08), 2)  # Max 8% target
    elif action == "SELL":
        support = sr.get("support", price * 0.95)
        return round(max(support, price * 0.93), 2)
    return None

def calculate_stop_loss(stock, tech, action):
    """Calculate stop loss level"""
    price = stock.get("current_price", 0)
    if not price:
        return None
    
    if action == "BUY":
        return round(price * 0.97, 2)  # 3% stop loss
    elif action == "SELL":
        return round(price * 1.03, 2)  # 3% stop loss on short
    return None

def assess_risk(tech):
    """Assess risk level based on technical indicators"""
    score = tech.get("technical_score", 50)
    volume_spike = tech.get("volume_spike", 1)
    
    if volume_spike > 3 or abs(score - 50) > 30:
        return "HIGH"
    elif abs(score - 50) > 15:
        return "MEDIUM"
    return "LOW"
