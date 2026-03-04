"""
Market Intelligence - FII/DII Data, Bulk Deals, Insider Trades
All from free public sources (NSE/BSE/Moneycontrol)
"""

import requests
import json
from datetime import datetime, timedelta

# NSE requires browser-like headers to avoid blocks
NSE_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.nseindia.com/",
    "Connection":      "keep-alive",
}

def get_nse_session():
    """Create a session with NSE cookies (required for API access)"""
    session = requests.Session()
    try:
        # Visit homepage first to get cookies
        session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
    except Exception:
        pass
    return session

def fetch_fii_dii_data():
    """
    Fetch FII/DII buy-sell activity for today
    Source: NSE India (free, public data)
    FII = Foreign Institutional Investors
    DII = Domestic Institutional Investors
    """
    try:
        session = get_nse_session()
        url = "https://www.nseindia.com/api/fiidiiTradeReact"
        response = session.get(url, headers=NSE_HEADERS, timeout=10)

        if response.status_code == 200:
            data = response.json()
            result = {
                "date":        datetime.now().strftime("%Y-%m-%d"),
                "fii":         {},
                "dii":         {},
                "sentiment":   "neutral",
                "raw":         data[:2] if data else []
            }

            for entry in data[:2]:
                category = entry.get("category", "").upper()
                bought   = float(str(entry.get("bought", "0")).replace(",", "") or 0)
                sold     = float(str(entry.get("sold", "0")).replace(",", "") or 0)
                net      = bought - sold

                if "FII" in category or "FPI" in category:
                    result["fii"] = {
                        "bought_cr": round(bought / 100, 2),
                        "sold_cr":   round(sold / 100, 2),
                        "net_cr":    round(net / 100, 2),
                        "action":    "BUYING" if net > 0 else "SELLING",
                    }
                elif "DII" in category:
                    result["dii"] = {
                        "bought_cr": round(bought / 100, 2),
                        "sold_cr":   round(sold / 100, 2),
                        "net_cr":    round(net / 100, 2),
                        "action":    "BUYING" if net > 0 else "SELLING",
                    }

            # Overall sentiment
            fii_net = result["fii"].get("net_cr", 0)
            dii_net = result["dii"].get("net_cr", 0)
            if fii_net > 500 or dii_net > 500:
                result["sentiment"] = "strongly_bullish"
            elif fii_net > 0 and dii_net > 0:
                result["sentiment"] = "bullish"
            elif fii_net < -500 or dii_net < -500:
                result["sentiment"] = "strongly_bearish"
            elif fii_net < 0 and dii_net < 0:
                result["sentiment"] = "bearish"

            print("   FII/DII data fetched successfully")
            return result

    except Exception as e:
        print("   Warning: FII/DII fetch failed: " + str(e))

    return {"date": datetime.now().strftime("%Y-%m-%d"), "fii": {}, "dii": {}, "sentiment": "unknown"}

def fetch_bulk_deals():
    """
    Fetch today's bulk deals from NSE
    Bulk deal = large trade (>0.5% of total shares) by big players
    This reveals where smart money is moving
    """
    try:
        session = get_nse_session()
        url = "https://www.nseindia.com/api/bulk-deals"
        response = session.get(url, headers=NSE_HEADERS, timeout=10)

        if response.status_code == 200:
            data  = response.json()
            deals = data.get("data", [])[:20]  # Top 20 deals

            processed = []
            for deal in deals:
                processed.append({
                    "symbol":   deal.get("symbol", ""),
                    "name":     deal.get("stockDesc", ""),
                    "client":   deal.get("clientName", ""),
                    "action":   "BUY" if "BUY" in str(deal.get("buySell", "")).upper() else "SELL",
                    "quantity": deal.get("tradedQty", 0),
                    "price":    deal.get("tradePrice", 0),
                })

            print("   Bulk deals fetched: " + str(len(processed)) + " deals today")
            return processed

    except Exception as e:
        print("   Warning: Bulk deals fetch failed: " + str(e))

    return []

def fetch_insider_trades():
    """
    Fetch recent insider trading disclosures from NSE
    SEBI requires insiders to disclose trades within 2 trading days
    """
    try:
        session = get_nse_session()
        url = "https://www.nseindia.com/api/corporates-pit"
        params = {"index": "equities", "from_date": (datetime.now() - timedelta(days=7)).strftime("%d-%m-%Y"),
                  "to_date": datetime.now().strftime("%d-%m-%Y")}
        response = session.get(url, headers=NSE_HEADERS, params=params, timeout=10)

        if response.status_code == 200:
            data   = response.json()
            trades = data.get("data", [])[:15]

            processed = []
            for trade in trades:
                qty       = float(str(trade.get("noOfShareBroughtSold", "0")).replace(",", "") or 0)
                buy_sell  = str(trade.get("typeOfSecurity", "")).upper()
                processed.append({
                    "symbol":   trade.get("symbol", ""),
                    "insider":  trade.get("personName", ""),
                    "role":     trade.get("typeOfPerson", ""),
                    "action":   "BUY" if "BUY" in buy_sell or qty > 0 else "SELL",
                    "quantity": qty,
                    "value_cr": round(qty * float(str(trade.get("tradedPrice", 0)).replace(",", "") or 0) / 10000000, 2),
                    "date":     trade.get("date", ""),
                })

            print("   Insider trades fetched: " + str(len(processed)) + " disclosures")
            return processed

    except Exception as e:
        print("   Warning: Insider trades fetch failed: " + str(e))

    return []

def fetch_all_market_intelligence():
    """Fetch all market intelligence data in one call"""
    print("   Fetching FII/DII data...")
    fii_dii = fetch_fii_dii_data()

    print("   Fetching bulk deals...")
    bulk_deals = fetch_bulk_deals()

    print("   Fetching insider trades...")
    insider_trades = fetch_insider_trades()

    return {
        "fii_dii":       fii_dii,
        "bulk_deals":    bulk_deals,
        "insider_trades": insider_trades,
        "fetched_at":    datetime.now().isoformat(),
    }

def format_for_ai(intel):
    """Format market intelligence data compactly for AI prompt"""
    lines = []

    # FII/DII
    fii = intel.get("fii_dii", {})
    if fii.get("fii") or fii.get("dii"):
        fii_data = fii.get("fii", {})
        dii_data = fii.get("dii", {})
        lines.append("FII/DII Activity:")
        if fii_data:
            lines.append("  FII: " + fii_data.get("action", "?") + " Net=" + str(fii_data.get("net_cr", 0)) + " Cr")
        if dii_data:
            lines.append("  DII: " + dii_data.get("action", "?") + " Net=" + str(dii_data.get("net_cr", 0)) + " Cr")
        lines.append("  Sentiment: " + fii.get("sentiment", "unknown").upper())

    # Bulk deals (top 5)
    bulk = intel.get("bulk_deals", [])
    if bulk:
        lines.append("\nBulk Deals (Big Money Moves):")
        for deal in bulk[:5]:
            lines.append("  " + deal["symbol"] + ": " + deal["action"]
                         + " by " + deal["client"][:40]
                         + " @ " + str(deal["price"]))

    # Insider trades (top 5)
    insider = intel.get("insider_trades", [])
    if insider:
        lines.append("\nInsider Trades (Last 7 days):")
        for trade in insider[:5]:
            lines.append("  " + trade["symbol"] + ": " + trade["action"]
                         + " by " + trade["insider"][:30]
                         + " (" + trade["role"] + ")"
                         + " Value=₹" + str(trade["value_cr"]) + "Cr")

    return "\n".join(lines) if lines else "Market intelligence data unavailable today."
