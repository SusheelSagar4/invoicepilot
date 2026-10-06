"""
Independent Verifier Module for InvoicePilot.
Validates recorded finance database entries against remembered agent facts and
against the Invoice Portal source of truth via API endpoints.
Operates independently without using browser DOM or Playwright.
"""

import re
from datetime import datetime
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


def _parse_issue_date(date_str: str) -> datetime:
    """Parse issue_date ISO string (YYYY-MM-DD) or fallback."""
    try:
        return datetime.strptime(str(date_str).strip(), "%Y-%m-%d")
    except Exception:
        return datetime.min


def verify_finance_record(facts: Dict[str, str], check_latest: bool = True) -> Dict[str, Any]:
    """
    Verify stored finance system record against remembered agent facts and source invoice portal.

    Args:
        facts: Memory facts dictionary stored by agent (e.g. invoice_number, vendor, amount, due_date).
        check_latest: If True, verifies that recorded invoice is the latest by issue_date for that vendor.

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

    # 1. Invoice Number Check (Facts vs Finance DB)
    exp_inv = invoice_num.upper()
    act_inv = str(rec.get("invoice_number", "")).strip().upper()
    checks.append({
        "name": "invoice_number",
        "expected": invoice_num,
        "actual": rec.get("invoice_number"),
        "ok": exp_inv == act_inv
    })

    # 2. Vendor Name Check (Facts vs Finance DB)
    exp_vendor = (facts.get("vendor") or "").strip().lower()
    act_vendor = str(rec.get("vendor", "")).strip().lower()
    checks.append({
        "name": "vendor",
        "expected": facts.get("vendor"),
        "actual": rec.get("vendor"),
        "ok": exp_vendor == act_vendor and bool(exp_vendor)
    })

    # 3. Amount Check (Facts vs Finance DB)
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

    # 4. Due Date Check (Facts vs Finance DB)
    exp_date = (facts.get("due_date") or "").strip()
    act_date = str(rec.get("due_date", "")).strip()
    checks.append({
        "name": "due_date",
        "expected": exp_date,
        "actual": act_date,
        "ok": exp_date == act_date and bool(exp_date)
    })

    # Query Source Invoice Portal (Port 8001) for source invoice verification
    src_url = f"http://localhost:8001/api/invoices/{invoice_num}"
    try:
        src_resp = requests.get(src_url, timeout=5)
        if src_resp.status_code == 200:
            src_inv = src_resp.json()

            # 5. Source Vendor Check (Portal Source vs Finance DB)
            exp_src_v = src_inv.get("vendor")
            act_v = rec.get("vendor")
            src_v_ok = bool(exp_src_v) and str(exp_src_v).strip().lower() == str(act_v).strip().lower()
            checks.append({
                "name": "source_vendor",
                "expected": exp_src_v,
                "actual": act_v,
                "ok": src_v_ok
            })

            # 6. Source Amount Check (Portal Source vs Finance DB)
            exp_src_amt = _normalize_amount(src_inv.get("amount"))
            src_amt_ok = False
            if exp_src_amt is not None and act_amt is not None:
                src_amt_ok = abs(exp_src_amt - act_amt) < 0.01
            checks.append({
                "name": "source_amount",
                "expected": exp_src_amt,
                "actual": act_amt,
                "ok": src_amt_ok
            })

            # 7. Source Due Date Check (Portal Source vs Finance DB)
            exp_src_due = str(src_inv.get("due_date", "")).strip()
            checks.append({
                "name": "source_due_date",
                "expected": exp_src_due,
                "actual": act_date,
                "ok": exp_src_due == act_date and bool(exp_src_due)
            })
        else:
            checks.append({"name": "source_vendor", "expected": f"HTTP 200 from {src_url}", "actual": f"HTTP {src_resp.status_code}", "ok": False})
            checks.append({"name": "source_amount", "expected": "Valid source invoice", "actual": "None", "ok": False})
            checks.append({"name": "source_due_date", "expected": "Valid source invoice", "actual": "None", "ok": False})
    except Exception as e:
        checks.append({"name": "source_vendor", "expected": "Portal API response", "actual": str(e), "ok": False})
        checks.append({"name": "source_amount", "expected": "Portal API response", "actual": str(e), "ok": False})
        checks.append({"name": "source_due_date", "expected": "Portal API response", "actual": str(e), "ok": False})

    # Check if recorded invoice is the latest invoice for vendor
    if check_latest:
        v_param = rec.get("vendor") or facts.get("vendor") or ""
        v_url = f"http://localhost:8001/api/invoices?vendor={v_param}"
        try:
            v_resp = requests.get(v_url, timeout=5)
            if v_resp.status_code == 200:
                v_invoices = v_resp.json()
                if v_invoices:
                    # Sort by issue_date descending
                    v_invoices.sort(key=lambda x: _parse_issue_date(x.get("issue_date", "")), reverse=True)
                    latest_inv = v_invoices[0]
                    exp_latest_num = str(latest_inv.get("invoice_number", "")).strip().upper()
                    latest_ok = (act_inv == exp_latest_num)
                    checks.append({
                        "name": "source_latest_invoice",
                        "expected": latest_inv.get("invoice_number"),
                        "actual": rec.get("invoice_number"),
                        "ok": latest_ok
                    })
                else:
                    checks.append({"name": "source_latest_invoice", "expected": "Vendor invoices list", "actual": "Empty list", "ok": False})
            else:
                checks.append({"name": "source_latest_invoice", "expected": f"HTTP 200 from {v_url}", "actual": f"HTTP {v_resp.status_code}", "ok": False})
        except Exception as e:
            checks.append({"name": "source_latest_invoice", "expected": "Portal Vendor API response", "actual": str(e), "ok": False})

    all_passed = all(c["ok"] for c in checks)
    reason = "All checks passed successfully." if all_passed else "One or more verification checks failed."

    return {
        "passed": all_passed,
        "checks": checks,
        "record_id": record_id,
        "reason": reason
    }
