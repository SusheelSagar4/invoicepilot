"""
Agent Memory Layer for InvoicePilot.
Maintains key-value remembered facts and an ordered action log of executed steps.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional


class Memory:
    """
    State container holding agent memory:
    - facts: Dictionary of remembered key-value pairs (e.g., invoice_number -> INV-2026-003)
    - action_log: Ordered history of tool executions with timestamps, arguments, and outcomes.
    """

    def __init__(self):
        self.facts: Dict[str, str] = {}
        self.action_log: List[Dict[str, Any]] = []

    def remember(self, key: str, value: str) -> Dict[str, Any]:
        """
        Store a key-value fact in memory.
        Callable by the 'remember' tool during agent execution.
        """
        clean_key = str(key).strip()
        clean_val = str(value).strip()
        self.facts[clean_key] = clean_val
        obs = f"Remembered fact: '{clean_key}' = '{clean_val}'"
        return {"ok": True, "observation": obs, "error": None}

    def log_action(self, tool: str, args: Dict[str, Any], result: Dict[str, Any]):
        """
        Append a tool execution entry to the ordered action log with timestamp.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool,
            "args": args,
            "ok": result.get("ok", False),
            "observation": result.get("observation", ""),
            "error": result.get("error")
        }
        self.action_log.append(entry)

    def get_facts_text(self) -> str:
        """
        Format all remembered facts into a readable text block to include in LLM context.
        """
        if not self.facts:
            return "Remembered Facts:\n(None)"

        lines = ["Remembered Facts:"]
        for k, v in self.facts.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)
