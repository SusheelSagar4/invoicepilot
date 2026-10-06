"""
Scripted Fake LLM Module for InvoicePilot.
Provides a deterministic, quota-free scripted decision generator for testing
the Playwright browser toolchain, approval gate, verifiers, and evidence reporting.
"""

from typing import List, Dict, Any, Optional
from agent.llm import DecisionResult


class FakeLLM:
    """
    Simulates LLM decisions by stepping through a hard-coded sequence of tool calls.
    Used when running InvoicePilot with `--fake-llm`.
    """

    def __init__(self):
        self.step_index = 0
        # Hard-coded happy path script for the Acme Technologies invoice task
        self.script: List[DecisionResult] = [
            # 1. Navigate to Portal
            DecisionResult(is_tool_call=True, tool_name="goto", tool_args={"url": "http://localhost:8001"}),
            # 2. Inspect Portal Home
            DecisionResult(is_tool_call=True, tool_name="read_page", tool_args={}),
            # 3. Type "acme" into search input (element 1)
            DecisionResult(is_tool_call=True, tool_name="type_text", tool_args={"element_id": 1, "text": "acme"}),
            # 4. Click Search button (element 2)
            DecisionResult(is_tool_call=True, tool_name="click", tool_args={"element_id": 2}),
            # 5. Inspect Search Results
            DecisionResult(is_tool_call=True, tool_name="read_page", tool_args={}),
            # 6. Click First Invoice Details link (element 1)
            DecisionResult(is_tool_call=True, tool_name="click", tool_args={"element_id": 1}),
            # 7. Inspect Invoice Detail Page
            DecisionResult(is_tool_call=True, tool_name="read_page", tool_args={}),
            # 8-11. Store Discovered Invoice Facts in Memory
            DecisionResult(is_tool_call=True, tool_name="remember", tool_args={"key": "invoice_number", "value": "INV-2026-003"}),
            DecisionResult(is_tool_call=True, tool_name="remember", tool_args={"key": "vendor", "value": "Acme Technologies"}),
            DecisionResult(is_tool_call=True, tool_name="remember", tool_args={"key": "amount", "value": "62400"}),
            DecisionResult(is_tool_call=True, tool_name="remember", tool_args={"key": "due_date", "value": "2026-10-30"}),
            # 12. Navigate to Finance System
            DecisionResult(is_tool_call=True, tool_name="goto", tool_args={"url": "http://localhost:8002"}),
            # 13. Inspect Finance Form Page
            DecisionResult(is_tool_call=True, tool_name="read_page", tool_args={}),
            # 14-17. Fill Form Fields
            DecisionResult(is_tool_call=True, tool_name="type_text", tool_args={"element_id": 1, "text": "INV-2026-003"}),
            DecisionResult(is_tool_call=True, tool_name="type_text", tool_args={"element_id": 2, "text": "Acme Technologies"}),
            DecisionResult(is_tool_call=True, tool_name="type_text", tool_args={"element_id": 3, "text": "62400"}),
            DecisionResult(is_tool_call=True, tool_name="type_text", tool_args={"element_id": 4, "text": "2026-10-30"}),
            # 18. Click Submit Invoice Record button (element 5) - Triggers Approval Gate!
            DecisionResult(is_tool_call=True, tool_name="click", tool_args={"element_id": 5}),
            # 19. Inspect Success Page
            DecisionResult(is_tool_call=True, tool_name="read_page", tool_args={}),
            # 20. Signal Completion
            DecisionResult(
                is_tool_call=True,
                tool_name="finish",
                tool_args={"summary": "Successfully recorded latest invoice INV-2026-003 for Acme Technologies into the finance system."}
            )
        ]

    def decide(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]]
    ) -> DecisionResult:
        """
        Return next decision in the scripted sequence.
        """
        if self.step_index < len(self.script):
            decision = self.script[self.step_index]
            self.step_index += 1
            return decision
        
        # If script sequence is exhausted, signal finish
        return DecisionResult(
            is_tool_call=True,
            tool_name="finish",
            tool_args={"summary": "Scripted FakeLLM sequence completed."}
        )
