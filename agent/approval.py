"""
Approval Gate Module for InvoicePilot.
Enforces human-in-the-loop approval before executing sensitive browser tool actions.
"""

from typing import Dict, Any, List, Tuple, Optional
from tools.browser import BrowserTools


class ApprovalGate:
    """
    Evaluates tool execution requests against sensitive action policies.
    Prompts human user for confirmation when a policy rule matches.
    """

    def __init__(self, policies: List[Dict[str, str]], auto_approve: bool = False):
        """
        Initialize ApprovalGate.

        Args:
            policies: List of policy rule dictionaries, e.g.:
                      [{'action': 'click', 'url_contains': 'localhost:8002', 'label_contains': 'Submit'}]
            auto_approve: If True, automatically approves all sensitive actions without terminal prompts.
        """
        self.policies = policies
        self.auto_approve = auto_approve

    def check_approval(
        self,
        browser: BrowserTools,
        tool_name: str,
        tool_args: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Check if the tool execution matches a sensitive action policy.
        If matched, requests terminal input from human operator unless auto_approve is set.

        Returns:
            (approved: bool, reason: str)
        """
        if not self.policies:
            return True, "No policies configured."

        current_url = browser.page.url
        matching_policy = None

        if tool_name == "click":
            element_id = tool_args.get("element_id")
            # Locate element text/label to check policy condition
            locator = browser.page.locator(f'[data-agent-id="{element_id}"]')
            elem_text = ""
            if locator.count() > 0:
                elem_text = (locator.inner_text() or locator.get_attribute("value") or "").strip()

            for policy in self.policies:
                p_action = policy.get("action", "")
                p_url = policy.get("url_contains", "")
                p_label = policy.get("label_contains", "")

                url_match = not p_url or p_url in current_url
                label_match = not p_label or p_label.lower() in elem_text.lower()

                if tool_name == p_action and url_match and label_match:
                    matching_policy = policy
                    break

        if not matching_policy:
            return True, "Action not flagged as sensitive."

        # Sensitive action policy matched
        if self.auto_approve:
            print(f"\n[Approval Gate] Auto-approved sensitive action '{tool_name}' on {current_url}")
            return True, "Auto-approved by CLI flag."

        # Extract current form field values for human summary
        form_summary = []
        try:
            inputs = browser.page.query_selector_all("input, select, textarea")
            for inp in inputs:
                inp_id = inp.get_attribute("id") or inp.get_attribute("name") or "field"
                val = inp.input_value() if hasattr(inp, "input_value") else inp.get_attribute("value") or ""
                if val:
                    form_summary.append(f"  - {inp_id}: {val}")
        except Exception:
            pass

        form_text = "\n".join(form_summary) if form_summary else "  (No input values detected)"

        print("\n" + "=" * 60)
        print("          [APPROVAL GATE: SENSITIVE ACTION DETECTED]          ")
        print("=" * 60)
        print(f"Target URL : {current_url}")
        print(f"Action     : {tool_name} (Element [{tool_args.get('element_id')}])")
        print("Form Summary:")
        print(form_text)
        print("=" * 60)

        response = input("Approve this action? [y/N]: ").strip().lower()
        if response == "y":
            print("[Approval Gate] Action APPROVED by human operator.\n")
            return True, "Human approved action."
        else:
            print("[Approval Gate] Action REJECTED by human operator.\n")
            return False, "Human rejected this action"
