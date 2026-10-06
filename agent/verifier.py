"""
Independent Verifier Module for InvoicePilot.
Validates recorded finance database entries against remembered agent facts via API endpoint.
Operates independently without using browser DOM or Playwright.
"""

import re
from typing import Dict, Any, List, Optional
import requests


def _normalize_amount(val: Any) -> Optional[float]:
    """Strip currency symbols, commas, and spaces, converting value to float."""
    if val is None:
        return None
    try:
        cleaned = re.sub(r"[^\d.]", "", str(val))
        return float(cleaned) if cleaned else None
    except Exception:
        return None


def verify_finance_record(facts: Dict[str, str]) -> Dict[str, Any]:
    """
    Verify stored finance system record against remembered agent facts.

    Args:
        facts: Memory facts dictionary stored by agent (e.g. invoice_number, vendor, amount, due_date).

    Returns:
        Dict containing:
        {
            "passed": bool,
            "checks": [{"name": str, "expected": Any, "actual": Any, "ok": bool}],
            "record_id": Optional[str],
            "reason": str
        }
    """
    invoice_num = (facts.get("invoice_number") or "").strip()
    if not invoice_num:
        return {
            "passed": False,
            "checks": [],
            "record_id": None,
            "reason": "Missing 'invoice_number' in remembered agent facts."
        }

    api_url = f"http://localhost:8002/api/records/{invoice_num}"
    try:
        resp = requests.get(api_url, timeout=5)
        if resp.status_code == 404:
            return {
                "passed": False,
                "checks": [],
                "record_id": None,
                "reason": f"Invoice record '{invoice_num}' not found in finance system (HTTP 404)."
            }
        if resp.status_code != 200:
            return {
                "passed": False,
                "checks": [],
                "record_id": None,
                "reason": f"HTTP {resp.status_code} returned from verifier API endpoint."
            }

        rec = resp.json()
    except Exception as e:
        return {
            "passed": False,
            "checks": [],
            "record_id": None,
            "reason": f"Failed to query verifier API: {str(e)}"
        }

    record_id = rec.get("record_id")
    checks: List[Dict[str, Any]] = []

    # 1. Invoice Number Check
    exp_inv = invoice_num.upper()
    act_inv = str(rec.get("invoice_number", "")).strip().upper()
    checks.append({
        "name": "invoice_number",
        "expected": invoice_num,
        "actual": rec.get("invoice_number"),
        "ok": exp_inv == act_inv
    })

    # 2. Vendor Name Check (Case-insensitive comparison)
    exp_vendor = (facts.get("vendor") or "").strip().lower()
    act_vendor = str(rec.get("vendor", "")).strip().lower()
    checks.append({
        "name": "vendor",
        "expected": facts.get("vendor"),
        "actual": rec.get("vendor"),
        "ok": exp_vendor == act_vendor and bool(exp_vendor)
    })

    # 3. Amount Check (Numerical comparison)
    exp_amt = _normalize_amount(facts.get("amount"))
    act_amt = _normalize_amount(rec.get("amount"))
    amt_ok = False
    if exp_amt is not None and act_amt is not None:
        amt_ok = abs(exp_amt - act_amt) < 0.01

    checks.append({
        "name": "amount",
        "expected": exp_amt,
        "actual": act_amt,
        "ok": amt_ok
    })

    # 4. Due Date Check (ISO YYYY-MM-DD string match)
    exp_date = (facts.get("due_date") or "").strip()
    act_date = str(rec.get("due_date", "")).strip()
    checks.append({
        "name": "due_date",
        "expected": exp_date,
        "actual": act_date,
        "ok": exp_date == act_date and bool(exp_date)
    })

    all_passed = all(c["ok"] for c in checks)
    reason = "All checks passed successfully." if all_passed else "One or more verification checks failed."

    return {
        "passed": all_passed,
        "checks": checks,
        "record_id": record_id,
        "reason": reason
    }
