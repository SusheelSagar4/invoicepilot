"""
Approval Gate Module for InvoicePilot.
Enforces human-in-the-loop approval before executing sensitive browser tool actions.
Fail-Closed design: unknown element or match error = sensitive.
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from tools.browser import BrowserTools

SENSITIVE_LABEL_REGEX = re.compile(r"\b(submit|record|save|confirm|pay|send|delete)\b", re.IGNORECASE)


class ApprovalGate:
    """
    Evaluates tool execution requests against sensitive action policies.
    Enforces human approval before sensitive actions reach Playwright execution.
    """

    def __init__(self, auto_approve: bool = False):
        """
        Initialize ApprovalGate.

        Args:
            auto_approve: If True, skips terminal prompts (with startup warning).
        """
        self.auto_approve = auto_approve

    def is_sensitive(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        current_url: str,
        element_map: Dict[int, Dict[str, Any]]
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Determine sensitivity from last read_page snapshot state.

        Sensitivity Rules:
        1. Tool is 'click' and element is unknown/missing from element_map -> sensitive (Fail-Closed).
        2. Element is input of type submit, or label matches submit|record|save|confirm|pay|send|delete -> sensitive.
        3. URL host:port is localhost:8002 (finance system) and element is a button -> sensitive.
        4. Programmatic form submit tools (if any) -> sensitive.

        Returns:
            (sensitive: bool, label: str, elem_info: dict)
        """
        if tool_name != "click":
            # Non-click tools (e.g. goto, type_text, read_page, remember) are not sensitive
            return False, "", {}

        element_id = tool_args.get("element_id")
        if element_id is None:
            return True, "unknown element (no ID)", {}

        # Rule C: Unknown element ID in snapshot -> Sensitive (Fail-Closed)
        elem_info = element_map.get(int(element_id)) if element_map else None
        if not elem_info:
            return True, f"unknown element (ID {element_id} not in snapshot)", {}

        el_type = str(elem_info.get("type", "")).lower()
        el_label = str(elem_info.get("label", "")).strip()

        # Rule A: Input of type submit OR label matches sensitive regex
        is_submit_type = el_type == "input:submit" or el_type == "submit"
        label_matches_sensitive = bool(SENSITIVE_LABEL_REGEX.search(el_label))

        # Rule B: Current URL host:port is localhost:8002 and element is a button
        is_finance_url = "localhost:8002" in current_url or ":8002" in current_url
        is_button = el_type == "button" or el_type.startswith("input:")
        finance_button = is_finance_url and is_button

        if is_submit_type or label_matches_sensitive or finance_button:
            return True, el_label, elem_info

        return False, el_label, elem_info

    def check_and_prompt(
        self,
        browser: Optional[BrowserTools],
        tool_name: str,
        tool_args: Dict[str, Any],
        element_map: Dict[int, Dict[str, Any]]
    ) -> Tuple[bool, str]:
        """
        Single Choke Point check before execution.
        Prints debug line for EVERY click and prompts if sensitive.

        Returns:
            (approved: bool, reason: str)
        """
        current_url = ""
        if browser and hasattr(browser, "page") and browser.page:
            try:
                current_url = browser.page.url
            except Exception:
                current_url = ""

        element_id = tool_args.get("element_id")

        sensitive, label, elem_info = self.is_sensitive(
            tool_name=tool_name,
            tool_args=tool_args,
            current_url=current_url,
            element_map=element_map
        )

        if not sensitive:
            if tool_name == "click":
                print(f"[GATE] click element {element_id} label='{label}' url={current_url} sensitive=False -> skipped")
            return True, "Non-sensitive action"

        # Action is sensitive
        if self.auto_approve:
            print(f"[GATE] click element {element_id} label='{label}' url={current_url} sensitive=True -> approved (auto-approve)")
            return True, "Auto-approved by CLI flag"

        # Build boxed form summary for human operator
        form_summary = []
        if browser and hasattr(browser, "page") and browser.page:
            try:
                inputs = browser.page.query_selector_all("input, select, textarea")
                for inp in inputs:
                    inp_id = inp.get_attribute("id") or inp.get_attribute("name") or "field"
                    val = inp.input_value() if hasattr(inp, "input_value") else inp.get_attribute("value") or ""
                    form_summary.append(f"  - {inp_id}: {val}")
            except Exception:
                pass

        form_text = "\n".join(form_summary) if form_summary else "  (No input fields found)"

        print("\n" + "=" * 60)
        print("          [APPROVAL GATE: SENSITIVE ACTION DETECTED]          ")
        print("=" * 60)
        print(f"Target URL : {current_url}")
        print(f"Target     : [{element_id}] {elem_info.get('type', 'element')} \"{label}\"")
        print("Current Form Values:")
        print(form_text)
        print("=" * 60)

        user_input = input("Approve this action? [y/N]: ").strip().lower()
        if user_input in ["y", "yes"]:
            print(f"[GATE] click element {element_id} label='{label}' url={current_url} sensitive=True -> approved")
            return True, "Human approved action"
        else:
            print(f"[GATE] click element {element_id} label='{label}' url={current_url} sensitive=True -> rejected")
            return False, "Human rejected this action"
