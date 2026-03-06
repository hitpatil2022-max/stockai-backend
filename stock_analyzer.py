"""
📊 Stock Data & Technical Analysis
Fetches Nifty 50 + Next 50 (100 stocks) efficiently using yfinance batch download
Calculates RSI, MACD, Bollinger Bands, Volume analysis
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config import (HISTORY_DAYS, RSI_OVERSOLD, RSI_OVERBOUGHT,
                    VOLUME_SPIKE_MULTIPLIER, NIFTY_50, NIFTY_NEXT_50, INDEXES)

# ── Batch download — fetches all stocks in ONE network call ───────────────────
def get_stock_data(symbols):
    """
    Fetch OHLCV data for all symbols using yfinance batch download.
    Much faster than fetching one by one (1 network call vs 100).
    """
    stock_data = {}

    # Separate tradeable stocks from indexes
    tradeable = [s for s in symbols if not s.startswith("^")]
    indexes   = [s for s in symbols if s.startswith("^")]

    # ── Batch download all stocks at once ─────────────────────────────────────
    print(f"   Batch downloading {len(tradeable)} stocks...")
    try:
        raw = yf.download(
            tickers=tradeable,
            period=f"{HISTORY_DAYS}d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as e:
        print(f"   ⚠️ Batch download failed: {e}. Falling back to individual fetch.")
        raw = None

    for symbol in tradeable:
        try:
            if raw is not None and len(tradeable) > 1:
                # Multi-ticker download returns a MultiIndex DataFrame
                if symbol in raw.columns.get_level_values(0):
                    hist = raw[symbol].dropna(how="all")
                else:
                    hist = pd.DataFrame()
            else:
                # Single stock or fallback
                hist = yf.download(symbol, period=f"{HISTORY_DAYS}d",
                                   interval="1d", progress=False, auto_adjust=True)

            if hist is None or hist.empty or len(hist) < 2:
                continue

            prices  = hist["Close"]
            volumes = hist["Volume"]

            current_price = float(prices.iloc[-1])
            prev_close    = float(prices.iloc[-2])
            change        = current_price - prev_close
            change_pct    = (change / prev_close) * 100 if prev_close else 0

            # Clean name from symbol
            clean = symbol.replace(".NS", "").replace(".BO", "")

            stock_data[symbol] = {
                "symbol":        symbol,
                "name":          clean,           # Will be enriched later if needed
                "current_price": round(current_price, 2),
                "prev_close":    round(prev_close, 2),
                "open":          round(float(hist["Open"].iloc[-1]), 2),
                "high":          round(float(hist["High"].iloc[-1]), 2),
                "low":           round(float(hist["Low"].iloc[-1]), 2),
                "volume":        int(volumes.iloc[-1]),
                "avg_volume":    int(volumes.tail(20).mean()),
                "change":        round(change, 2),
                "change_pct":    round(change_pct, 2),
                "52w_high":      round(float(prices.tail(252).max()), 2),
                "52w_low":       round(float(prices.tail(252).min()), 2),
                "hist":          hist,  # kept for technical analysis below
                "index_group":   _get_index_group(symbol),
            }

        except Exception as e:
            pass  # Skip silently — 100 stocks, a few failures are normal

    # ── Indexes (fetch individually — different structure) ────────────────────
    for symbol in indexes:
        try:
            hist = yf.download(symbol, period="30d", interval="1d",
                               progress=False, auto_adjust=True)
            if hist is None or hist.empty or len(hist) < 2:
                continue
            prices = hist["Close"]
            current = float(prices.iloc[-1])
            prev    = float(prices.iloc[-2])
            stock_data[symbol] = {
                "symbol":        symbol,
                "name":          _index_name(symbol),
                "current_price": round(current, 2),
                "prev_close":    round(prev, 2),
                "change_pct":    round((current - prev) / prev * 100, 2),
                "hist":          hist,
                "is_index":      True,
                "index_group":   "INDEX",
            }
        except Exception:
            pass

    loaded = len([s for s in stock_data if not stock_data[s].get("is_index")])
    print(f"   Successfully loaded {loaded} stocks + {len(indexes)} indexes")
    return stock_data


def _get_index_group(symbol):
    """Tag each stock with which index it belongs to."""
    clean = symbol.replace(".NS", "")
    nifty50_clean = [s.replace(".NS", "") for s in NIFTY_50]
    if clean in nifty50_clean:
        return "NIFTY50"
    return "NIFTY_NEXT50"


def _index_name(symbol):
    names = {"^NSEI": "Nifty 50", "^BSESN": "Sensex", "^NSMIDCP": "Nifty Midcap"}
    return names.get(symbol, symbol)


# ── Technical indicators ───────────────────────────────────────────────────────

def calculate_rsi(prices, period=14):
    delta    = prices.diff()
    gain     = delta.where(delta > 0, 0)
    loss     = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs       = avg_gain / avg_loss
    rsi      = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def calculate_macd(prices):
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
    sma     = prices.rolling(window=period).mean()
    std     = prices.rolling(window=period).std()
    upper   = sma + (std * 2)
    lower   = sma - (std * 2)
    current = float(prices.iloc[-1])
    bw      = float(upper.iloc[-1]) - float(lower.iloc[-1])
    pos     = (current - float(lower.iloc[-1])) / bw if bw > 0 else 0.5
    return {
        "upper":    round(float(upper.iloc[-1]), 2),
        "middle":   round(float(sma.iloc[-1]), 2),
        "lower":    round(float(lower.iloc[-1]), 2),
        "position": round(pos, 3),
    }


def calculate_support_resistance(prices):
    recent = prices.tail(30)
    return {
        "resistance": round(float(recent.max()), 2),
        "support":    round(float(recent.min()), 2),
        "current":    round(float(prices.iloc[-1]), 2),
    }


def calculate_technical_signals(stock_data):
    """Calculate all technical indicators for each stock."""
    signals = {}

    for symbol, data in stock_data.items():
        if "hist" not in data or data.get("is_index"):
            continue

        hist    = data["hist"]
        prices  = hist["Close"].astype(float)
        volumes = hist["Volume"].astype(float)

        if len(prices) < 26:   # Need at least 26 days for MACD
            continue

        try:
            rsi  = calculate_rsi(prices)
            macd = calculate_macd(prices)
            bb   = calculate_bollinger_bands(prices)
            sr   = calculate_support_resistance(prices)

            current_vol = float(volumes.iloc[-1])
            avg_vol     = float(volumes.tail(20).mean())
            vol_spike   = round(current_vol / avg_vol, 2) if avg_vol > 0 else 1.0

            ma20  = round(float(prices.rolling(20).mean().iloc[-1]), 2)
            ma50  = round(float(prices.rolling(50).mean().iloc[-1]), 2) if len(prices) >= 50 else None
            ma200 = round(float(prices.rolling(200).mean().iloc[-1]), 2) if len(prices) >= 200 else None
            price = float(prices.iloc[-1])

            # ── Technical score (0–100) ───────────────────────────────────────
            score = 50

            # RSI
            if rsi < RSI_OVERSOLD:
                score += 20       # Oversold → bullish
            elif rsi < 40:
                score += 10
            elif rsi > RSI_OVERBOUGHT:
                score -= 20       # Overbought → bearish
            elif rsi > 60:
                score -= 10

            # MACD
            score += 10 if macd["trend"] == "bullish" else -10

            # MACD histogram momentum (is it accelerating?)
            if abs(macd["histogram"]) > 0:
                score += 5 if macd["histogram"] > 0 else -5

            # Bollinger position
            if bb["position"] < 0.2:
                score += 10   # Near lower band → potential bounce
            elif bb["position"] > 0.8:
                score -= 10   # Near upper band → potential pullback

            # MA trend
            if ma50 and price > ma50:
                score += 8
            elif ma50 and price < ma50:
                score -= 8

            if ma200 and price > ma200:
                score += 7    # Long-term uptrend
            elif ma200 and price < ma200:
                score -= 7

            # Volume confirms signal
            if vol_spike >= VOLUME_SPIKE_MULTIPLIER:
                score = score + 6 if score > 50 else score - 6

            # Near 52-week high/low
            w52h = data.get("52w_high")
            w52l = data.get("52w_low")
            if w52h and w52l and (w52h - w52l) > 0:
                pct_from_high = (w52h - price) / w52h
                if pct_from_high < 0.03:
                    score += 5   # Breaking out near 52-week high

            signals[symbol] = {
                "rsi":              rsi,
                "rsi_signal":       ("oversold"  if rsi < RSI_OVERSOLD else
                                     "overbought" if rsi > RSI_OVERBOUGHT else "neutral"),
                "macd":             macd,
                "bollinger":        bb,
                "support_resistance": sr,
                "ma20":             ma20,
                "ma50":             ma50,
                "ma200":            ma200,
                "volume_spike":     vol_spike,
                "technical_score":  min(100, max(0, round(score))),
                "trend":            ("bullish" if score > 60 else
                                     "bearish" if score < 40 else "sideways"),
                "current_price":    price,
                "index_group":      data.get("index_group", "NIFTY50"),
            }

        except Exception as e:
            pass   # Skip silently

    print(f"   Technical indicators calculated for {len(signals)} stocks")
    return signals
