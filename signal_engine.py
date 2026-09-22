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

    NOTE: field names below (buyValue/sellValue/netValue/category) were verified
    against a real captured NSE response — the previous version of this function
    used "bought"/"sold" (fields that don't exist in NSE's actual response), which
    silently produced 0.0 for every value while "raw" showed the real numbers
    right next to it. Also removed an incorrect /100 division — NSE already
    reports these in ₹ Crores directly, confirmed by buyValue - sellValue == netValue
    on real data (e.g. 18256.88 - 16592.72 = 1664.16, matching netValue exactly).
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
                bought   = float(str(entry.get("buyValue", "0")).replace(",", "") or 0)
                sold     = float(str(entry.get("sellValue", "0")).replace(",", "") or 0)
                net_raw  = entry.get("netValue")
                net      = float(str(net_raw).replace(",", "")) if net_raw not in (None, "") else (bought - sold)

                if "FII" in category or "FPI" in category:
                    result["fii"] = {
                        "bought_cr": round(bought, 2),
                        "sold_cr":   round(sold, 2),
                        "net_cr":    round(net, 2),
                        "action":    "BUYING" if net > 0 else "SELLING",
                    }
                elif "DII" in category:
                    result["dii"] = {
                        "bought_cr": round(bought, 2),
                        "sold_cr":   round(sold, 2),
                        "net_cr":    round(net, 2),
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


# ── Bulk deal enrichment: narrative sentence + rule-based impact tag ────────
# Deliberately NOT another Gemini call — the app already fights a shared 15/min
# free-tier quota; this is a deterministic, explainable, zero-cost alternative.
KNOWN_MARQUEE_INSTITUTIONS = [
    "government of singapore", "gic", "temasek", "norges bank",
    "abu dhabi investment", "qatar investment", "blackrock", "vanguard",
    "fidelity", "capital group", "t. rowe price", "t rowe price",
    "morgan stanley", "goldman sachs", "jpmorgan", "jp morgan",
    "life insurance corporation", " lic ", "sbi mutual fund",
    "hdfc mutual fund", "icici prudential", "kotak mahindra mutual",
    "axis mutual fund", "nomura", "citigroup", "hsbc",
]


def _deal_size_tier(value_cr):
    if value_cr is None:
        return "Unknown"
    if value_cr >= 100:
        return "Major"
    if value_cr >= 25:
        return "Significant"
    return "Moderate"


def _is_marquee_institution(client_name):
    if not client_name:
        return False
    name_l = f" {client_name.lower()} "
    return any(k in name_l for k in KNOWN_MARQUEE_INSTITUTIONS)


def _deal_narrative(deal):
    """One-sentence plain-English description of the actual deal."""
    verb = "bought" if deal["action"] == "BUY" else "sold"
    qty = deal.get("quantity") or 0
    qty_str = f"{int(qty):,}" if qty else "an undisclosed number of"
    value_str = f" worth ₹{deal['value_cr']} Cr" if deal.get("value_cr") else ""
    price_str = f" at ₹{deal['price']:,.2f}/share" if deal.get("price") else ""
    date_str = f" on {deal['date']}" if deal.get("date") else ""
    stock_label = deal.get("name") or deal.get("symbol", "this stock")
    client = deal.get("client") or "An investor"
    return f"{client} {verb} {qty_str} shares of {stock_label}{value_str}{price_str}{date_str}."


def _deal_impact(deal):
    """
    Rule-based, deterministic impact read — NOT an AI guess. Based only on:
    (1) deal size tier, (2) whether the buyer/seller is a well-known institution,
    (3) buy vs. sell direction. Deliberately hedged language — a single bulk deal
    is a data point, not a prediction.
    """
    tier = _deal_size_tier(deal.get("value_cr"))
    marquee = _is_marquee_institution(deal.get("client", ""))

    if tier == "Unknown":
        return {"tier": tier, "tag": "ℹ️ Limited data",
                "note": "Deal value couldn't be computed from available quantity/price data.",
                "marquee_institution": marquee}

    if deal["action"] == "BUY":
        if marquee and tier in ("Major", "Significant"):
            tag = "🟢 Bullish — Marquee institutional buying"
            note = (f"A well-known institutional investor made a {tier.lower()} purchase. "
                     "Large, reputable buyers accumulating a stock is often read as a vote of "
                     "confidence, though it doesn't guarantee future price direction.")
        elif tier == "Major":
            tag = "🟢 Bullish — Large buying activity"
            note = ("A large single-day purchase of this size can reflect strong institutional "
                     "conviction, though the buyer's strategy (long-term hold vs. short-term "
                     "arbitrage) isn't disclosed by NSE.")
        else:
            tag = "🟡 Mildly positive"
            note = ("A moderate buy — worth watching if followed by more buying in subsequent "
                     "sessions, but not a strong signal on its own.")
    else:
        if marquee and tier in ("Major", "Significant"):
            tag = "🔴 Cautionary — Marquee institutional selling"
            note = (f"A well-known institutional investor made a {tier.lower()} sale. This can "
                     "reflect profit-booking or portfolio rebalancing rather than a negative "
                     "view — context beyond this single data point matters.")
        elif tier == "Major":
            tag = "🔴 Cautionary — Large selling activity"
            note = ("A large single-day sale can reflect profit-booking or a strategic exit. "
                     "Worth checking if this is a one-off or part of a sustained trend.")
        else:
            tag = "🟡 Mildly cautionary"
            note = "A moderate sell — not significant enough alone to draw strong conclusions."

    return {"tier": tier, "tag": tag, "note": note, "marquee_institution": marquee}


def fetch_bulk_deals():
    """
    Fetch today's bulk deals from NSE
    Bulk deal = large trade (>0.5% of total shares) by big players
    This reveals where smart money is moving

    NOTE: field names below (BD_SYMBOL, BD_CLIENT_NAME, BD_QTY_TRD, etc.) were
    verified against a real captured NSE bulk-deals response — the previous
    version of this function used plain names like "symbol"/"clientName"/
    "tradedQty" that don't exist in NSE's actual response, so every field
    silently came back empty/zero and every deal defaulted to SELL regardless
    of the real action.
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
                symbol = deal.get("BD_SYMBOL", "")
                name   = deal.get("BD_SCRIP_NAME", "")
                client = deal.get("BD_CLIENT_NAME", "")
                action = "BUY" if "BUY" in str(deal.get("BD_BUY_SELL", "")).upper() else "SELL"
                qty    = float(str(deal.get("BD_QTY_TRD", 0)).replace(",", "") or 0)
                price  = float(str(deal.get("BD_TP_WATP", 0)).replace(",", "") or 0)
                date   = deal.get("BD_DT_DATE", "")
                value_cr = round((qty * price) / 1e7, 2) if qty and price else None

                item = {
                    "symbol": symbol, "name": name, "client": client,
                    "action": action, "quantity": qty, "price": price,
                    "date": date, "value_cr": value_cr,
                }
                item["narrative"] = _deal_narrative(item)
                item["impact"] = _deal_impact(item)
                processed.append(item)

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
