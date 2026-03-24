"""
mutual_fund_engine.py
=====================
Discovers and ranks top Indian mutual funds dynamically.
No hardcoded fund names — all data from mfapi.in (AMFI official).

Data flow:
  1. Fetch all Direct Growth schemes from mfapi.in
  2. For each SEBI category, fetch NAV history → calculate real CAGR
  3. Composite score = 1Y×20% + 3Y×50% + 5Y×30%
  4. Top 5 per category saved to data.json
"""

import requests
import time
import json
import os
import gc
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytz

IST = pytz.timezone('Asia/Kolkata')

# ── SEBI category map ─────────────────────────────────────────────
# Keys are substrings of mfapi.in meta.scheme_category
# Values are display names shown in dashboard
SEBI_CATEGORIES = {
    'Large Cap Fund':              { 'label': 'Large Cap',       'icon': '🏦', 'color': '#1d4ed8',
                                     'note': 'Nifty 100 universe · Lower volatility · Wealth preservation' },
    'Mid Cap Fund':                { 'label': 'Mid Cap',         'icon': '📈', 'color': '#7c3aed',
                                     'note': 'Growth engine · 3-5yr horizon recommended' },
    'Small Cap Fund':              { 'label': 'Small Cap',       'icon': '🌱', 'color': '#16a34a',
                                     'note': 'High growth potential · High volatility · 5yr+ horizon' },
    'Flexi Cap Fund':              { 'label': 'Flexi Cap',       'icon': '🔄', 'color': '#0891b2',
                                     'note': 'No market cap restriction · All-weather allocation' },
    'ELSS':                        { 'label': 'ELSS (Tax Saver)','icon': '💰', 'color': '#dc2626',
                                     'note': '₹1.5L deduction u/s 80C · 3yr lock-in' },
    'Aggressive Hybrid Fund':      { 'label': 'Hybrid',          'icon': '⚖️', 'color': '#ea580c',
                                     'note': '65-80% equity · Lower drawdowns · Moderate risk' },
    'Index Funds':                 { 'label': 'Index Funds',     'icon': '📊', 'color': '#374151',
                                     'note': 'Benchmark returns · Lowest cost · Passive investing' },
    'Sectoral/Thematic':           { 'label': 'Sectoral',        'icon': '🏭', 'color': '#9333ea',
                                     'note': 'High conviction · Concentrated risk · Not for core portfolio' },
}

# How many candidate funds to evaluate per category before picking top 5
CANDIDATES_PER_CAT = 25
TOP_N = 5

# Composite score weights
WEIGHT_1Y = 0.20
WEIGHT_3Y = 0.50
WEIGHT_5Y = 0.30


def log(msg):
    print(f"[MF] {msg}")


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%d-%m-%Y")


def _parse_date(s: str) -> datetime:
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def fetch_all_schemes(session: requests.Session) -> list[dict]:
    """
    Fetch all scheme codes + names from mfapi.in.
    Filter to Direct + Growth plans only.
    Returns list of {schemeCode, schemeName}
    """
    log("Fetching all schemes from mfapi.in…")
    try:
        r = session.get("https://api.mfapi.in/mf", timeout=30)
        r.raise_for_status()
        all_schemes = r.json()
        log(f"  Total schemes: {len(all_schemes):,}")

        # Filter: must be Direct plan AND Growth option
        filtered = []
        for s in all_schemes:
            name = s.get('schemeName', '').lower()
            if 'direct' in name and ('growth' in name or '-gr' in name):
                # Exclude dividend / IDCW / bonus variants
                if not any(x in name for x in ['idcw', 'dividend', 'bonus', 'payout', 'reinvest']):
                    filtered.append(s)

        log(f"  After Direct+Growth filter: {len(filtered):,} schemes")
        return filtered

    except Exception as e:
        log(f"  ❌ Failed to fetch scheme list: {e}")
        return []


def fetch_nav_history(session: requests.Session, scheme_code: int) -> dict | None:
    """
    Fetch NAV history + meta for a single scheme.
    Returns full response dict or None on error.
    """
    try:
        r = session.get(
            f"https://api.mfapi.in/mf/{scheme_code}",
            timeout=15
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return None


def calculate_cagr(nav_data: list[dict], years: int, as_of: datetime) -> float | None:
    """
    Calculate CAGR over `years` years from NAV history.
    nav_data: list of {date, nav} newest-first from mfapi.in
    """
    if not nav_data or len(nav_data) < 2:
        return None

    # Latest NAV
    latest = nav_data[0]
    try:
        latest_nav  = float(latest['nav'])
        latest_date = _parse_date(latest['date'])
        if not latest_date or latest_nav <= 0:
            return None
    except (ValueError, TypeError):
        return None

    # Target date = latest_date - years
    target_date = latest_date - timedelta(days=int(years * 365.25))

    # Find closest NAV on or before target_date
    old_nav = None
    actual_years = years
    for entry in nav_data:  # newest-first; first match <= target_date is closest
        d = _parse_date(entry.get('date', ''))
        if d and d <= target_date:
            try:
                nav_val = float(entry['nav'])
                if nav_val > 0:
                    old_nav    = nav_val
                    actual_years = (latest_date - d).days / 365.25
                    break
            except (ValueError, TypeError):
                pass

    if not old_nav or actual_years < years * 0.75:
        # Fund too new for this timeframe
        return None

    cagr = (pow(latest_nav / old_nav, 1.0 / actual_years) - 1) * 100
    return round(cagr, 2)


def score_fund(r1y, r3y, r5y) -> float:
    """Composite score. Missing periods penalised, not ignored."""
    if r1y is None and r3y is None:
        return -999.0
    s = 0.0
    if r1y is not None: s += r1y * WEIGHT_1Y
    if r3y is not None: s += r3y * WEIGHT_3Y
    if r5y is not None: s += r5y * WEIGHT_5Y
    # Penalise funds missing long-term data (likely too new)
    if r3y is None: s -= 5.0
    if r5y is None: s -= 3.0
    return round(s, 3)


def discover_category_funds(
    session: requests.Session,
    category_key: str,
    category_info: dict,
    all_schemes: list[dict],
    max_candidates: int = CANDIDATES_PER_CAT
) -> list[dict]:
    """
    For a given SEBI category:
    1. Sample candidate funds from scheme list
    2. Fetch their meta to confirm category
    3. Calculate returns
    4. Rank and return top N
    """
    label = category_info['label']
    log(f"\n  Category: {label}")

    # Get scheme meta to find correct category — sample candidates broadly
    # We'll fetch meta for a random cross-section of schemes and filter by category
    # Start with schemes that have category keywords in name
    cat_keywords = {
        'Large Cap Fund':         ['large cap', 'bluechip', 'top 100'],
        'Mid Cap Fund':           ['mid cap', 'midcap'],
        'Small Cap Fund':         ['small cap', 'smallcap'],
        'Flexi Cap Fund':         ['flexi cap', 'flexicap', 'multi cap', 'multicap'],
        'ELSS':                   ['elss', 'tax saver', 'long term equity', 'taxsaver'],
        'Aggressive Hybrid Fund': ['equity hybrid', 'balanced advantage', 'aggressive hybrid'],
        'Index Funds':            ['index', 'nifty 50', 'nifty50', 'sensex'],
        'Sectoral/Thematic':      ['sectoral', 'thematic', 'technology', 'pharma', 'infra',
                                   'banking', 'consumption', 'digital', 'healthcare', 'psu', 'energy'],
    }

    keywords = cat_keywords.get(category_key, [category_key.lower()])
    candidates = []
    for s in all_schemes:
        name_lower = s['schemeName'].lower()
        if any(kw in name_lower for kw in keywords):
            candidates.append(s)

    log(f"    Keyword-matched candidates: {len(candidates)}")
    if not candidates:
        return []

    # Limit to avoid too many API calls
    candidates = candidates[:max_candidates]

    # Fetch NAV history in parallel threads
    results = []
    now = datetime.now()

    def process_scheme(scheme):
        code = scheme['schemeCode']
        data = fetch_nav_history(session, code)
        if not data:
            return None
        meta     = data.get('meta', {})
        nav_data = data.get('data', [])

        # Confirm it's actually this SEBI category
        scheme_cat = meta.get('scheme_category', '')
        if category_key.lower() not in scheme_cat.lower():
            return None

        if len(nav_data) < 60:  # Need at least 2 months of data
            return None

        r1y = calculate_cagr(nav_data, 1, now)
        r3y = calculate_cagr(nav_data, 3, now)
        r5y = calculate_cagr(nav_data, 5, now)

        return {
            'scheme_code':   code,
            'name':          meta.get('scheme_name', scheme['schemeName']),
            'fund_house':    meta.get('fund_house', ''),
            'category':      scheme_cat,
            'ret_1y':        r1y,
            'ret_3y':        r3y,
            'ret_5y':        r5y,
            'score':         score_fund(r1y, r3y, r5y),
            'nav_count':     len(nav_data),
        }

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(process_scheme, s): s for s in candidates}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception:
                pass
        time.sleep(0.1)  # be polite to mfapi.in

    # Sort by composite score
    results.sort(key=lambda x: x['score'], reverse=True)
    top = results[:TOP_N]

    log(f"    Evaluated {len(results)} funds → top {len(top)}")
    for f in top:
        log(f"      {f['name'][:50]:50s}  1Y:{str(f['ret_1y']):>7}  3Y:{str(f['ret_3y']):>7}  5Y:{str(f['ret_5y']):>7}  score:{f['score']:>7}")

    return top


def discover_hidden_gems(
    session: requests.Session,
    all_schemes: list[dict],
    max_age_months: int = 12,  # strictly < 12 months old
    top_n: int = 8
) -> list[dict]:
    """
    Find recently launched funds (≤18 months old) with strong since-launch returns.
    A "hidden gem" = new fund, not yet widely tracked, strong early performance.
    """
    now_str = datetime.now().strftime("%d %b %Y")
    log(f"\nDiscovering hidden gems — launched after {(datetime.now() - timedelta(days=int(max_age_months*30.44))).strftime('%d %b %Y')} (today: {now_str}, cutoff: {max_age_months} months)")

    cutoff_date = datetime.now() - timedelta(days=int(max_age_months * 30.5))
    results = []

    # Sample broadly — just check 100 random schemes for launch date
    import random
    sample = random.sample(all_schemes, min(200, len(all_schemes)))

    def check_gem(scheme):
        code = scheme['schemeCode']
        data = fetch_nav_history(session, code)
        if not data:
            return None

        nav_data = data.get('data', [])
        meta     = data.get('meta', {})

        if len(nav_data) < 10:  # too little history
            return None

        # Oldest NAV date = launch date
        oldest = _parse_date(nav_data[-1].get('date', ''))
        if not oldest or oldest < cutoff_date:
            return None  # too old or can't determine

        # Calculate since-launch return
        try:
            launch_nav = float(nav_data[-1]['nav'])
            current_nav = float(nav_data[0]['nav'])
            if launch_nav <= 0:
                return None
        except (ValueError, TypeError):
            return None

        months_old = int((datetime.now() - oldest).days / 30.44)  # integer floor months
        ret_since_launch = (current_nav / launch_nav - 1) * 100

        # Must have positive return to be a "gem"
        if ret_since_launch < 0:
            return None

        r1y = calculate_cagr(nav_data, 1, datetime.now())

        category = meta.get('scheme_category', '')
        # Skip debt, liquid, overnight funds
        if any(x in category.lower() for x in ['debt', 'liquid', 'overnight', 'money market', 'gilt']):
            return None

        return {
            'scheme_code':      code,
            'name':             meta.get('scheme_name', scheme['schemeName']),
            'fund_house':       meta.get('fund_house', ''),
            'category':         category,
            'nav':              round(current_nav, 2),
            'launched':         oldest.strftime('%b %Y'),
            'months_old':       round(months_old, 1),
            'ret_since_launch': round(ret_since_launch, 2),
            'ret_1y':           r1y,
            'aum':              None,  # not available from mfapi.in
            'why_gem':          (f"Launched {oldest.strftime('%b %Y')} · "
                                f"{months_old} months old · "
                                f"Current NAV ₹{current_nav:.2f} · "
                                f"{'Exceptional early momentum' if ret_since_launch > 30 else 'Strong early momentum' if ret_since_launch > 15 else 'Steady growth since launch'}"),
        }

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(check_gem, s): s for s in sample}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception:
                pass

    results.sort(key=lambda x: x['ret_since_launch'], reverse=True)
    top = results[:top_n]
    log(f"  Found {len(results)} recently launched funds → top {len(top)} gems")
    return top


def fetch_top_mutual_funds() -> dict:
    """
    Main entry point. Returns dict ready to embed in data.json under 'mutual_funds' key.
    """
    log("=" * 60)
    log("Starting mutual fund discovery & ranking")
    log("=" * 60)

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 IndiaStockAI/1.0',
        'Accept': 'application/json',
    })

    all_schemes = fetch_all_schemes(session)
    if not all_schemes:
        return {}

    output = {
        'updated_at':  datetime.now(IST).isoformat(),
        'source':      'mfapi.in (AMFI official NAV data)',
        'methodology': f'Top {TOP_N} per SEBI category ranked by composite score '
                       f'(1Y×{WEIGHT_1Y*100:.0f}% + 3Y×{WEIGHT_3Y*100:.0f}% + 5Y×{WEIGHT_5Y*100:.0f}%)',
        'categories':  [],
    }

    for cat_key, cat_info in SEBI_CATEGORIES.items():
        try:
            funds = discover_category_funds(session, cat_key, cat_info, all_schemes)
            output['categories'].append({
                'key':   cat_key,
                'label': cat_info['label'],
                'icon':  cat_info['icon'],
                'color': cat_info['color'],
                'note':  cat_info['note'],
                'funds': funds,
            })
            del funds        # release NAV data from memory
            gc.collect()     # force GC — prevents OOM on Railway
            time.sleep(0.5)  # between categories
        except Exception as e:
            log(f"  ❌ {cat_info['label']}: {e}")

    # Discover hidden gems
    log("\nStarting hidden gems discovery…")
    try:
        hidden_gems = discover_hidden_gems(session, all_schemes)
        output['hidden_gems'] = hidden_gems
    except Exception as e:
        log(f"  ⚠️  Hidden gems discovery failed: {e}")
        output['hidden_gems'] = []

    total_funds = sum(len(c['funds']) for c in output['categories'])
    log(f"\n✅ Done — {total_funds} funds across {len(output['categories'])} categories "
        f"+ {len(output.get('hidden_gems', []))} hidden gems")
    return output


if __name__ == "__main__":
    result = fetch_top_mutual_funds()
    print(json.dumps(result, indent=2, default=str))
