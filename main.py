#!/usr/bin/env python3
"""
SEC EDGAR Financial Data API
Fetches comprehensive financial metrics from SEC filings and Yahoo Finance.
"""

from __future__ import annotations
import requests
import yfinance as yf
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import math

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
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
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
    """Extract observations with USD units."""
    if not isinstance(units_dict, dict):
        return []
    
    observations = []
    for unit_key, obs in units_dict.items():
        if "USD" in str(unit_key).upper() and isinstance(obs, list):
            observations.extend(obs)
    
    return observations

def _get_facts_for_tag(facts: Dict[str, Any], tag: str) -> List[Dict[str, Any]]:
    """Get fact observations for a specific tag."""
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
    
    annuals.sort(key=lambda x: (int(x.get("fy", 0) or 0), x.get("end", "")), reverse=True)
    
    result = []
    for obs in annuals[:years]:
        result.append({
            "year": obs.get("fy"),
            "value": float(obs["val"]),
            "end_date": obs.get("end"),
            "filed": obs.get("filed")
        })
    
    return result

def _extract_quarterly_values(observations: List[Dict[str, Any]], quarters: int = 20) -> List[Dict[str, Any]]:
    """Extract quarterly values for the past N quarters."""
    quarterlies = [
        obs for obs in observations 
        if obs.get("fp") in {"Q1", "Q2", "Q3", "Q4"} and isinstance(obs.get("val"), (int, float))
    ]
    
    quarterlies.sort(key=lambda x: (int(x.get("fy", 0) or 0), x.get("end", "")), reverse=True)
    
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
        observations = _get_facts_for_tag(facts, tag)
        if observations:
            return observations
    return []

# ----------------------------
# Market Data
# ----------------------------

def get_shares_outstanding(facts: Dict[str, Any]) -> Optional[float]:
    """Extract most recent shares outstanding from SEC data."""
    # Try DEI (Document and Entity Information) first
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
            if "shares" in unit_key.lower() and isinstance(observations, list):
                shares_data.extend(observations)
        
        if not shares_data:
            continue
        
        # Sort by end date to get most recent
        shares_data.sort(key=lambda x: x.get("end", ""), reverse=True)
        
        for obs in shares_data:
            val = obs.get("val")
            if isinstance(val, (int, float)) and val > 0:
                return float(val)
    
    return None

def get_yahoo_quote(ticker: str) -> Dict[str, Any]:
    """Fetch current quote from Yahoo Finance. Returns None if unavailable."""
    try:
        # Try alternate scraping method with requests
        url = f"https://finance.yahoo.com/quote/{ticker}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        # Simple parsing - look for price in the response
        # This is a fallback and may not always work
        if response.status_code == 200:
            import re
            # Try to find price patterns in the HTML
            price_pattern = r'"regularMarketPrice":\{"raw":([\d.]+)'
            market_cap_pattern = r'"marketCap":\{"raw":(\d+)'
            
            price_match = re.search(price_pattern, response.text)
            cap_match = re.search(market_cap_pattern, response.text)
            
            if price_match:
                return {
                    "price": float(price_match.group(1)),
                    "currency": "USD",
                    "market_cap": int(cap_match.group(1)) if cap_match else None,
                    "exchange": None,
                }
        
        return None
        
    except Exception:
        return None

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
        
        # Determine price and market cap
        price = None
        market_cap = None
        currency = "USD"
        exchange = None
        
        if market_data:
            price = market_data.get("price")
            market_cap = market_data.get("market_cap")
            currency = market_data.get("currency", "USD")
            exchange = market_data.get("exchange")
        
        # Calculate market cap from shares if we have price and shares but no market cap
        if market_cap is None and price and shares_outstanding:
            market_cap = price * shares_outstanding
        
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
        
        # Calculate FCF for each year
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
                "eps_quarterly": eps_quarterly,
                "free_cash_flow_annual": fcf_annual,
                "capex_annual": capex_annual,
                "stock_based_compensation_annual": sbc_annual,
            },
            "metadata": {
                "cik": cik,
                "retrieved_at": datetime.utcnow().isoformat() + "Z",
                "data_sources": {
                    "fundamentals": "SEC EDGAR XBRL",
                    "market_data": "Yahoo Finance (when available)" if market_data else "SEC EDGAR only"
                },
                "notes": "Market data may be limited. Price and market cap from SEC when Yahoo unavailable."
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
    import json
    
    parser = argparse.ArgumentParser(
        description="Fetch comprehensive financial data from SEC EDGAR and Yahoo Finance"
    )
    parser.add_argument("ticker", help="Stock ticker (e.g., AAPL, MSFT)")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON output")
    
    args = parser.parse_args()
    
    result = get_financial_data(args.ticker)
    
    if args.pretty:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result))