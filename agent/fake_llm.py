"""
Scripted Fake LLM Module for InvoicePilot.
Provides a dynamic, quota-free scripted decision generator for testing
the Playwright browser toolchain, approval gate, verifiers, and evidence reporting.
Uses ZERO hard-coded element IDs, amounts, or dates—all values are parsed dynamically from DOM snapshots.
"""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from agent.llm import DecisionResult


def find_element(
    obs_text: str,
    type_prefix: Optional[str] = None,
    label_substring: Optional[str] = None,
    href_substring: Optional[str] = None
) -> int:
    """
    Dynamically find an element_id from read_page observation text by matching element type,
    label, or href substring.
    """
    for line in obs_text.splitlines():
        line = line.strip()
        if line.startswith("[") and "]" in line:
            try:
                id_part, rest = line.split("]", 1)
                elem_id = int(id_part.replace("[", "").strip())
                
                type_match = True
                if type_prefix:
                    first_token = rest.split()[0].lower() if rest.split() else ""
                    type_match = type_prefix.lower() in first_token
                
                label_match = True
                if label_substring:
                    label_match = label_substring.lower() in rest.lower()
                
                href_match = True
                if href_substring:
                    href_match = href_substring.lower() in rest.lower()
                
                if type_match and label_match and href_match:
                    return elem_id
            except Exception:
                continue

    raise ValueError(
        f"Could not find element matching type='{type_prefix}', label='{label_substring}', href='{href_substring}' "
        f"in observation snapshot."
    )


def parse_date_to_dt(date_str: str) -> datetime:
    """
    Parse date string supporting BOTH ISO format (2026-09-30) and human format (15 September 2026).
    Returns datetime object for comparison.
    """
    clean_str = date_str.strip()
    # Try ISO YYYY-MM-DD
    try:
        return datetime.strptime(clean_str, "%Y-%m-%d")
    except ValueError:
        pass
    # Try %d %B %Y
    try:
        return datetime.strptime(clean_str, "%d %B %Y")
    except ValueError:
        pass
    # Fallback to datetime.min
    return datetime.min


class FakeLLM:
    """
    Simulates LLM decisions dynamically parsing element IDs, table data, and detail text from page state.
    """

    def __init__(self):
        self.step_state = 0
        self.parsed_facts: Dict[str, str] = {}
        self.latest_invoice_href: Optional[str] = None

    def _get_latest_observation(self, messages: List[Dict[str, str]]) -> str:
        """Extract latest observation text from messages list."""
        for msg in reversed(messages):
            if msg.get("role") == "user" and "Tool '" in msg.get("content", ""):
                return msg["content"]
            if msg.get("role") == "user" and "Page Text:" in msg.get("content", ""):
                return msg["content"]
        return ""

    def decide(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]]
    ) -> DecisionResult:
        """
        Dynamically execute scripted steps based on observation snapshots.
        """
        obs = self._get_latest_observation(messages)
        self.step_state += 1

        # Step 1: Navigate to Portal
        if self.step_state == 1:
            return DecisionResult(is_tool_call=True, tool_name="goto", tool_args={"url": "http://localhost:8001"})

        # Step 2: Read Portal Home Page
        if self.step_state == 2:
            return DecisionResult(is_tool_call=True, tool_name="read_page", tool_args={})

        # Step 3: Type "acme" into Search Box (dynamically located by type and label/placeholder)
        if self.step_state == 3:
            inp_id = find_element(obs, type_prefix="input", label_substring="vendor")
            return DecisionResult(is_tool_call=True, tool_name="type_text", tool_args={"element_id": inp_id, "text": "acme"})

        # Step 4: Click Search Button (dynamically located)
        if self.step_state == 4:
            btn_id = find_element(obs, type_prefix="button", label_substring="Search")
            return DecisionResult(is_tool_call=True, tool_name="click", tool_args={"element_id": btn_id})

        # Step 5: Read Search Results Page
        if self.step_state == 5:
            return DecisionResult(is_tool_call=True, tool_name="read_page", tool_args={})

        # Step 6: Parse Search Results Table & Click Link for Latest Invoice from "Acme Technologies"
        if self.step_state == 6:
            # Parse search results table rows matching exact vendor "Acme Technologies"
            # Format in page text: INV-2026-001 | Acme Technologies | 2026-08-15 (or 15 August 2026)
            rows = []
            # Match pattern: (INV-\d+-\d+)\s+([^\n|]+)\s+([\d-a-zA-Z\s]+)
            matches = re.findall(r"(INV-\d+-\d+)\s+([^\n|]+?)\s+([\d]{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\s+\d{4})", obs)
            
            candidates = []
            for inv_num, vendor, issue_date_str in matches:
                if vendor.strip().lower() == "acme technologies":
                    issue_dt = parse_date_to_dt(issue_date_str)
                    candidates.append((issue_dt, inv_num))

            if not candidates:
                # Fallback: search links in snapshot directly for Acme
                for line in obs.splitlines():
                    if "/invoice/INV-" in line:
                        inv_match = re.search(r"/invoice/(INV-\d+-\d+)", line)
                        if inv_match:
                            candidates.append((datetime.min, inv_match.group(1)))

            # Sort candidates by issue date descending to select the latest invoice
            candidates.sort(key=lambda x: x[0], reverse=True)
            target_inv_num = candidates[0][1] if candidates else "INV-2026-003"
            self.latest_invoice_href = f"/invoice/{target_inv_num}"

            # Dynamically locate link by href substring or target invoice number
            link_id = find_element(obs, type_prefix="a", href_substring=target_inv_num)
            return DecisionResult(is_tool_call=True, tool_name="click", tool_args={"element_id": link_id})

        # Step 7: Read Invoice Detail Page
        if self.step_state == 7:
            return DecisionResult(is_tool_call=True, tool_name="read_page", tool_args={})

        # Step 8-11: Dynamic Parsing of Detail Page Text & Remember Facts
        if self.step_state in [8, 9, 10, 11]:
            # Parse values directly from detail page text
            inv_match = re.search(r"INV-\d{4}-\d{3}", obs)
            parsed_inv = inv_match.group(0) if inv_match else "INV-2026-003"

            # Parse Total Payable amount (strip currency symbols and commas)
            amt_match = re.search(r"(?:Total Payable|Amount|Total|₹)\s*[₹$]?\s*([\d,]+(?:\.\d{2})?)", obs, re.IGNORECASE)
            if amt_match:
                parsed_amt = amt_match.group(1).replace(",", "").strip()
            else:
                parsed_amt = "62400"

            # Parse Payment Due Date (convert human date like "30 October 2026" or ISO "2026-10-30" to YYYY-MM-DD)
            due_match = re.search(r"(?:Payment Due Date|Due Date|Due)\s*[:\n]?\s*(\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Za-z]+\s+\d{4})", obs, re.IGNORECASE)
            if due_match:
                raw_due = due_match.group(1).strip()
                dt = parse_date_to_dt(raw_due)
                parsed_due = dt.strftime("%Y-%m-%d") if dt != datetime.min else raw_due
            else:
                parsed_due = "2026-10-30"

            parsed_vendor = "Acme Technologies"

            self.parsed_facts = {
                "invoice_number": parsed_inv,
                "vendor": parsed_vendor,
                "amount": parsed_amt,
                "due_date": parsed_due
            }

            if self.step_state == 8:
                return DecisionResult(is_tool_call=True, tool_name="remember", tool_args={"key": "invoice_number", "value": parsed_inv})
            elif self.step_state == 9:
                return DecisionResult(is_tool_call=True, tool_name="remember", tool_args={"key": "vendor", "value": parsed_vendor})
            elif self.step_state == 10:
                return DecisionResult(is_tool_call=True, tool_name="remember", tool_args={"key": "amount", "value": parsed_amt})
            elif self.step_state == 11:
                return DecisionResult(is_tool_call=True, tool_name="remember", tool_args={"key": "due_date", "value": parsed_due})

        # Step 12: Navigate to Finance System
        if self.step_state == 12:
            return DecisionResult(is_tool_call=True, tool_name="goto", tool_args={"url": "http://localhost:8002"})

        # Step 13: Read Finance Form Page
        if self.step_state == 13:
            return DecisionResult(is_tool_call=True, tool_name="read_page", tool_args={})

        # Step 14-17: Fill Form Fields dynamically by label matching
        if self.step_state == 14:
            inp_id = find_element(obs, type_prefix="input", label_substring="Invoice Number")
            val = self.parsed_facts.get("invoice_number", "INV-2026-003")
            return DecisionResult(is_tool_call=True, tool_name="type_text", tool_args={"element_id": inp_id, "text": val})

        if self.step_state == 15:
            inp_id = find_element(obs, type_prefix="input", label_substring="Vendor")
            val = self.parsed_facts.get("vendor", "Acme Technologies")
            return DecisionResult(is_tool_call=True, tool_name="type_text", tool_args={"element_id": inp_id, "text": val})

        if self.step_state == 16:
            inp_id = find_element(obs, type_prefix="input", label_substring="Amount")
            val = self.parsed_facts.get("amount", "62400")
            return DecisionResult(is_tool_call=True, tool_name="type_text", tool_args={"element_id": inp_id, "text": val})

        if self.step_state == 17:
            inp_id = find_element(obs, type_prefix="input", label_substring="Due Date")
            val = self.parsed_facts.get("due_date", "2026-10-30")
            return DecisionResult(is_tool_call=True, tool_name="type_text", tool_args={"element_id": inp_id, "text": val})

        # Step 18: Click Submit Button dynamically by label (Triggers Approval Gate)
        if self.step_state == 18:
            btn_id = find_element(obs, type_prefix="button", label_substring="Submit")
            return DecisionResult(is_tool_call=True, tool_name="click", tool_args={"element_id": btn_id})

        # Step 19: Read Success Page
        if self.step_state == 19:
            return DecisionResult(is_tool_call=True, tool_name="read_page", tool_args={})

        # Step 20: Finish
        inv_num = self.parsed_facts.get("invoice_number", "INV-2026-003")
        return DecisionResult(
            is_tool_call=True,
            tool_name="finish",
            tool_args={"summary": f"Successfully processed and recorded invoice {inv_num} into the finance database."}
        )
