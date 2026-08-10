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


# ── Multi-timeframe resampling ──────────────────────────────────────────────
def resample_ohlc(hist, rule):
    """Resample daily OHLCV to weekly ('W-FRI') or monthly ('ME') bars."""
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in hist.columns:
        agg["Volume"] = "sum"
    out = hist.resample(rule).agg(agg).dropna(how="any")
    return out


def _macd_histogram_series(prices):
    """Full MACD histogram series (not just latest value) — needed to check if it's rising."""
    ema12  = prices.ewm(span=12, adjust=False).mean()
    ema26  = prices.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd - signal


# ── ADX / +DI / -DI (Wilder's smoothing) ────────────────────────────────────
def calculate_adx(hist, period=14):
    """
    Average Directional Index — measures trend STRENGTH (not direction).
    +DI > -DI means the trend is up; ADX > 20-25 means that trend has real conviction
    (vs. sideways chop). Used by the Chartink-style screener to filter out weak/choppy setups.
    """
    high, low, close = hist["High"].astype(float), hist["Low"].astype(float), hist["Close"].astype(float)

    up_move   = high.diff()
    down_move = -low.diff()
    plus_dm   = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm  = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)

    atr       = tr.ewm(alpha=1/period, adjust=False).mean()
    plus_di   = 100 * pd.Series(plus_dm, index=hist.index).ewm(alpha=1/period, adjust=False).mean() / atr
    minus_di  = 100 * pd.Series(minus_dm, index=hist.index).ewm(alpha=1/period, adjust=False).mean() / atr
    dx        = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx       = dx.ewm(alpha=1/period, adjust=False).mean()

    if len(adx) == 0 or pd.isna(adx.iloc[-1]):
        return None
    return {
        "adx":      round(float(adx.iloc[-1]), 2),
        "plus_di":  round(float(plus_di.iloc[-1]), 2),
        "minus_di": round(float(minus_di.iloc[-1]), 2),
        "trending": bool(adx.iloc[-1] > 20 and plus_di.iloc[-1] > minus_di.iloc[-1]),
    }


# ── Multi-timeframe trend alignment (Chartink-style screener) ──────────────
def calculate_mtf_alignment(hist):
    """
    Reproduces the multi-timeframe screener strategy:
    - Monthly & Weekly MACD histogram > 0 AND rising  → big-picture trend accelerating
    - Daily MACD histogram < 0 but rising              → daily pullback within that uptrend, bottoming
    - Close > SMA(9) on Monthly + Weekly + Daily        → trend confirmed on all three timeframes
    - Daily Low dipped below SMA(9) then closed back above → tested support, bounced (low-risk entry)
    """
    result = {
        "monthly_macd_rising": False, "weekly_macd_rising": False,
        "daily_macd_pullback": False, "mtf_aligned": False, "dip_buy_signal": False,
    }
    try:
        monthly = resample_ohlc(hist, "ME")
        weekly  = resample_ohlc(hist, "W-FRI")
        daily   = hist

        # Monthly MACD histogram rising and positive (need ≥3 bars to check "rising")
        if len(monthly) >= 3:
            mh = _macd_histogram_series(monthly["Close"].astype(float))
            result["monthly_macd_rising"] = bool(mh.iloc[-1] > 0 and mh.iloc[-1] > mh.iloc[-2])
        # Weekly MACD histogram rising and positive
        if len(weekly) >= 3:
            wh = _macd_histogram_series(weekly["Close"].astype(float))
            result["weekly_macd_rising"] = bool(wh.iloc[-1] > 0 and wh.iloc[-1] > wh.iloc[-2])
        # Daily MACD histogram: negative (pullback) but rising (bottoming out)
        if len(daily) >= 3:
            dh = _macd_histogram_series(daily["Close"].astype(float))
            result["daily_macd_pullback"] = bool(dh.iloc[-1] < 0 and dh.iloc[-1] > dh.iloc[-2])

        # Close > SMA(9) on all three timeframes
        def _above_sma9(df):
            if len(df) < 9: return False
            c = df["Close"].astype(float)
            return bool(c.iloc[-1] > c.rolling(9).mean().iloc[-1])

        aligned = _above_sma9(monthly) and _above_sma9(weekly) and _above_sma9(daily)
        result["mtf_aligned"] = bool(aligned)

        # Daily low dipped into SMA9 (tested support) but closed back above it
        if len(daily) >= 9:
            c9 = daily["Close"].astype(float).rolling(9).mean().iloc[-1]
            low_today   = float(daily["Low"].iloc[-1])
            close_today = float(daily["Close"].iloc[-1])
            result["dip_buy_signal"] = bool(low_today < c9 <= close_today)

    except Exception:
        pass
    return result


# ── Minervini Trend Template (Mark Minervini — "Trade Like a Stock Market Wizard") ──
def calculate_minervini_criteria(prices, ma50, ma150, ma200, w52h, w52l):
    """
    8-point Stage-2 uptrend checklist used by Mark Minervini (multi-time U.S. Investing
    Champion). A stock passing most/all of these is textbook "institutional accumulation,
    strong uptrend" — the classic setup professional trend-followers look for.
    RS Rating (point 8) is computed separately, relative to this app's own watchlist.
    """
    price = float(prices.iloc[-1])
    criteria = {}
    criteria["c1_above_ma150_200"] = bool(ma150 and ma200 and price > ma150 and price > ma200)
    criteria["c2_ma150_above_ma200"] = bool(ma150 and ma200 and ma150 > ma200)

    # c3: 200-day MA trending up for ≥1 month (~21 trading days)
    if ma200 is not None and len(prices) >= 221:
        ma200_series = prices.rolling(200).mean()
        ma200_prev = ma200_series.iloc[-21]
        criteria["c3_ma200_trending_up"] = bool(pd.notna(ma200_prev) and ma200 > ma200_prev)
    else:
        criteria["c3_ma200_trending_up"] = False

    criteria["c4_ma_stacked"] = bool(ma50 and ma150 and ma200 and ma50 > ma150 > ma200)
    criteria["c5_above_ma50"] = bool(ma50 and price > ma50)
    criteria["c6_above_52w_low_25pct"] = bool(w52l and price >= w52l * 1.25)
    criteria["c7_within_25pct_of_52w_high"] = bool(w52h and price >= w52h * 0.75)

    passed = sum(1 for v in criteria.values() if v)
    criteria["criteria_passed"] = passed
    criteria["criteria_total"]  = 7   # RS rating (8th) added separately once known
    return criteria


def _rs_raw_score(prices):
    """
    Approximation of IBD's Relative Strength formula: heavier weight on the most
    recent quarter. Ranked into a percentile (0-100) across this app's watchlist below.
    """
    try:
        p_now = float(prices.iloc[-1])
        def _ret(n):
            if len(prices) <= n: return None
            p_then = float(prices.iloc[-n])
            return p_now / p_then if p_then > 0 else None
        r3, r6, r9, r12 = _ret(63), _ret(126), _ret(189), _ret(252)
        parts = [(r3, 0.4), (r6, 0.2), (r9, 0.2), (r12, 0.2)]
        valid = [(r, w) for r, w in parts if r is not None]
        if not valid:
            return None
        wsum = sum(w for _, w in valid)
        return sum(r * w for r, w in valid) / wsum
    except Exception:
        return None


def calculate_technical_signals(stock_data):
    """Calculate all technical indicators for each stock."""
    signals = {}
    rs_raw_scores = {}   # symbol -> raw RS score, for cross-sectional percentile ranking below

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
            ma150 = round(float(prices.rolling(150).mean().iloc[-1]), 2) if len(prices) >= 150 else None
            ma200 = round(float(prices.rolling(200).mean().iloc[-1]), 2) if len(prices) >= 200 else None
            price = float(prices.iloc[-1])

            w52h = data.get("52w_high")
            w52l = data.get("52w_low")

            # ── New: multi-timeframe alignment + ADX + Minervini template ──────
            mtf     = calculate_mtf_alignment(hist)
            adx     = calculate_adx(hist)
            mine    = calculate_minervini_criteria(prices, ma50, ma150, ma200, w52h, w52l)
            rs_raw  = _rs_raw_score(prices)
            if rs_raw is not None:
                rs_raw_scores[symbol] = rs_raw

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
            if w52h and w52l and (w52h - w52l) > 0:
                pct_from_high = (w52h - price) / w52h
                if pct_from_high < 0.03:
                    score += 5   # Breaking out near 52-week high

            # ── New: multi-timeframe alignment bonus (Chartink-style screener) ─
            if mtf["monthly_macd_rising"]:
                score += 8
            if mtf["weekly_macd_rising"]:
                score += 6
            if mtf["daily_macd_pullback"]:
                score += 6     # daily pullback bottoming within a larger uptrend
            if mtf["mtf_aligned"]:
                score += 8     # trend confirmed on monthly + weekly + daily simultaneously
            if mtf["dip_buy_signal"]:
                score += 5     # tested SMA9 support intraday and closed back above it

            # ── New: ADX trend-strength confirmation ────────────────────────────
            if adx and adx["trending"]:
                score += 7      # real directional strength, not just sideways chop

            # ── New: Minervini Trend Template — partial credit per criterion ───
            score += mine["criteria_passed"] * 1.5

            signals[symbol] = {
                "rsi":              rsi,
                "rsi_signal":       ("oversold"  if rsi < RSI_OVERSOLD else
                                     "overbought" if rsi > RSI_OVERBOUGHT else "neutral"),
                "macd":             macd,
                "bollinger":        bb,
                "support_resistance": sr,
                "ma20":             ma20,
                "ma50":             ma50,
                "ma150":            ma150,
                "ma200":            ma200,
                "volume_spike":     vol_spike,
                "technical_score":  min(100, max(0, round(score))),
                "trend":            ("bullish" if score > 60 else
                                     "bearish" if score < 40 else "sideways"),
                "current_price":    price,
                "index_group":      data.get("index_group", "NIFTY50"),
                "mtf_alignment":    mtf,
                "adx":              adx,
                "minervini":        mine,   # rs_rating filled in below, once the full universe is scored
            }

        except Exception as e:
            pass   # Skip silently

    # ── Cross-sectional RS Rating: percentile rank each stock's raw RS score
    #    against every other stock in THIS watchlist (proxy for IBD's market-wide rating,
    #    scoped to this app's own universe — labelled as such, not oversold as literal IBD data) ──
    if rs_raw_scores:
        ranks = pd.Series(rs_raw_scores).rank(pct=True) * 100
        for symbol, rs_rating in ranks.items():
            if symbol in signals:
                signals[symbol]["minervini"]["rs_rating"] = round(float(rs_rating))
                signals[symbol]["minervini"]["c8_rs_rating_70plus"] = bool(rs_rating >= 70)
                if rs_rating >= 70:
                    signals[symbol]["minervini"]["criteria_passed"] += 1
                    signals[symbol]["minervini"]["criteria_total"] = 8
                    signals[symbol]["technical_score"] = min(100, signals[symbol]["technical_score"] + 2)
                else:
                    signals[symbol]["minervini"]["criteria_total"] = 8

    print(f"   Technical indicators calculated for {len(signals)} stocks")
    return signals
