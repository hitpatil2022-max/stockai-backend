"""
📐 Fundamental Analyzer — P/E vs industry, 3-year growth, ROE/ROCE, debt
Answers: "Is this a genuinely good BUSINESS, not just a good chart?"

Data source: yfinance (.info + income_stmt + balance_sheet) — free, already a
dependency, no new API key needed. Screener.in was evaluated and rejected: its
only official API requires login and supports pre-defined screens alone (no
custom multi-metric queries); everything else is unofficial scraping against
their ToS. yfinance gives us real reported financials to compute an honest
3-year CAGR ourselves, rather than trusting a single pre-baked "growth %" field.

Fundamentals change slowly (a company's ROE doesn't move in 30 minutes the way
its stock price does) — so this is fetched and cached separately from the
price/technical cycle, refreshed once per CACHE_MAX_AGE_HOURS, not every run.
"""

import os
import json
import time
import yfinance as yf

CACHE_FILE = "fundamentals_cache.json"
CACHE_MAX_AGE_HOURS = 24

# "Good" thresholds — commonly used, reasonable defaults for Indian large/mid-cap equities.
# Not magic numbers from a specific book; adjust here if you want stricter/looser screening.
MIN_GROWTH_PCT   = 20    # revenue AND profit CAGR must both clear this, per the ask
MIN_ROE_ROCE_PCT = 15    # either ROE or ROCE clearing this counts as "high"
MAX_DEBT_EQUITY  = 1.0   # D/E below this counts as "low debt"


# ── Disk cache ───────────────────────────────────────────────────────────────
def _load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, default=str)
    except Exception as e:
        print(f"   ⚠️ Could not save fundamentals cache: {e}")


def _is_fresh(entry):
    fetched_at = entry.get("_fetched_at")
    if not fetched_at:
        return False
    return (time.time() - fetched_at) < CACHE_MAX_AGE_HOURS * 3600


# ── CAGR helper ──────────────────────────────────────────────────────────────
def _cagr(start_val, end_val, years):
    """Compound annual growth rate. Returns None if inputs are unusable
    (e.g. company was loss-making in the base year — CAGR isn't meaningful there)."""
    try:
        if start_val is None or end_val is None or years <= 0:
            return None
        if start_val <= 0 or end_val <= 0:
            return None
        return (((end_val / start_val) ** (1 / years)) - 1) * 100
    except Exception:
        return None


# ── Find a row in yfinance's financial statements defensively ───────────────
# yfinance's exact row labels have shifted across versions ("Net Income" vs
# "Net Income Common Stockholders" etc.) — search case-insensitively for any match.
def _find_row(df, candidates):
    if df is None or df.empty:
        return None
    for label in df.index:
        label_l = str(label).lower()
        for cand in candidates:
            if cand.lower() in label_l:
                return df.loc[label]
    return None


def _fetch_one(symbol):
    """Fetch fundamentals for a single symbol. Every field defaults to None on
    failure — mirrors the rest of this codebase's 'skip silently, don't crash
    the whole batch over one bad ticker' philosophy."""
    result = {
        "pe_ratio": None, "sector": None, "industry": None,
        "roe_pct": None, "roce_pct": None, "debt_to_equity": None,
        "profit_margin_pct": None, "market_cap": None,
        "revenue_growth_pct": None,   # repurposed as 3-year revenue CAGR (see module docstring)
        "eps_growth_pct": None,       # repurposed as 3-year profit/net-income CAGR
        "revenue_cagr_3y_pct": None,  # explicit alias, same value, for new code that wants clarity
        "profit_cagr_3y_pct": None,
    }

    try:
        t = yf.Ticker(symbol)
        info = t.info or {}
    except Exception as e:
        print(f"   ⚠️ Fundamentals: {symbol} .info failed: {e}")
        return result

    result["pe_ratio"]          = info.get("trailingPE")
    result["sector"]            = info.get("sector")
    result["industry"]          = info.get("industry")
    result["market_cap"]        = info.get("marketCap")
    result["debt_to_equity"]    = info.get("debtToEquity")
    result["profit_margin_pct"] = (info.get("profitMargins") or 0) * 100 if info.get("profitMargins") is not None else None

    roe = info.get("returnOnEquity")
    result["roe_pct"] = roe * 100 if roe is not None else None

    # yfinance's debtToEquity is often already a percentage (e.g. 45.2 meaning 0.45x) —
    # normalise to a plain ratio so MAX_DEBT_EQUITY comparisons stay consistent.
    if result["debt_to_equity"] is not None and result["debt_to_equity"] > 5:
        result["debt_to_equity"] = result["debt_to_equity"] / 100

    # ── 3-year revenue & profit CAGR from actual annual financial statements ──
    try:
        income = t.income_stmt
        if income is not None and not income.empty:
            revenue_row = _find_row(income, ["Total Revenue", "Operating Revenue"])
            profit_row  = _find_row(income, ["Net Income Common Stockholders", "Net Income", "Net Income Continuous Operations"])

            if revenue_row is not None and len(revenue_row.dropna()) >= 2:
                vals = revenue_row.dropna()
                years = len(vals) - 1   # yfinance columns are annual periods, most-recent first
                rev_cagr = _cagr(float(vals.iloc[-1]), float(vals.iloc[0]), years)
                result["revenue_growth_pct"] = round(rev_cagr, 1) if rev_cagr is not None else None
                result["revenue_cagr_3y_pct"] = result["revenue_growth_pct"]

            if profit_row is not None and len(profit_row.dropna()) >= 2:
                vals = profit_row.dropna()
                years = len(vals) - 1
                profit_cagr = _cagr(float(vals.iloc[-1]), float(vals.iloc[0]), years)
                result["eps_growth_pct"] = round(profit_cagr, 1) if profit_cagr is not None else None
                result["profit_cagr_3y_pct"] = result["eps_growth_pct"]
    except Exception as e:
        print(f"   ⚠️ Fundamentals: {symbol} income_stmt failed: {e}")

    # ── Approximate ROCE = EBIT / (Total Assets − Current Liabilities) ──────
    # "Approximate" because yfinance's free balance sheet doesn't always cleanly
    # separate every line item the way a paid data vendor would — best-effort only.
    try:
        income  = t.income_stmt
        balance = t.balance_sheet
        if income is not None and balance is not None and not income.empty and not balance.empty:
            ebit_row = _find_row(income, ["EBIT", "Operating Income"])
            assets_row = _find_row(balance, ["Total Assets"])
            curr_liab_row = _find_row(balance, ["Current Liabilities", "Total Current Liabilities"])
            if ebit_row is not None and assets_row is not None and curr_liab_row is not None:
                ebit = float(ebit_row.dropna().iloc[0])
                assets = float(assets_row.dropna().iloc[0])
                curr_liab = float(curr_liab_row.dropna().iloc[0])
                capital_employed = assets - curr_liab
                if capital_employed > 0:
                    result["roce_pct"] = round((ebit / capital_employed) * 100, 1)
    except Exception as e:
        print(f"   ⚠️ Fundamentals: {symbol} ROCE calc failed: {e}")

    return result


def get_fundamentals_cached(symbols):
    """
    Main entry point. Returns {symbol: {...fundamentals}} for every symbol,
    fetching fresh data only for symbols whose cache entry is missing or stale
    (>CACHE_MAX_AGE_HOURS old) — fundamentals don't need re-fetching every 30 min
    the way price/technical data does.
    """
    cache = _load_cache()
    fetched_count = 0

    for symbol in symbols:
        if symbol.startswith("^"):   # skip indexes
            continue
        entry = cache.get(symbol)
        if entry and _is_fresh(entry):
            continue
        data = _fetch_one(symbol)
        data["_fetched_at"] = time.time()
        cache[symbol] = data
        fetched_count += 1

    if fetched_count:
        _save_cache(cache)
        print(f"   Fundamentals refreshed for {fetched_count} stocks (cache: {CACHE_FILE})")
    else:
        print(f"   Fundamentals cache still fresh — no refetch needed")

    # Strip internal bookkeeping key before returning
    return {sym: {k: v for k, v in entry.items() if k != "_fetched_at"}
            for sym, entry in cache.items() if sym in symbols}


# ── Peer-group P/E ("industry average", scoped to this watchlist) ──────────
def compute_industry_pe(fundamentals):
    """
    'P/E lower than industry' needs an industry average to compare against.
    We don't have a full-market data feed, so this computes the average P/E
    across this app's own watchlist, grouped by yfinance's 'industry' field
    (falling back to 'sector' if industry is missing) — an honest, watchlist-
    scoped proxy, not a claim of true market-wide industry data.
    """
    groups = {}
    for symbol, f in fundamentals.items():
        pe = f.get("pe_ratio")
        group_key = f.get("industry") or f.get("sector")
        if not group_key or pe is None or pe <= 0 or pe > 500:   # filter obvious data errors
            continue
        groups.setdefault(group_key, []).append(pe)

    industry_avg_pe = {
        group: round(sum(pes) / len(pes), 2)
        for group, pes in groups.items() if len(pes) >= 2   # need ≥2 peers for a meaningful average
    }
    return industry_avg_pe


# ── The 4 quality criteria the person asked for, as explicit pass/fail flags ─
def evaluate_fundamental_quality(f, industry_avg_pe):
    """
    1. P/E lower than industry (peer group within this watchlist)
    2. Revenue AND profit both growing ≥20% CAGR over the last ~3 years
    3. High ROE or ROCE (≥15%)
    4. Low debt (D/E < 1.0)
    """
    group_key = f.get("industry") or f.get("sector")
    ind_pe = industry_avg_pe.get(group_key)
    pe = f.get("pe_ratio")

    crit = {}
    crit["pe_below_industry"] = bool(pe is not None and ind_pe is not None and 0 < pe < ind_pe)
    crit["industry_avg_pe"]   = ind_pe

    rev_g, prof_g = f.get("revenue_cagr_3y_pct"), f.get("profit_cagr_3y_pct")
    crit["growth_20pct_3y"] = bool(
        rev_g is not None and prof_g is not None and rev_g >= MIN_GROWTH_PCT and prof_g >= MIN_GROWTH_PCT
    )

    roe, roce = f.get("roe_pct"), f.get("roce_pct")
    crit["high_roe_roce"] = bool(
        (roe is not None and roe >= MIN_ROE_ROCE_PCT) or (roce is not None and roce >= MIN_ROE_ROCE_PCT)
    )

    de = f.get("debt_to_equity")
    crit["low_debt"] = bool(de is not None and de < MAX_DEBT_EQUITY)

    crit["criteria_passed"] = sum([crit["pe_below_industry"], crit["growth_20pct_3y"],
                                    crit["high_roe_roce"], crit["low_debt"]])
    crit["criteria_total"] = 4
    return crit
