"""
Political & Business Intelligence Analyzer
Scans news for mentions of key figures linked to stocks
Finds hidden/indirect connections that could impact stock prices
"""

from datetime import datetime

# ── Key figures to watch ──────────────────────────────────────────────────────

POLITICIANS = {
    "Narendra Modi":    ["RELIANCE", "ADANIENT", "LT", "NTPC", "POWERGRID", "ONGC"],
    "Amit Shah":        ["ADANIENT", "ADANIPORTS"],
    "Nirmala Sitharaman": ["SBIN", "HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK"],
    "Piyush Goyal":     ["COALINDIA", "NTPC", "POWERGRID", "LT"],
    "Nitin Gadkari":    ["LT", "TATAMOTORS", "MARUTI", "BAJAJ-AUTO"],
    "Arvind Kejriwal":  ["NTPC", "POWERGRID", "BHARTIARTL"],
    "Mamata Banerjee":  ["TATASTEEL", "JSWSTEEL", "COALINDIA"],
    "Yogi Adityanath":  ["RELIANCE", "ADANIENT", "NTPC"],
    "Rahul Gandhi":     ["SBIN", "HDFCBANK", "RELIANCE"],
    "RBI Governor":     ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "BAJFINANCE"],
    "SEBI":             ["ALL"],
}

BUSINESS_FIGURES = {
    "Mukesh Ambani":    ["RELIANCE"],
    "Gautam Adani":     ["ADANIENT", "ADANIPORTS", "ADANIGREEN", "ADANITRANS"],
    "Ratan Tata":       ["TATAMOTORS", "TATASTEEL", "TCS", "TATAPOWER"],
    "Cyrus Mistry":     ["TATAMOTORS", "TATASTEEL", "TCS"],
    "Kumar Mangalam Birla": ["HINDALCO", "ULTRACEMCO", "GRASIM"],
    "Azim Premji":      ["WIPRO"],
    "Narayana Murthy":  ["INFY"],
    "Uday Kotak":       ["KOTAKBANK"],
    "Deepinder Goyal":  ["ZOMATO"],
    "Rakesh Jhunjhunwala": ["TITAN", "STAR HEALTH", "AKASA"],
    "Ashish Kacholia":  ["SMALLCAP"],
    "Radhakishan Damani": ["DMart", "DMART"],
    "Vijay Kedia":      ["SMALLCAP"],
}

# Indirect / sector connection map
# If figure X is mentioned + topic Y, these stocks are indirectly affected
INDIRECT_CONNECTIONS = {
    "infrastructure": ["LT", "NTPC", "POWERGRID", "ADANIENT"],
    "bank":           ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK"],
    "telecom":        ["BHARTIARTL", "RELIANCE"],
    "oil gas":        ["RELIANCE", "ONGC", "BPCL", "IOC"],
    "defence":        ["LT", "HAL", "BEL", "BHEL"],
    "renewable":      ["NTPC", "ADANIGREEN", "TATAPOWER", "POWERGRID"],
    "electric vehicle": ["TATAMOTORS", "BAJAJ-AUTO", "MARUTI"],
    "pharma":         ["SUNPHARMA", "DRREDDY", "CIPLA"],
    "it sector":      ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM"],
    "steel":          ["TATASTEEL", "JSWSTEEL"],
    "agriculture":    ["ITC", "UPL"],
    "fdi":            ["HDFCBANK", "ICICIBANK", "RELIANCE", "INFY", "TCS"],
    "budget":         ["SBIN", "LT", "NTPC", "COALINDIA", "ONGC"],
    "rbi rate":       ["HDFCBANK", "ICICIBANK", "SBIN", "BAJFINANCE", "KOTAKBANK"],
    "gst":            ["ITC", "HINDUNILVR", "MARUTI", "RELIANCE"],
    "upi":            ["HDFCBANK", "ICICIBANK", "AXISBANK", "SBIN"],
}

def scan_for_figures(news_items):
    """
    Scan news for political/business figure mentions
    Returns list of intelligence findings
    """
    findings = []

    for item in news_items:
        text = (item.get("title", "") + " " + item.get("summary", "")).lower()

        matched_figures  = []
        affected_stocks  = set()
        indirect_sectors = []

        # Check politicians
        for figure, stocks in POLITICIANS.items():
            if figure.lower() in text:
                matched_figures.append(("POLITICIAN", figure))
                if "ALL" in stocks:
                    affected_stocks.update(["HDFCBANK", "RELIANCE", "TCS", "SBIN"])
                else:
                    affected_stocks.update(stocks)

        # Check business figures
        for figure, stocks in BUSINESS_FIGURES.items():
            if figure.lower() in text:
                matched_figures.append(("BUSINESS", figure))
                affected_stocks.update(stocks)

        # Check indirect sector connections
        for sector, stocks in INDIRECT_CONNECTIONS.items():
            if sector in text:
                indirect_sectors.append(sector)
                affected_stocks.update(stocks)

        if matched_figures or indirect_sectors:
            findings.append({
                "title":            item.get("title", ""),
                "source":           item.get("source", ""),
                "figures_mentioned": matched_figures,
                "indirect_sectors": indirect_sectors,
                "potentially_affected_stocks": list(affected_stocks),
                "importance":       item.get("importance_score", 5),
                "published":        item.get("published", ""),
            })

    # Sort by importance
    findings.sort(key=lambda x: x["importance"], reverse=True)
    return findings[:10]  # Top 10 findings

def format_for_ai(findings):
    """Format political/business intelligence for AI prompt"""
    if not findings:
        return "No significant political or business figure activity detected."

    lines = []
    for f in findings:
        figures = ", ".join([fig + " (" + ftype + ")" for ftype, fig in f["figures_mentioned"]])
        sectors = ", ".join(f["indirect_sectors"]) if f["indirect_sectors"] else "direct mention"
        stocks  = ", ".join(f["potentially_affected_stocks"][:6])
        lines.append(
            "- " + f["title"][:100] + "\n"
            + "  Figures: " + (figures or "indirect connection") + "\n"
            + "  Sectors: " + sectors + "\n"
            + "  Potentially affected: " + stocks
        )
    return "\n".join(lines)
