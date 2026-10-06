"""
Manual End-to-End Browser Tool Test.
Operates BrowserTools directly without any LLM calls to verify page navigation,
element tagging, form submission, date filling, and chaos failure handling.
"""

import sys
import os
import urllib.request
import json
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.browser import BrowserTools


def print_step(title: str, result: dict):
    """Utility helper to print observation outputs clearly."""
    print(f"\n==================== {title} ====================")
    print(f"OK: {result.get('ok')}")
    if result.get('error'):
        print(f"ERROR: {result.get('error')}")
    print(f"OBSERVATION:\n{result.get('observation')}")


def find_element_id(read_result: dict, label_substring: str) -> int:
    """Helper to find an element ID by label or placeholder matching."""
    obs = read_result.get("observation", "")
    for line in obs.splitlines():
        if label_substring.lower() in line.lower() and line.startswith("["):
            # Extract number inside brackets e.g. [2] -> 2
            try:
                elem_id = int(line.split("]")[0].replace("[", ""))
                return elem_id
            except Exception:
                pass
    raise ValueError(f"Could not find element matching '{label_substring}' in observation:\n{obs}")


def main():
    browser = BrowserTools(headless=False, slow_mo=300)
    try:
        # Step 1: Goto Invoice Portal
        r1 = browser.goto("http://localhost:8001")
        print_step("1. Goto Portal", r1)

        # Step 2: Read Portal Home Page
        r2 = browser.read_page()
        print_step("2. Read Portal Page", r2)

        # Step 3: Type "acme" into Search Box
        search_input_id = find_element_id(r2, "input:text")
        r3 = browser.type_text(search_input_id, "acme")
        print_step("3. Type Search Query", r3)

        # Step 4: Click Search Button
        search_btn_id = find_element_id(r2, "Search")
        r4 = browser.click(search_btn_id)
        print_step("4. Click Search Button", r4)

        # Step 5: Read Search Results Page
        r5 = browser.read_page()
        print_step("5. Read Search Results", r5)

        # Step 6: Click First Invoice Details Link
        link_id = find_element_id(r5, "View Details")
        r6 = browser.click(link_id)
        print_step("6. Click Invoice Link", r6)

        # Step 7: Read Invoice Detail Page
        r7 = browser.read_page()
        print_step("7. Read Invoice Details", r7)

        # Step 8: Goto Finance System
        r8 = browser.goto("http://localhost:8002")
        print_step("8. Goto Finance System", r8)

        # Step 9: Read Finance Form Page
        r9 = browser.read_page()
        print_step("9. Read Finance Form", r9)

        # Step 10: Fill Form Fields
        inv_input_id = find_element_id(r9, "Invoice Number")
        vendor_input_id = find_element_id(r9, "Vendor Name")
        amount_input_id = find_element_id(r9, "Amount")
        date_input_id = find_element_id(r9, "Due Date")

        browser.type_text(inv_input_id, "INV-2026-003")
        browser.type_text(vendor_input_id, "Acme Technologies")
        browser.type_text(amount_input_id, "62400")
        r_date = browser.type_text(date_input_id, "2026-10-30")
        print_step("10. Fill Form Fields", r_date)

        # Step 11: Submit Form & Read Success Page
        submit_btn_id = find_element_id(r9, "Submit")
        r11_click = browser.click(submit_btn_id)
        print_step("11. Click Submit", r11_click)

        r11_read = browser.read_page()
        print_step("11. Read Success Page", r11_read)

        # Step 12: Trigger Chaos Switch on Invoice Portal (POST /admin/chaos fail_next=1)
        print("\n==================== 12. Trigger Chaos Switch ====================")
        req = urllib.request.Request(
            "http://localhost:8001/admin/chaos",
            data=json.dumps({"fail_next": 1}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req) as resp:
            print("Chaos endpoint response:", resp.read().decode())

        # Step 13: Attempt Search on Portal during active chaos (Expect HTTP 503 handled gracefully)
        r13 = browser.goto("http://localhost:8001/search?q=acme")
        print_step("13. Search during Chaos (Expected HTTP 503 returned as ok=False)", r13)

    finally:
        browser.close()


if __name__ == "__main__":
    main()
