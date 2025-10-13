#!/usr/bin/env python3
"""
SEC EDGAR Financial Data API
Fetches comprehensive financial metrics from SEC filings and Yahoo Finance.

Changes in this version:
- Robust Yahoo price fetch:
  * Prefer yfinance.fast_info -> yfinance.history -> Yahoo v7 quote JSON (no HTML scraping)
  * Normalize class-share tickers for Yahoo (e.g., BRK.B -> BRK-B)
  * Validate the returned symbol matches the requested
  * Choose the most relevant live price (post/pre/regular) with safe fallbacks
- Market cap sanity check vs. price * shares
- Minor hardening of SEC requests (headers) and sorting logic
"""

from __future__ import annotations
import requests
import yfinance as yf
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import math
import json
import re

# ----------------------------
# Configuration
# ----------------------------

SEC_SITE = "https://www.sec.gov"
SEC_DATA = "https://data.sec.gov"
USER_AGENT = "FinancialDataApp/1.0 (p.bierley@yahoo.com)"

TAG_CANDIDATES = {
    "cfo": [
        "us-gaap/NetCashProvidedByUsedInOperatingActivities",
        "us-gaap/NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": [
        "us-gaap/PaymentsToAcquirePropertyPlantAndEquipment",
        "us-gaap/PaymentsToAcquireProductiveAssets",
    ],
    "sbc": [
        "us-gaap/ShareBasedCompensation",
        "us-gaap/AllocatedShareBasedCompensationExpense",
    ],
    "eps": [
        "us-gaap/EarningsPerShareBasic",
        "us-gaap/EarningsPerShareDiluted",
    ],
    "shares": [
        # Commonly found in dei or us-gaap; we will search both group dicts.
        "EntityCommonStockSharesOutstanding",
        "CommonStockSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasic",
    ]
}

# ----------------------------
# HTTP Utilities
# ----------------------------

def _get_json(url: str) -> Any:
    """GET JSON with SEC-friendly headers."""
    resp = requests.get(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        },
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()

def _normalize_ticker(ticker: str) -> str:
    """Normalize ticker to uppercase without spaces."""
    return ticker.strip().upper()

def _normalize_cik(cik: str) -> str:
    """Convert CIK to zero-padded 10-digit string."""
    return cik.strip().zfill(10)

# ----------------------------
# SEC Data Retrieval
# ----------------------------

def get_cik_for_ticker(ticker: str) -> str:
    """Resolve ticker to CIK using SEC's company_tickers.json."""
    t = _normalize_ticker(ticker)
    data = _get_json(f"{SEC_SITE}/files/company_tickers.json")

    for _, row in data.items():
        if row.get("ticker", "").upper() == t:
            return str(row["cik_str"]).zfill(10)

    raise ValueError(f"Ticker not found: {t}")

def get_company_facts(cik: str) -> Dict[str, Any]:
    """Fetch complete Company Facts XBRL data."""
    url = f"{SEC_DATA}/api/xbrl/companyfacts/CIK{cik}.json"
    return _get_json(url)

def get_company_metadata(cik: str) -> Dict[str, Any]:
    """Fetch company metadata from SEC submissions."""
    url = f"{SEC_DATA}/submissions/CIK{cik}.json"
    data = _get_json(url)

    return {
        "cik": cik,
        "name": data.get("name"),
        "tickers": data.get("tickers", []),
        "sic": data.get("sic"),
        "sicDescription": data.get("sicDescription"),
    }

# ----------------------------
# XBRL Data Extraction
# ----------------------------

def _get_usd_observations(units_dict: dict) -> List[Dict[str, Any]]:
    """Extract observations with USD-like units."""
    if not isinstance(units_dict, dict):
        return []

    observations = []
    for unit_key, obs in units_dict.items():
        # Accept 'USD', 'iso4217:USD', etc.
        if "USD" in str(unit_key).upper() and isinstance(obs, list):
            observations.extend(obs)

    return observations

def _get_facts_for_tag(facts: Dict[str, Any], tag: str) -> List[Dict[str, Any]]:
    """Get fact observations for a specific tag 'taxonomy/name'."""
    taxonomy, name = tag.split("/", 1)
    series = facts.get("facts", {}).get(taxonomy, {}).get(name, {})
    units = series.get("units", {})
    return _get_usd_observations(units)

def _extract_annual_values(observations: List[Dict[str, Any]], years: int = 5) -> List[Dict[str, Any]]:
    """Extract annual (FY) values for the past N years."""
    annuals = [
        obs for obs in observations
        if obs.get("fp") == "FY" and isinstance(obs.get("val"), (int, float))
    ]

    # Sort most recent first by fiscal year then end-date
    annuals.sort(key=lambda x: (int(x.get("fy") or 0), x.get("end") or ""), reverse=True)

    result = []
    seen_years = set()
    for obs in annuals:
        yr = obs.get("fy")
        if yr in seen_years:
            continue
        seen_years.add(yr)
        result.append({
            "year": yr,
            "value": float(obs["val"]),
            "end_date": obs.get("end"),
            "filed": obs.get("filed")
        })
        if len(result) >= years:
            break

    return result

def _extract_quarterly_values(observations: List[Dict[str, Any]], quarters: int = 20) -> List[Dict[str, Any]]:
    """Extract quarterly values for the past N quarters."""
    quarterlies = [
        obs for obs in observations
        if obs.get("fp") in {"Q1", "Q2", "Q3", "Q4"} and isinstance(obs.get("val"), (int, float))
    ]

    # Sort most recent first
    quarterlies.sort(key=lambda x: (int(x.get("fy") or 0), x.get("end") or ""), reverse=True)

    result = []
    for obs in quarterlies[:quarters]:
        result.append({
            "year": obs.get("fy"),
            "quarter": obs.get("fp"),
            "value": float(obs["val"]),
            "end_date": obs.get("end"),
            "filed": obs.get("filed")
        })

    return result

def _try_multiple_tags(facts: Dict[str, Any], tags: List[str]) -> List[Dict[str, Any]]:
    """Try multiple tags and return first non-empty result."""
    for tag in tags:
        if "/" in tag:
            # Fully qualified (taxonomy/name)
            observations = _get_facts_for_tag(facts, tag)
        else:
            # Unqualified; search both dei and us-gaap groups by key name
            observations = []
            for taxonomy in ("dei", "us-gaap"):
                series = facts.get("facts", {}).get(taxonomy, {}).get(tag, {})
                units = series.get("units", {})
                observations.extend(_get_usd_observations(units))
        if observations:
            return observations
    return []

# ----------------------------
# Market Data (Yahoo)
# ----------------------------

def _yahoo_symbol(t: str) -> str:
    """Map common class-share formats to Yahoo’s symbol format."""
    t = t.upper().strip()
    # BRK.B -> BRK-B, RDS.A -> RDS-A, etc.
    t = t.replace(".", "-").replace("/", "-")
    return t

def _clean_symbol(s: Optional[str]) -> Optional[str]:
    return s.upper().replace(".", "-") if s else None

def get_yahoo_quote(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Fetch current quote using yfinance (fast_info/history) with fallback to Yahoo v7 quote API.
    Returns dict {price, currency, market_cap, exchange, source, symbol} or None.
    """
    ysym = _yahoo_symbol(ticker)

    # 1) yfinance fast_info
    try:
        tk = yf.Ticker(ysym)

        # Prefer fast_info
        fi = getattr(tk, "fast_info", None)
        if fi:
            price = getattr(fi, "last_price", None)
            currency = getattr(fi, "currency", None)
            market_cap = getattr(fi, "market_cap", None)
            exchange = getattr(fi, "exchange", None)
            if price and price > 0:
                return {
                    "price": float(price),
                    "currency": currency or "USD",
                    "market_cap": int(market_cap) if market_cap else None,
                    "exchange": exchange,
                    "source": "yfinance.fast_info",
                    "symbol": ysym
                }

        # Fallback: last close from 1d history
        hist = tk.history(period="1d", auto_adjust=False)
        if hasattr(hist, "empty") and not hist.empty:
            last = hist["Close"].iloc[-1]
            if isinstance(last, (int, float)) and last > 0:
                info = getattr(tk, "info", {}) or {}
                mc = info.get("marketCap")
                currency = info.get("currency") or "USD"
                exchange = info.get("exchange") or info.get("fullExchangeName")
                return {
                    "price": float(last),
                    "currency": currency,
                    "market_cap": int(mc) if mc else None,
                    "exchange": exchange,
                    "source": "yfinance.history",
                    "symbol": ysym
                }
    except Exception:
        # ignore and try HTTP fallback
        pass

    # 2) Yahoo v7 quote API
    try:
        url = "https://query1.finance.yahoo.com/v7/finance/quote"
        params = {"symbols": ysym}
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }
        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        result = (data.get("quoteResponse") or {}).get("result") or []
        if not result:
            return None

        q = result[0]
        # Validate symbol
        qsym = _clean_symbol(q.get("symbol"))
        if qsym != _clean_symbol(ysym):
            return None

        # Choose best live price
        candidates: List[Tuple[str, Any]] = [
            ("postMarketPrice", q.get("postMarketPrice")),
            ("preMarketPrice", q.get("preMarketPrice")),
            ("regularMarketPrice", q.get("regularMarketPrice")),
        ]
        price = next((float(v) for _, v in candidates if isinstance(v, (int, float)) and v > 0), None)
        if not price and isinstance(q.get("regularMarketPreviousClose"), (int, float)):
            price = float(q["regularMarketPreviousClose"])
        if not price or price <= 0:
            return None

        return {
            "price": price,
            "currency": q.get("currency") or "USD",
            "market_cap": int(q["marketCap"]) if isinstance(q.get("marketCap"), (int, float)) else None,
            "exchange": q.get("fullExchangeName") or q.get("exchange"),
            "source": "yahoo.v7",
            "symbol": qsym
        }
    except Exception:
        return None

# ----------------------------
# Shares (from SEC facts)
# ----------------------------

def get_shares_outstanding(facts: Dict[str, Any]) -> Optional[float]:
    """Extract most recent shares outstanding from SEC data."""
    dei_facts = facts.get("facts", {}).get("dei", {})
    us_gaap_facts = facts.get("facts", {}).get("us-gaap", {})
    all_facts = {**dei_facts, **us_gaap_facts}

    for tag in TAG_CANDIDATES["shares"]:
        if tag not in all_facts:
            continue

        units = all_facts[tag].get("units", {})
        shares_data = []

        # Look for 'shares' unit (case-insensitive)
        for unit_key, observations in units.items():
            if isinstance(unit_key, str) and "shares" in unit_key.lower() and isinstance(observations, list):
                shares_data.extend(observations)

        if not shares_data:
            continue

        # Sort by end date to get most recent
        shares_data.sort(key=lambda x: x.get("end", "") or "", reverse=True)

        for obs in shares_data:
            val = obs.get("val")
            if isinstance(val, (int, float)) and val > 0:
                return float(val)

    return None

def get_historical_shares(facts: Dict[str, Any], years: int = 5) -> List[Dict[str, Any]]:
    """Extract annual shares outstanding for past N years."""
    dei_facts = facts.get("facts", {}).get("dei", {})
    us_gaap_facts = facts.get("facts", {}).get("us-gaap", {})
    all_facts = {**dei_facts, **us_gaap_facts}

    for tag in TAG_CANDIDATES["shares"]:
        if tag not in all_facts:
            continue

        units = all_facts[tag].get("units", {})
        shares_data = []

        # Look for 'shares' unit
        for unit_key, observations in units.items():
            if isinstance(unit_key, str) and "shares" in unit_key.lower() and isinstance(observations, list):
                shares_data.extend(observations)

        if not shares_data:
            continue

        # Filter for annual/year-end data
        annual_shares = []
        for obs in shares_data:
            val = obs.get("val")
            fy = obs.get("fy")
            fp = obs.get("fp")

            if isinstance(val, (int, float)) and val > 0 and fy:
                if fp in ("FY", "Q4"):
                    annual_shares.append({
                        "year": fy,
                        "value": float(val),
                        "end_date": obs.get("end"),
                        "period": fp
                    })

        if annual_shares:
            # Sort by year & end-date, dedupe by year (keep most recent)
            annual_shares.sort(key=lambda x: (int(x["year"]), x["end_date"] or ""), reverse=True)
            seen_years = set()
            result = []
            for row in annual_shares:
                if row["year"] in seen_years:
                    continue
                seen_years.add(row["year"])
                result.append(row)
                if len(result) >= years:
                    break

            # return most recent first
            result.sort(key=lambda x: int(x["year"]), reverse=True)
            return result[:years]

    return []

# ----------------------------
# Main API Function
# ----------------------------

def get_financial_data(ticker: str) -> Dict[str, Any]:
    """
    Fetch comprehensive financial data for a stock.

    Returns JSON with:
    - Stock name, ticker, price, market cap
    - Quarterly EPS for past 5 years
    - Annual FCF, CapEx, SBC for past 5 years
    - Historical market cap for past 5 years (approx via current price * historical shares)
    """
    try:
        # Get CIK and metadata
        cik = get_cik_for_ticker(ticker)
        metadata = get_company_metadata(cik)
        facts = get_company_facts(cik)

        # Try to get market data from Yahoo (optional)
        market_data = get_yahoo_quote(ticker)

        # Get shares outstanding from SEC
        shares_outstanding = get_shares_outstanding(facts)
        historical_shares = get_historical_shares(facts, years=5)

        # Determine price and market cap
        price: Optional[float] = None
        market_cap: Optional[float] = None
        currency = "USD"
        exchange = None
        source = None
        notes: List[str] = []

        if market_data:
            price = market_data.get("price")
            market_cap = market_data.get("market_cap")
            currency = market_data.get("currency", "USD")
            exchange = market_data.get("exchange")
            source = market_data.get("source")

        # Compute market cap from shares if we have price & shares but no market cap
        if price and shares_outstanding:
            computed_mc = price * shares_outstanding
            if market_cap is None:
                market_cap = computed_mc
                notes.append("Market cap computed from price * SEC shares.")
            else:
                # If wildly different (>30%), prefer computed and record a note
                if abs(market_cap - computed_mc) / max(market_cap, 1) > 0.30:
                    market_cap = computed_mc
                    notes.append("Adjusted market cap to price * SEC shares (Yahoo value inconsistent).")

        # Extract EPS (quarterly, past 5 years = 20 quarters)
        eps_observations = _try_multiple_tags(facts, TAG_CANDIDATES["eps"])
        eps_quarterly = _extract_quarterly_values(eps_observations, quarters=20)

        # Extract annual metrics (past 5 years)
        cfo_observations = _try_multiple_tags(facts, TAG_CANDIDATES["cfo"])
        capex_observations = _try_multiple_tags(facts, TAG_CANDIDATES["capex"])
        sbc_observations = _try_multiple_tags(facts, TAG_CANDIDATES["sbc"])

        cfo_annual = _extract_annual_values(cfo_observations, years=5)
        capex_annual = _extract_annual_values(capex_observations, years=5)
        sbc_annual = _extract_annual_values(sbc_observations, years=5)

        # Calculate FCF for each year: FCF = CFO - CapEx
        fcf_annual = []
        for cfo_year in cfo_annual:
            year = cfo_year["year"]
            capex_year = next((c for c in capex_annual if c["year"] == year), None)
            if capex_year:
                fcf_value = cfo_year["value"] - capex_year["value"]
                fcf_annual.append({
                    "year": year,
                    "value": fcf_value,
                    "cfo": cfo_year["value"],
                    "capex": capex_year["value"]
                })

        # Historical market cap (approx: current price * historical shares)
        market_cap_annual = []
        if price and historical_shares:
            for share_data in historical_shares:
                market_cap_annual.append({
                    "year": share_data["year"],
                    "value": share_data["value"] * price,
                    "shares": share_data["value"],
                    "price_used": price,
                    "note": "Calculated using current price as approximation"
                })

        # Build API response
        response = {
            "status": "success",
            "data": {
                "stock_name": metadata.get("name"),
                "stock_ticker": _normalize_ticker(ticker),
                "stock_price": price,
                "currency": currency,
                "market_cap": market_cap,
                "shares_outstanding": shares_outstanding,
                "exchange": exchange,
                "price_source": source,
                "eps_quarterly": eps_quarterly,
                "free_cash_flow_annual": fcf_annual,
                "capex_annual": capex_annual,
                "stock_based_compensation_annual": sbc_annual,
                "market_cap_annual": market_cap_annual,
            },
            "metadata": {
                "cik": cik,
                "retrieved_at": datetime.utcnow().isoformat() + "Z",
                "data_sources": {
                    "fundamentals": "SEC EDGAR XBRL",
                    "market_data": f"Yahoo Finance via {source}" if source else "SEC EDGAR only"
                },
                "notes": " | ".join(
                    ["Historical market cap calculated using current price and historical shares as approximation."]
                    + notes
                )
            }
        }
        return response

    except Exception as e:
        return {
            "status": "error",
            "error": {
                "message": str(e),
                "type": type(e).__name__
            },
            "data": None
        }

# ----------------------------
# CLI Usage
# ----------------------------

if __name__ == "__main__":
    import argparse
    import json as _json

    parser = argparse.ArgumentParser(
        description="Fetch comprehensive financial data from SEC EDGAR and Yahoo Finance"
    )
    parser.add_argument("ticker", help="Stock ticker (e.g., AAPL, MSFT)")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON output")

    args = parser.parse_args()

    result = get_financial_data(args.ticker)

    if args.pretty:
        print(_json.dumps(result, indent=2))
    else:
        print(_json.dumps(result))
