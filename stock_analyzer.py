"""
Stock Data & Technical Analysis
Uses yfinance (free) to get NSE/BSE data
Calculates RSI, MACD, Bollinger Bands, Volume analysis
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config import HISTORY_DAYS, RSI_OVERSOLD, RSI_OVERBOUGHT, VOLUME_SPIKE_MULTIPLIER

# Symbols that are known to have changed or be unavailable on yfinance
# Key = old symbol, Value = new/correct symbol (or None to skip)
SYMBOL_OVERRIDES = {
    "TATAMOTORS.NS": "TATAMOTORS.NS",   # Sometimes has yfinance issues, keep retrying
    "BAJAJ-AUTO.NS": "BAJAJ-AUTO.NS",   # Hyphen symbols can cause issues
}

def get_stock_data(symbols):
    """Fetch current + historical data for all symbols"""
    stock_data = {}

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)

            # Get historical data
            hist = ticker.history(period=f"{HISTORY_DAYS}d", interval="1d")

            if hist.empty or len(hist) < 5:
                print(f"   Skipping {symbol}: insufficient data")
                continue

            # Current price info
            try:
                info = ticker.info
            except Exception:
                info = {}  # info() can fail even when history works — handle gracefully

            current_price = round(float(hist["Close"].iloc[-1]), 2)
            prev_close    = round(float(hist["Close"].iloc[-2]), 2) if len(hist) > 1 else current_price

            stock_data[symbol] = {
                "symbol":       symbol,
                "name":         info.get("longName", symbol.replace(".NS", "")),
                "current_price": current_price,
                "prev_close":   prev_close,
                "open":         round(float(hist["Open"].iloc[-1]), 2),
                "high":         round(float(hist["High"].iloc[-1]), 2),
                "low":          round(float(hist["Low"].iloc[-1]), 2),
                "volume":       int(hist["Volume"].iloc[-1]),
                "avg_volume":   int(hist["Volume"].tail(20).mean()),
                "market_cap":   info.get("marketCap", 0),
                "sector":       info.get("sector", "Unknown"),
                "pe_ratio":     info.get("trailingPE", None),
                "52w_high":     info.get("fiftyTwoWeekHigh", None),
                "52w_low":      info.get("fiftyTwoWeekLow", None),
                "hist":         hist,
            }

            # Daily change
            change     = current_price - prev_close
            change_pct = (change / prev_close) * 100 if prev_close else 0
            stock_data[symbol]["change"]     = round(change, 2)
            stock_data[symbol]["change_pct"] = round(change_pct, 2)

        except Exception as e:
            print(f"   Skipping {symbol}: {e}")

    print(f"   Successfully loaded {len(stock_data)} stocks")
    return stock_data

def calculate_rsi(prices, period=14):
    """Calculate RSI indicator"""
    delta    = prices.diff()
    gain     = delta.where(delta > 0, 0)
    loss     = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs       = avg_gain / avg_loss
    rsi      = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)

def calculate_macd(prices):
    """Calculate MACD indicator"""
    ema12     = prices.ewm(span=12, adjust=False).mean()
    ema26     = prices.ewm(span=26, adjust=False).mean()
    macd      = ema12 - ema26
    signal    = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal
    return {
        "macd":      round(float(macd.iloc[-1]), 4),
        "signal":    round(float(signal.iloc[-1]), 4),
        "histogram": round(float(histogram.iloc[-1]), 4),
        "trend":     "bullish" if macd.iloc[-1] > signal.iloc[-1] else "bearish",
    }

def calculate_bollinger_bands(prices, period=20):
    """Calculate Bollinger Bands"""
    sma        = prices.rolling(window=period).mean()
    std        = prices.rolling(window=period).std()
    upper      = sma + (std * 2)
    lower      = sma - (std * 2)
    current    = float(prices.iloc[-1])
    band_width = float(upper.iloc[-1]) - float(lower.iloc[-1])
    position   = (current - float(lower.iloc[-1])) / band_width if band_width > 0 else 0.5
    return {
        "upper":    round(float(upper.iloc[-1]), 2),
        "middle":   round(float(sma.iloc[-1]), 2),
        "lower":    round(float(lower.iloc[-1]), 2),
        "position": round(position, 3),
    }

def calculate_support_resistance(prices):
    """Simple support/resistance levels"""
    recent = prices.tail(30)
    return {
        "resistance": round(float(recent.max()), 2),
        "support":    round(float(recent.min()), 2),
        "current":    round(float(prices.iloc[-1]), 2),
    }

def calculate_technical_signals(stock_data):
    """Calculate all technical indicators for each stock"""
    signals = {}

    for symbol, data in stock_data.items():
        if "hist" not in data:
            continue

        hist    = data["hist"]
        prices  = hist["Close"]
        volumes = hist["Volume"]

        try:
            rsi  = calculate_rsi(prices)
            macd = calculate_macd(prices)
            bb   = calculate_bollinger_bands(prices)
            sr   = calculate_support_resistance(prices)

            # Volume analysis
            current_vol  = float(volumes.iloc[-1])
            avg_vol      = float(volumes.tail(20).mean())
            volume_spike = round(current_vol / avg_vol, 2) if avg_vol > 0 else 1.0

            # Moving averages
            ma20          = round(float(prices.rolling(20).mean().iloc[-1]), 2)
            ma50          = round(float(prices.rolling(50).mean().iloc[-1]), 2) if len(prices) >= 50  else None
            ma200         = round(float(prices.rolling(200).mean().iloc[-1]), 2) if len(prices) >= 200 else None
            current_price = float(prices.iloc[-1])

            # Technical score (0-100)
            score = 50

            if rsi < RSI_OVERSOLD:
                score += 20
            elif rsi > RSI_OVERBOUGHT:
                score -= 20

            if macd["trend"] == "bullish":
                score += 10
            else:
                score -= 10

            if bb["position"] < 0.2:
                score += 10
            elif bb["position"] > 0.8:
                score -= 10

            if ma50 and current_price > ma50:
                score += 10

            if volume_spike >= VOLUME_SPIKE_MULTIPLIER:
                score = score + 5 if score > 50 else score - 5

            signals[symbol] = {
                "rsi":              rsi,
                "rsi_signal":       "oversold" if rsi < RSI_OVERSOLD else "overbought" if rsi > RSI_OVERBOUGHT else "neutral",
                "macd":             macd,
                "bollinger":        bb,
                "support_resistance": sr,
                "ma20":             ma20,
                "ma50":             ma50,
                "ma200":            ma200,
                "volume_spike":     volume_spike,
                "technical_score":  min(100, max(0, round(score))),
                "trend":            "bullish" if score > 60 else "bearish" if score < 40 else "sideways",
            }

        except Exception as e:
            print(f"   Technical calc skipped for {symbol}: {e}")

    return signals
