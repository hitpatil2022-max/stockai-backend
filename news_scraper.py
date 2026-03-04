"""
News Scraper - Fetches Indian market news from free RSS feeds
Sources: Economic Times, Business Standard, Mint, Moneycontrol
"""

import feedparser
from datetime import datetime, timedelta
from config import NEWS_SOURCES, WATCHLIST

# Extract ticker symbols from watchlist (remove .NS suffix)
SYMBOLS = [s.replace(".NS", "").replace("^", "") for s in WATCHLIST]

# Keywords that indicate high-impact news
HIGH_IMPACT_KEYWORDS = [
    "acquisition", "merger", "deal", "partnership", "contract",
    "quarterly results", "earnings", "revenue", "profit", "loss",
    "RBI", "SEBI", "government", "policy", "tax", "GST",
    "FII", "FDI", "foreign investment",
    "CEO", "management change", "founder",
    "IPO", "buyback", "dividend", "bonus shares",
    "raid", "fraud", "scam", "investigation",
    "new product", "launch", "expansion",
    "US", "China", "global", "recession", "inflation",
    "crude oil", "rupee", "dollar", "interest rate",
]

def fetch_rss_feed(url):
    """Fetch and parse a single RSS feed — last 6 hours only"""
    try:
        feed  = feedparser.parse(url)
        items = []
        cutoff = datetime.now() - timedelta(hours=6)

        for entry in feed.entries[:30]:
            # Try to parse published date and filter old news
            published_str = entry.get("published", "")
            try:
                import email.utils
                published_dt = datetime(*email.utils.parsedate(published_str)[:6])
                if published_dt < cutoff:
                    continue  # Skip news older than 6 hours
            except Exception:
                pass  # If date can't be parsed, include the item anyway

            items.append({
                "title":     entry.get("title", ""),
                "summary":   entry.get("summary", "")[:500],
                "link":      entry.get("link", ""),
                "published": published_str or str(datetime.now()),
                "source":    feed.feed.get("title", url),
            })

        return items
    except Exception as e:
        print(f"   Warning: Failed to fetch {url}: {e}")
        return []

def extract_mentioned_stocks(text):
    """Find which stocks are mentioned in a news item"""
    mentioned  = []
    text_upper = text.upper()
    for symbol in SYMBOLS:
        if symbol in text_upper:
            mentioned.append(symbol)
    return mentioned

def score_news_importance(title, summary):
    """Score news from 1-10 based on market impact potential"""
    text  = (title + " " + summary).lower()
    score = 5  # Base score

    for keyword in HIGH_IMPACT_KEYWORDS:
        if keyword.lower() in text:
            score += 0.5

    if any(word in text for word in ["crore", "billion", "lakh", "trillion"]):
        score += 1

    if "%" in text:
        score += 0.5

    return min(10, round(score, 1))

def fetch_google_news_india():
    """Fetch from Google News RSS for Indian markets (free, no API key)"""
    queries = [
        "Indian stock market NSE BSE",
        "Nifty Sensex today",
        "India economy RBI SEBI",
    ]
    items = []
    for query in queries:
        url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en-IN&gl=IN&ceid=IN:en"
        items.extend(fetch_rss_feed(url))
    return items

def fetch_all_news():
    """Fetch news from all sources and return ranked list"""
    all_news = []

    for source_url in NEWS_SOURCES:
        items = fetch_rss_feed(source_url)
        all_news.extend(items)

    google_items = fetch_google_news_india()
    all_news.extend(google_items)

    # Deduplicate and enrich
    seen_titles = set()
    enriched    = []

    for item in all_news:
        title = item["title"]
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)

        item["mentioned_stocks"] = extract_mentioned_stocks(title + " " + item["summary"])
        item["importance_score"] = score_news_importance(title, item["summary"])
        item["sentiment"]        = "neutral"   # Updated by AI analyzer
        item["impact"]           = "unknown"   # Updated by AI analyzer

        enriched.append(item)

    enriched.sort(key=lambda x: x["importance_score"], reverse=True)
    return enriched[:50]
