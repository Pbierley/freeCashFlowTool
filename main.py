#!/usr/bin/env python3
"""
Minimal SEC EDGAR fetcher for FCF and SBC with resilient tag + unit handling.

- Accuracy-first: Pulls tagged XBRL facts directly from EDGAR.
- Single-responsibility functions with simple orchestration in `get_fcf_sbc_metrics`.
- Improvements:
  * Try multiple preferred tags per metric (CFO, CapEx, SBC).
  * Accept USD-like units (e.g., 'USD', 'iso4217:USD').
  * Keyword fallback scan when preferred tags are absent.
"""

from __future__ import annotations
import requests
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# ----------------------------
# Config
# ----------------------------

SEC_SITE = "https://www.sec.gov"   # for static files like company_tickers.json
SEC_DATA = "https://data.sec.gov"  # for API endpoints like /api/xbrl/companyfacts
USER_AGENT = "FreeCashFlowApp/1.0 (p.bierley@yahoo.com)"  # <-- use your contact

# Preferred tag lists (ordered)
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
        "us-gaap/StockBasedCompensation",
        "us-gaap/AllocatedShareBasedCompensationExpense",
        "us-gaap/ShareBasedCompensationExpense",
    ],
}

# ----------------------------
# Low-level HTTP + helpers
# ----------------------------

def _get_json(url: str) -> Any:
    """GET JSON with SEC-friendly headers."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    resp.raise_for_status()
    return resp.json()

def _normalize_ticker(ticker: str) -> str:
    """Uppercase, strip spaces."""
    return ticker.strip().upper()

# ----------------------------
# Ticker → CIK
# ----------------------------

def get_cik_for_ticker(ticker: str) -> str:
    """
    Resolve a ticker to a zero-padded 10-digit CIK using SEC's company_tickers.json.
    """
    t = _normalize_ticker(ticker)
    url = f"{SEC_SITE}/files/company_tickers.json"
    data = _get_json(url)

    # The JSON is an object with integer keys "0","1",... each value has 'cik_str','ticker','title'
    for _, row in data.items():
        if row.get("ticker", "").upper() == t:
            return str(row["cik_str"]).zfill(10)
    raise ValueError(f"Ticker not found in SEC mapping: {t}")

# ----------------------------
# Company Facts (XBRL)
# ----------------------------

def get_company_facts(cik: str) -> Dict[str, Any]:
    """Fetch the full Company Facts payload for the company."""
    url = f"{SEC_DATA}/api/xbrl/companyfacts/CIK{cik}.json"
    return _get_json(url)

def _get_usdish_units(units_dict: dict) -> List[Dict[str, Any]]:
    """
    Return observations from any unit key that looks like USD, e.g. 'USD', 'iso4217:USD'.
    """
    if not isinstance(units_dict, dict):
        return []
    candidates: List[Dict[str, Any]] = []
    for unit_key, obs in units_dict.items():
        key_upper = str(unit_key).upper()
        if "USD" in key_upper and isinstance(obs, list):
            candidates.extend(obs)
    return candidates

def _get_facts_units(facts: Dict[str, Any], tag: str) -> List[Dict[str, Any]]:
    """
    Return list of fact observations for the given tag (USD-like units only).
    Tag must be in 'namespace/name' form (e.g., 'us-gaap/StockBasedCompensation').
    """
    taxonomy, name = tag.split("/", 1)
    by_tax = facts.get("facts", {}).get(taxonomy, {})
    series = by_tax.get(name, {})
    units = series.get("units", {})
    return _get_usdish_units(units)  # list of dicts with 'fy','fp','val','end','form','frame', etc.

# ----------------------------
# Value selection logic
# ----------------------------

def _pick_latest_annual(values: List[Dict[str, Any]]) -> Optional[Tuple[float, Dict[str, Any]]]:
    """
    Choose the most recent annual (FY) value.
    Returns (value, meta) or None.
    """
    annuals = [v for v in values if v.get("fp") == "FY" and isinstance(v.get("val"), (int, float))]
    if not annuals:
        return None
    # Sort by fiscal year then end date
    annuals.sort(key=lambda v: (int(v.get("fy", 0) or 0), v.get("end", "")))
    latest = annuals[-1]
    return float(latest["val"]), latest

def _pick_ttm_from_quarters(values: List[Dict[str, Any]]) -> Optional[Tuple[float, List[Dict[str, Any]]]]:
    """
    Sum the last 4 quarterly (Q1/Q2/Q3/Q4) values as a simple TTM fallback.
    Returns (sum, quarters_meta) or None.
    """
    quarters = [v for v in values if v.get("fp") in {"Q1", "Q2", "Q3", "Q4"} and isinstance(v.get("val"), (int, float))]
    if len(quarters) < 1:
        return None
    def _parse_end(v):
        try:
            return datetime.fromisoformat(v.get("end", "1900-01-01"))
        except Exception:
            return datetime(1900, 1, 1)
    quarters.sort(key=_parse_end)
    last_four = quarters[-4:]
    total = sum(float(v["val"]) for v in last_four)
    return total, last_four

def _available_usgaap_fact_names(facts: Dict[str, Any]) -> List[str]:
    """List available us-gaap fact names (without the 'us-gaap/' prefix)."""
    return list((facts.get("facts", {}).get("us-gaap", {}) or {}).keys())

def _scan_for_keywords(facts: Dict[str, Any], keywords: List[str]) -> List[str]:
    """
    Return 'us-gaap/<name>' fact tags whose names contain ALL keywords (case-insensitive).
    """
    names = _available_usgaap_fact_names(facts)
    picks: List[str] = []
    for nm in names:
        up = nm.lower()
        if all(kw.lower() in up for kw in keywords):
            picks.append(f"us-gaap/{nm}")
    return picks

def select_value_multi(
    facts: Dict[str, Any],
    preferred_tags: List[str],
    keywords: List[str]
) -> Tuple[float, Dict[str, Any], str, str]:
    """
    Try preferred tags in order; if none has USD-like values, try a keyword scan.
    Returns (value, meta, basis, tag_used)
    """
    # 1) Try explicit preferred tags
    for tag in preferred_tags:
        vals = _get_facts_units(facts, tag)
        if vals:
            annual = _pick_latest_annual(vals)
            if annual:
                val, meta = annual
                return val, meta, "annual", tag
            ttm = _pick_ttm_from_quarters(vals)
            if ttm:
                val, meta_list = ttm
                return val, {"quarters": meta_list}, "ttm", tag

    # 2) Keyword fallback across all us-gaap facts
    for tag in _scan_for_keywords(facts, keywords):
        vals = _get_facts_units(facts, tag)
        if vals:
            annual = _pick_latest_annual(vals)
            if annual:
                val, meta = annual
                return val, meta, "annual", tag
            ttm = _pick_ttm_from_quarters(vals)
            if ttm:
                val, meta_list = ttm
                return val, {"quarters": meta_list}, "ttm", tag

    raise ValueError(f"No USD-like values for any tag matching {preferred_tags} or keywords={keywords}")

# ----------------------------
# Domain calculations
# ----------------------------

def compute_fcf(cfo: float, capex: float) -> float:
    """FCF = Cash Flow from Operations − Capital Expenditures."""
    return float(cfo) - float(capex)

def compute_fcf_minus_sbc(fcf: float, sbc: float) -> float:
    """FCF − Stock-Based Compensation."""
    return float(fcf) - float(sbc)

# ----------------------------
# Orchestration
# ----------------------------

def get_fcf_sbc_metrics(ticker: str) -> Dict[str, Any]:
    """
    High-level function that:
      1) maps ticker→CIK
      2) fetches company facts
      3) extracts CFO, CapEx, SBC (resilient selection)
      4) computes FCF and FCF − SBC
    Returns a dict with values and provenance.
    """
    cik = get_cik_for_ticker(ticker)
    facts = get_company_facts(cik)

    # CFO
    cfo, cfo_meta, cfo_basis, cfo_tag = select_value_multi(
        facts,
        TAG_CANDIDATES["cfo"],
        keywords=["net", "cash", "operating", "activities"]
    )

    # CapEx
    capex, capex_meta, capex_basis, capex_tag = select_value_multi(
        facts,
        TAG_CANDIDATES["capex"],
        keywords=["payments", "acquire", "property", "plant", "equipment"]
    )

    # SBC
    sbc, sbc_meta, sbc_basis, sbc_tag = select_value_multi(
        facts,
        TAG_CANDIDATES["sbc"],
        keywords=["share", "based", "compensation"]
    )

    fcf = compute_fcf(cfo, capex)
    fcf_minus_sbc = compute_fcf_minus_sbc(fcf, sbc)

    return {
        "ticker": _normalize_ticker(ticker),
        "cik": cik,
        "values": {
            "cfo":  {"value": cfo,  "basis": cfo_basis,  "meta": cfo_meta,  "tag": cfo_tag},
            "capex":{"value": capex,"basis": capex_basis,"meta": capex_meta,"tag": capex_tag},
            "sbc":  {"value": sbc,  "basis": sbc_basis,  "meta": sbc_meta,  "tag": sbc_tag},
            "fcf": {"value": fcf, "formula": "CFO - CapEx"},
            "fcf_minus_sbc": {"value": fcf_minus_sbc, "formula": "(CFO - CapEx) - SBC"},
        },
        "source": {
            "mapping": f"{SEC_SITE}/files/company_tickers.json",
            "facts": f"{SEC_DATA}/api/xbrl/companyfacts/CIK{cik}.json",
            "notes": "Values selected via preferred tag list with keyword fallback; USD-like units only."
        },
    }

# ----------------------------
# CLI usage
# ----------------------------

if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser(description="Fetch FCF and SBC from SEC EDGAR (XBRL).")
    parser.add_argument("ticker", help="Stock ticker, e.g., AAPL")
    args = parser.parse_args()

    try:
        result = get_fcf_sbc_metrics(args.ticker)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        raise
