"""
filing_pdf_analyzer.py
----------------------
Downloads NSE filing PDFs, extracts text via pymupdf, classifies
sentiment and extracts key numbers using regex + heuristics.

Filter logic (operator trap protection):
- Symbol must be in NIFTY500 universe (or pass volume threshold)
- 20-day avg volume must be >= MIN_AVG_VOLUME (default 200,000 shares)
- Market cap proxy: rejects stocks with avg_volume < 50,000 (illiquid)
"""

import io
import json
import logging
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── NIFTY 500 symbol set (NSE trading symbols) ────────────────────────────
# Core NIFTY50 + NIFTY100 + NIFTY200 + NIFTY500 additions
# This is the operator-trap protection layer — we only analyse filings
# for stocks with sufficient institutional participation.
NIFTY500_SYMBOLS: set[str] = {
    # NIFTY 50
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "BHARTIARTL",
    "SBIN", "ITC", "HINDUNILVR", "KOTAKBANK", "LT", "AXISBANK",
    "BAJFINANCE", "MARUTI", "NTPC", "TITAN", "SUNPHARMA", "WIPRO",
    "HCLTECH", "ULTRACEMCO", "POWERGRID", "BAJAJFINSV", "TECHM",
    "NESTLEIND", "ADANIENT", "ADANIPORTS", "ONGC", "JSWSTEEL",
    "TATASTEEL", "HINDALCO", "COALINDIA", "GRASIM", "INDUSINDBK",
    "CIPLA", "DRREDDY", "DIVISLAB", "APOLLOHOSP", "EICHERMOT",
    "BAJAJ-AUTO", "HEROMOTOCO", "TATACONSUM", "BRITANNIA", "ASIANPAINT",
    "PIDILITIND", "HAVELLS", "DMART", "TRENT", "NAUKRI", "ETERNAL",
    # NIFTY 100 additions
    "BANKBARODA", "PNB", "IDFCFIRSTB", "FEDERALBNK", "AUBANK",
    "CHOLAFIN", "SBICARD", "SBILIFE", "HDFCLIFE", "ICICIPRULI",
    "LTIM", "MPHASIS", "PERSISTENT", "COFORGE", "OFSS",
    "TATAELXSI", "KPITTECH", "MOTHERSON", "BOSCHLTD", "BHARATFORG",
    "BALKRISIND", "APOLLOTYRE", "CEATLTD", "EXIDEIND",
    "AUROPHARMA", "ALKEM", "IPCALAB", "LUPIN", "TORNTPHARM", "BIOCON",
    "MAXHEALTH", "FORTIS", "GLAXO", "PFIZER", "ABBOTINDIA",
    "MARICO", "DABUR", "GODREJCP", "COLPAL", "EMAMILTD",
    "BPCL", "IOC", "GAIL", "TATAPOWER", "ADANIGREEN", "ADANIPOWER",
    "TORNTPOWER", "CESC", "SJVN", "NHPC", "IREDA",
    "VEDL", "NMDC", "SAIL", "JINDALSTEL", "NATIONALUM", "HINDCOPPER",
    "SHREECEM", "AMBUJACEM", "ACC", "RAMCOCEM", "JKCEMENT",
    "ABB", "SIEMENS", "HAL", "BEL", "BHEL", "CUMMINSIND", "THERMAX",
    "DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "PHOENIXLTD",
    "SRF", "AARTIIND", "DEEPAKNTR", "NAVINFLUOR", "TATACHEM",
    "IRCTC", "JIOFIN", "PAYTM", "NYKAA", "POLICYBZR",
    "HDFCAMC", "NIPPONLIFE", "ICICIGI", "RECLTD", "PFC",
    "MUTHOOTFIN", "BAJAJHLDNG", "LICHSGFIN",
    "CANBK", "UNIONBANK", "INDIANB", "BANKINDIA", "MAHABANK",
    # NIFTY 200 / 500 additions (liquid mid-caps)
    "VOLTAS", "CROMPTON", "VGUARD", "BLUESTARCO", "WHIRLPOOL",
    "TATACOMM", "IDEA", "VBL", "RADICO", "UNITDSPR",
    "SUPREMEIND", "ASTRAL", "PRINCEPIPE",
    "AIAENG", "GRINDWELL", "SCHAEFFLER", "TIINDIA",
    "SUNDRMFAST", "NATCOPHARM", "IPCALAB",
    "BRIGADE", "SOBHA", "MAHINDCIE", "ENDURANCE",
    "ZOMATO", "PAYTM", "NYKAA", "POLICYBZR", "DELHIVERY",
    "CAMPUS", "LATENTVIEW", "HAPPYFORGE",
    "KALYANKJIL", "SENCO", "PNGJEWELLERS",
    "JSWENERGY", "GREENPANEL", "CENTURYPLY",
    "FINPIPE", "HFCL", "STLTECH", "RAILTEL",
    "RVNL", "IRFC", "HUDCO", "NBCC",
    "COCHINSHIP", "MAZAGON", "GRSE", "BDL",
    "CDSL", "BSE", "MCX", "CAMS",
    "ANGELONE", "5PAISA",
    "ZYDUSLIFE", "GLENMARK", "SUNPHARMA", "JBCHEPHARM",
    "LALPATHLAB", "METROPOLIS", "THYROCARE",
    "INDIAMART", "JUSTDIAL", "INFOEDGE",
    "MFSL", "STARHEALTH", "NIACL",
    "PGHH", "GILLETTE", "3MINDIA",
    "TATAELXSI", "MASTEK", "ZENSAR", "HEXAWARE",
    "CYIENT", "LTTS", "BIRLASOFT",
    "PIIND", "UPL", "BAYER", "RALLIS",
    "GNFC", "ALKYLAMINE", "CLEAN", "FINEORG",
    "WELCORP", "RATNAMANI", "JINDALSAW",
    "HEIDELBERG", "STARCEMENT", "JKPAPER", "TNPL",
    "PAGEIND", "MANYAVAR", "VEDANT",
    "SHOPERSTOP", "VMART", "TRENT",
    "ZEEL", "SUNTV", "PVRINOX", "INOXWIND",
    "CONCOR", "BLUEDART", "GATI", "TCI",
    "MAHLOG", "ALLCARGO",
}

# Minimum 20-day average daily volume to pass operator filter
MIN_AVG_VOLUME = 200_000  # 2 lakh shares/day
# Absolute floor — below this it's illiquid regardless of index membership
ILLIQUID_FLOOR = 50_000

_NSE_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


# ── Volume filter ─────────────────────────────────────────────────────────

def _get_avg_volume(symbol: str) -> Optional[float]:
    """Fetch 20-day avg volume from DB candles. Returns None if no data."""
    try:
        from app.db.session import SessionLocal
        from app.db.models_candles import CandleDaily
        from sqlalchemy import func

        db = SessionLocal()
        try:
            rows = (
                db.query(CandleDaily.volume)
                .filter(CandleDaily.symbol == symbol)
                .order_by(CandleDaily.date.desc())
                .limit(20)
                .all()
            )
            if len(rows) < 5:
                return None
            vols = [r[0] for r in rows if r[0] and r[0] > 0]
            return sum(vols) / len(vols) if vols else None
        finally:
            db.close()
    except Exception as e:
        logger.warning("avg_volume fetch failed for %s: %s", symbol, e)
        return None


def passes_operator_filter(symbol: str) -> tuple[bool, float, str]:
    """
    Returns (passed, avg_volume, reason).
    Passes if:
      - Symbol is in NIFTY500 (volume data optional — no candles yet is not a rejection)
      - OR not in NIFTY500 but avg_volume >= MIN_AVG_VOLUME (liquid mid-cap)
    """
    avg_vol_raw = _get_avg_volume(symbol)  # None = no candle data yet
    avg_vol = avg_vol_raw or 0.0
    in_nifty500 = symbol.upper() in NIFTY500_SYMBOLS

    # NIFTY500 members always pass — volume check is secondary protection
    if in_nifty500:
        if avg_vol_raw is None:
            return True, avg_vol, f"NIFTY500 member (no candle data yet)"
        if avg_vol < ILLIQUID_FLOOR:
            return False, avg_vol, f"NIFTY500 but illiquid: avg_vol={avg_vol:.0f} < {ILLIQUID_FLOOR}"
        return True, avg_vol, f"NIFTY500 member, avg_vol={avg_vol:.0f}"

    # Non-NIFTY500: require volume data and minimum threshold
    if avg_vol_raw is None:
        return False, avg_vol, "not NIFTY500 + no candle data"
    if avg_vol >= MIN_AVG_VOLUME:
        return True, avg_vol, f"liquid non-index stock, avg_vol={avg_vol:.0f}"

    return False, avg_vol, f"not NIFTY500 + avg_vol={avg_vol:.0f} < {MIN_AVG_VOLUME}"


# ── PDF download + text extraction ───────────────────────────────────────

def download_and_extract_pdf(pdf_url: str, max_chars: int = 8000) -> Optional[str]:
    """
    Download NSE PDF and extract text using pymupdf (fitz).
    Returns extracted text trimmed to max_chars, or None on failure.
    """
    if not pdf_url:
        return None
    try:
        import fitz  # pymupdf

        headers = {
            "User-Agent": _NSE_UA,
            "Referer": "https://www.nseindia.com/",
            "Accept": "application/pdf,*/*",
        }
        r = requests.get(pdf_url, headers=headers, timeout=15, stream=True)
        if r.status_code != 200:
            logger.warning("PDF download failed %s: HTTP %s", pdf_url, r.status_code)
            return None

        content = r.content
        if len(content) < 500:
            return None

        doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
        pages_text = []
        for page in doc:
            pages_text.append(page.get_text())
            if sum(len(t) for t in pages_text) > max_chars:
                break
        doc.close()

        text = "\n".join(pages_text).strip()
        return text[:max_chars] if text else None

    except Exception as e:
        logger.warning("PDF extraction failed %s: %s", pdf_url, e)
        return None


# ── Key number extraction ─────────────────────────────────────────────────

_NUMBER_PATTERNS = [
    # Revenue / turnover
    (r"(?:revenue|turnover|net sales)[^\d]{0,30}([\d,]+(?:\.\d+)?)\s*(?:crore|cr|lakh|mn|million|billion)?", "revenue"),
    # PAT / net profit
    (r"(?:net profit|pat|profit after tax)[^\d]{0,30}([\d,]+(?:\.\d+)?)\s*(?:crore|cr|lakh)?", "net_profit"),
    # EBITDA
    (r"ebitda[^\d]{0,20}([\d,]+(?:\.\d+)?)\s*(?:crore|cr)?", "ebitda"),
    # Order value
    (r"(?:order|contract|project)[^\d]{0,40}(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:crore|cr|lakh)", "order_value"),
    # Dividend
    (r"dividend[^\d]{0,20}(?:rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:per share|%)?", "dividend"),
    # Penalty / fine
    (r"(?:penalty|fine|demand)[^\d]{0,30}(?:rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)\s*(?:crore|cr|lakh)?", "penalty"),
    # EPS
    (r"(?:eps|earnings per share)[^\d]{0,20}(?:rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)", "eps"),
]


def extract_key_numbers(text: str) -> dict:
    """Extract financial numbers from PDF text using regex patterns."""
    text_lower = text.lower()
    numbers = {}
    for pattern, key in _NUMBER_PATTERNS:
        m = re.search(pattern, text_lower)
        if m:
            try:
                val_str = m.group(1).replace(",", "")
                numbers[key] = float(val_str)
            except (ValueError, IndexError):
                pass
    return numbers


# ── Sentiment classification ──────────────────────────────────────────────

_BULLISH_SIGNALS = [
    "record revenue", "record profit", "highest ever", "strong growth",
    "beat estimates", "above expectations", "order win", "order received",
    "new order", "contract awarded", "letter of award", "capacity expansion",
    "dividend declared", "bonus issue", "buyback", "promoter buying",
    "debt free", "zero debt", "strong demand", "market share gain",
    "revenue growth", "profit growth", "margin expansion", "ebitda growth",
    "qoq growth", "yoy growth", "beat", "outperform",
]

_BEARISH_SIGNALS = [
    "loss", "net loss", "decline", "fall", "drop", "below expectations",
    "miss", "disappointing", "weak demand", "margin pressure", "margin decline",
    "penalty", "fine", "sebi notice", "regulatory action", "fraud",
    "insolvency", "default", "npa", "write-off", "impairment",
    "resignation", "ceo resigned", "md resigned", "promoter selling",
    "debt increased", "leverage", "downgrade", "rating cut",
    "revenue decline", "profit decline", "loss widened",
]

_NEUTRAL_SIGNALS = [
    "in line with", "as expected", "meets estimates", "board meeting",
    "agm", "egm", "change in address", "appointment",
]


def classify_sentiment(text: str, key_numbers: dict) -> tuple[str, float]:
    """
    Returns (sentiment, score) where score is -1.0 to +1.0.
    """
    text_lower = text.lower()

    bull_hits = sum(1 for kw in _BULLISH_SIGNALS if kw in text_lower)
    bear_hits = sum(1 for kw in _BEARISH_SIGNALS if kw in text_lower)

    # Penalty/loss in numbers is a strong bearish signal
    if key_numbers.get("penalty") and key_numbers["penalty"] > 10:
        bear_hits += 3
    if "net_profit" in key_numbers and key_numbers["net_profit"] < 0:
        bear_hits += 3

    total = bull_hits + bear_hits
    if total == 0:
        return "NEUTRAL", 0.0

    score = (bull_hits - bear_hits) / total  # -1 to +1
    score = max(-1.0, min(1.0, score))

    if score > 0.2:
        sentiment = "BULLISH"
    elif score < -0.2:
        sentiment = "BEARISH"
    else:
        sentiment = "NEUTRAL"

    return sentiment, round(score, 3)


# ── Signal tags ───────────────────────────────────────────────────────────

def extract_signal_tags(text: str, key_numbers: dict, headline: str) -> list[str]:
    """Extract structured signal tags from text."""
    text_lower = (text + " " + headline).lower()
    tags = []

    if any(kw in text_lower for kw in ["beat", "above expectations", "record profit", "record revenue"]):
        tags.append("BEAT")
    if any(kw in text_lower for kw in ["miss", "below expectations", "disappointing", "weak"]):
        tags.append("MISS")
    if any(kw in text_lower for kw in ["order win", "order received", "contract awarded", "letter of award", "new order"]):
        tags.append("ORDER_WIN")
    if any(kw in text_lower for kw in ["penalty", "fine", "sebi notice", "regulatory"]):
        tags.append("REGULATORY_ACTION")
    if any(kw in text_lower for kw in ["dividend", "bonus", "buyback"]):
        tags.append("SHAREHOLDER_RETURN")
    if any(kw in text_lower for kw in ["acquisition", "merger", "takeover"]):
        tags.append("M&A")
    if any(kw in text_lower for kw in ["loss", "net loss", "loss widened"]):
        tags.append("LOSS_REPORTED")
    if any(kw in text_lower for kw in ["expansion", "capex", "new plant", "greenfield"]):
        tags.append("EXPANSION")
    if any(kw in text_lower for kw in ["debt", "ncd", "qip", "rights issue"]):
        tags.append("FUNDRAISE")
    if any(kw in text_lower for kw in ["promoter buying", "insider buying"]):
        tags.append("INSIDER_BUY")
    if any(kw in text_lower for kw in ["promoter selling", "insider selling"]):
        tags.append("INSIDER_SELL")

    return tags


# ── Summary generator ─────────────────────────────────────────────────────

def generate_summary(
    headline: str,
    sentiment: str,
    key_numbers: dict,
    signal_tags: list[str],
    text_snippet: str,
) -> str:
    """Generate a 2-3 line human-readable summary without LLM."""
    parts = [headline.strip()]

    if key_numbers:
        num_parts = []
        if "revenue" in key_numbers:
            num_parts.append(f"Revenue ₹{key_numbers['revenue']:,.0f} Cr")
        if "net_profit" in key_numbers:
            label = "Net Profit" if key_numbers["net_profit"] >= 0 else "Net Loss"
            num_parts.append(f"{label} ₹{abs(key_numbers['net_profit']):,.0f} Cr")
        if "order_value" in key_numbers:
            num_parts.append(f"Order ₹{key_numbers['order_value']:,.0f} Cr")
        if "dividend" in key_numbers:
            num_parts.append(f"Dividend ₹{key_numbers['dividend']}/share")
        if "penalty" in key_numbers:
            num_parts.append(f"Penalty ₹{key_numbers['penalty']:,.0f} Cr")
        if num_parts:
            parts.append(" | ".join(num_parts))

    if signal_tags:
        parts.append(f"Signals: {', '.join(signal_tags)}")

    return " • ".join(parts)


# ── Main entry point ──────────────────────────────────────────────────────

def analyze_filing(
    symbol: str,
    company: str,
    headline: str,
    category: str,
    impact: str,
    pdf_url: Optional[str],
    published_at: str,
    dedup_key: str,
) -> dict:
    """
    Full pipeline: filter → download → extract → classify → store.
    Returns a dict matching NseFilingAnalysis columns.
    """
    result = {
        "symbol": symbol,
        "company": company,
        "headline": headline,
        "category": category,
        "impact": impact,
        "pdf_url": pdf_url,
        "published_at": published_at,
        "dedup_key": dedup_key,
        "pdf_text": None,
        "pdf_extracted": False,
        "sentiment": "NEUTRAL",
        "sentiment_score": 0.0,
        "summary": headline,
        "key_numbers": "{}",
        "signal_tags": "",
        "passed_filter": False,
        "avg_volume": 0.0,
        "filter_reason": "",
    }

    # Step 1: operator filter
    passed, avg_vol, reason = passes_operator_filter(symbol)
    result["passed_filter"] = passed
    result["avg_volume"] = avg_vol
    result["filter_reason"] = reason

    if not passed:
        logger.info("Filing filtered out [%s]: %s", symbol, reason)
        return result

    # Step 2: PDF download + extraction
    text = None
    if pdf_url:
        text = download_and_extract_pdf(pdf_url)
        if text:
            result["pdf_text"] = text[:6000]  # store trimmed version
            result["pdf_extracted"] = True

    # Fall back to headline-only analysis if PDF unavailable
    analysis_text = text or headline

    # Step 3: extract numbers
    key_numbers = extract_key_numbers(analysis_text)
    result["key_numbers"] = json.dumps(key_numbers)

    # Step 4: sentiment
    sentiment, score = classify_sentiment(analysis_text, key_numbers)
    result["sentiment"] = sentiment
    result["sentiment_score"] = score

    # Step 5: signal tags
    tags = extract_signal_tags(analysis_text, key_numbers, headline)
    result["signal_tags"] = ",".join(tags)

    # Step 6: summary
    result["summary"] = generate_summary(headline, sentiment, key_numbers, tags, analysis_text[:500])

    logger.info(
        "Filing analysed [%s] %s → %s (score=%.2f) tags=%s pdf=%s",
        symbol, headline[:60], sentiment, score, tags, result["pdf_extracted"],
    )
    return result


def store_filing_analysis(result: dict) -> None:
    """Upsert filing analysis result into DB."""
    try:
        from app.db.session import SessionLocal
        from app.db.models_filing_analysis import NseFilingAnalysis

        db = SessionLocal()
        try:
            existing = (
                db.query(NseFilingAnalysis)
                .filter(NseFilingAnalysis.dedup_key == result["dedup_key"])
                .first()
            )
            if existing:
                for k, v in result.items():
                    if hasattr(existing, k):
                        setattr(existing, k, v)
            else:
                db.add(NseFilingAnalysis(**{k: v for k, v in result.items() if hasattr(NseFilingAnalysis, k)}))
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.error("store_filing_analysis failed: %s", e)
