"""
Agent Core Execution Loop for InvoicePilot.
Manages the step-by-step reasoning cycle:
1. Build prompt context (Task goal + Remembered facts + Trimmed interaction history)
2. Obtain LLM decision via llm.decide()
3. Check sensitive action Approval Gate at single choke point
4. Execute selected tool through ToolRegistry
5. Gate finish tool via independent Verifier check
6. Log step action, generate Evidence Report, and save run JSON
"""

import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable

from tools.browser import BrowserTools
from agent.memory import Memory
from agent.tool_registry import ToolRegistry
from agent.prompts import build_system_prompt
from agent.approval import ApprovalGate
from agent import llm


class Agent:
    """
    Autonomous AI Browser Worker Agent.
    Executes tasks using Playwright tools, memory storage, function-calling decisions,
    approval gates, verifiers, and evidence reporting.
    """

    def __init__(
        self,
        apps_config: List[Dict[str, str]],
        verifier_fn: Optional[Callable[[Dict[str, str]], Dict[str, Any]]] = None,
        auto_approve: bool = False,
        headless: bool = False,
        slow_mo: int = 300
    ):
        """
        Initialize Agent with application config, verifiers, approval settings, and browser settings.
        """
        self.apps_config = apps_config
        self.verifier_fn = verifier_fn
        self.auto_approve = auto_approve
        self.headless = headless
        self.slow_mo = slow_mo

    def run(self, task: str, max_steps: int = 25) -> Dict[str, Any]:
        """
        Execute the autonomous agent loop up to max_steps.

        Args:
            task: User-defined task instruction string.
            max_steps: Maximum number of loop iterations allowed (default 25).

        Returns:
            Dict containing {'success': bool, 'status': str, 'summary': str, 'steps': int, 'memory_facts': dict}
        """
        start_time = time.time()
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"\n==================== Starting Agent Loop ====================")
        print(f"Task: {task}")
        print(f"Max Steps: {max_steps}")
        if self.auto_approve:
            print("⚠️ WARNING: --auto-approve is ENABLED. All sensitive actions will execute without human confirmation!")
        print(f"============================================================\n")

        # Initialize browser tools, memory, registry, and approval gate
        browser = BrowserTools(headless=self.headless, slow_mo=self.slow_mo)
        memory = Memory()
        registry = ToolRegistry()
        approval_gate = ApprovalGate(auto_approve=self.auto_approve)

        # Map holding last read_page snapshot element metadata (element_id -> {type, label, href})
        last_snapshot_elements: Dict[int, Dict[str, Any]] = {}

        # State flags for task completion and metrics
        finished = False
        final_summary = ""
        run_status = "IN_PROGRESS"
        rejected_finish_attempts = 0
        tool_failures_count = 0
        human_approvals_count = 0
        verifier_result: Optional[Dict[str, Any]] = None

        def wrapped_read_page() -> Dict[str, Any]:
            nonlocal last_snapshot_elements
            res = browser.read_page()
            # Extract and store elements map from DOM read_page result
            if res.get("ok") and "observation" in res:
                # Re-parse or fetch elements array via internal evaluate for state map
                try:
                    raw_data = browser.page.evaluate("""
                    () => {
                        const candidates = Array.from(document.querySelectorAll('[data-agent-id]'));
                        return candidates.map(el => ({
                            id: parseInt(el.getAttribute('data-agent-id')),
                            type: el.tagName.toLowerCase() === 'input' ? `input:${el.type || 'text'}` : el.tagName.toLowerCase(),
                            label: (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '').trim()
                        }));
                    }
                    """)
                    last_snapshot_elements = {el["id"]: el for el in raw_data if "id" in el}
                except Exception:
                    pass
            return res

        def finish_impl(summary: str) -> Dict[str, Any]:
            nonlocal finished, final_summary, run_status, rejected_finish_attempts, verifier_result

            # Run independent verifier check if configured
            if self.verifier_fn:
                v_res = self.verifier_fn(memory.facts)
                verifier_result = v_res

                if v_res.get("passed"):
                    finished = True
                    run_status = "SUCCESS"
                    final_summary = summary
                    return {
                        "ok": True,
                        "observation": f"Verification PASSED! Summary: {summary}",
                        "error": None
                    }
                else:
                    rejected_finish_attempts += 1
                    failed_checks = [
                        f"{c['name']} (expected: {c['expected']}, actual: {c['actual']})"
                        for c in v_res.get("checks", []) if not c.get("ok")
                    ]
                    failed_str = ", ".join(failed_checks) if failed_checks else v_res.get("reason", "Checks failed")

                    if rejected_finish_attempts >= 2:
                        finished = True
                        run_status = "FAILED_VERIFICATION"
                        final_summary = f"Verification failed twice ({failed_str})."
                        return {
                            "ok": False,
                            "observation": f"Verification failed twice ({failed_str}). Terminating run.",
                            "error": "Failed verification limit reached."
                        }
                    else:
                        return {
                            "ok": False,
                            "observation": (
                                f"Verification FAILED (Attempt {rejected_finish_attempts}/2): {failed_str}. "
                                f"Reason: {v_res.get('reason')}. Please inspect the page, correct any missing or invalid data, "
                                f"store the corrected facts with `remember`, and call `finish` again."
                            ),
                            "error": "Verification failed."
                        }
            else:
                finished = True
                run_status = "SUCCESS"
                final_summary = summary
                return {"ok": True, "observation": f"Task finished with summary: {summary}", "error": None}

        # Register tools in ToolRegistry
        registry.register("goto", browser.goto, "Navigate browser to specified URL.", {
            "type": "OBJECT", "properties": {"url": {"type": "STRING"}}, "required": ["url"]
        })

        registry.register("read_page", wrapped_read_page, "Inspect DOM state and return visible text and tagged elements.", {
            "type": "OBJECT", "properties": {}
        })

        registry.register("click", browser.click, "Click interactive element by integer data-agent-id.", {
            "type": "OBJECT", "properties": {"element_id": {"type": "INTEGER"}}, "required": ["element_id"]
        })

        registry.register("type_text", browser.type_text, "Type text into input field by integer data-agent-id.", {
            "type": "OBJECT",
            "properties": {
                "element_id": {"type": "INTEGER"},
                "text": {"type": "STRING"}
            },
            "required": ["element_id", "text"]
        })

        registry.register("remember", memory.remember, "Store key-value fact into memory.", {
            "type": "OBJECT",
            "properties": {
                "key": {"type": "STRING"},
                "value": {"type": "STRING"}
            },
            "required": ["key", "value"]
        })

        registry.register("finish", finish_impl, "Signal task completion and provide final summary.", {
            "type": "OBJECT",
            "properties": {"summary": {"type": "STRING"}},
            "required": ["summary"]
        })

        history_steps: List[Dict[str, str]] = []
        completed_steps = 0

        try:
            for step in range(1, max_steps + 1):
                completed_steps = step
                print(f"\n--- Step {step}/{max_steps} ---")

                system_prompt = build_system_prompt(self.apps_config)
                facts_text = memory.get_facts_text()

                messages = [
                    {
                        "role": "user",
                        "content": f"Task Goal: {task}\n\n{facts_text}\n\nProceed with the next step."
                    }
                ]

                # History trimming: keep only most recent read_page observation full
                latest_read_index = -1
                for idx, item in enumerate(history_steps):
                    if item.get("tool") == "read_page" and item.get("role") == "observation":
                        latest_read_index = idx

                for idx, item in enumerate(history_steps):
                    role = item["role"]
                    content = item["content"]
                    if item.get("tool") == "read_page" and role == "observation" and idx != latest_read_index:
                        content = "[earlier page snapshot omitted]"
                    messages.append({"role": role, "content": content})

                tool_schemas = registry.get_schemas()
                try:
                    decision = llm.decide(
                        system_prompt=system_prompt,
                        messages=messages,
                        tools=tool_schemas
                    )
                except llm.LLMUnavailableError as e:
                    run_status = "LLM_UNAVAILABLE"
                    print(f"\nStopped: LLM unavailable after retries ({str(e)})")
                    break

                if decision.error:
                    print(f"LLM Error: {decision.error}")
                    run_status = "LLM_UNAVAILABLE"
                    break

                if decision.is_tool_call:
                    tool_name = decision.tool_name
                    tool_args = decision.tool_args
                    print(f"Action: {tool_name}({tool_args})")

                    # SINGLE CHOKE POINT: Check Approval Gate before executing action
                    approved, app_reason = approval_gate.check_and_prompt(
                        browser=browser,
                        tool_name=tool_name,
                        tool_args=tool_args,
                        element_map=last_snapshot_elements
                    )

                    if not approved:
                        result = {
                            "ok": False,
                            "observation": "Human rejected this action",
                            "error": "Human rejected action"
                        }
                        tool_failures_count += 1
                        memory.log_action(tool_name, tool_args, result)
                        history_steps.append({"role": "model", "content": f"Selected tool '{tool_name}' with args {tool_args}", "tool": tool_name})
                        history_steps.append({"role": "user", "content": f"Tool '{tool_name}' result:\nHuman rejected this action", "tool": tool_name})
                        print(f"Result (ok=False): Human rejected this action")
                        continue
                    elif "Human approved" in app_reason or "Auto-approved" in app_reason:
                        human_approvals_count += 1

                    # Execute tool via ToolRegistry
                    result = registry.execute(tool_name, tool_args)
                    if not result.get("ok"):
                        tool_failures_count += 1

                    obs_str = result.get("observation", "")
                    short_obs = obs_str.replace("\n", " ")[:120]
                    print(f"Result (ok={result.get('ok')}): {short_obs}...")

                    memory.log_action(tool_name, tool_args, result)
                    history_steps.append({"role": "model", "content": f"Selected tool '{tool_name}' with args {tool_args}", "tool": tool_name})
                    history_steps.append({"role": "user", "content": f"Tool '{tool_name}' result:\n{obs_str}", "tool": tool_name})

                    if finished:
                        break
                else:
                    text = decision.text or ""
                    print(f"Model Thought: {text}")
                    history_steps.append({"role": "model", "content": text})

            if not finished and run_status not in ["LLM_UNAVAILABLE", "FAILED_VERIFICATION"]:
                run_status = "MAX_STEPS"
                final_summary = f"Reached maximum steps ({max_steps}) without completion."

            if self.verifier_fn and not verifier_result:
                verifier_result = self.verifier_fn(memory.facts)

        finally:
            elapsed_sec = time.time() - start_time
            
            os.makedirs("screenshots", exist_ok=True)
            screenshot_path = os.path.join("screenshots", f"final_run_{timestamp_str}.png")
            try:
                browser.screenshot(path=screenshot_path)
            except Exception:
                screenshot_path = "None"

            browser.close()

            rec_id = verifier_result.get("record_id") if verifier_result else "N/A"
            checks = verifier_result.get("checks", []) if verifier_result else []

            print("\n" + "=" * 65)
            print("                        EVIDENCE REPORT                        ")
            print("=" * 65)
            print(f"Status           : {run_status}")
            print(f"Task             : {task}")
            print(f"Finance Record ID: {rec_id}")
            print(f"Steps Executed   : {completed_steps}")
            print(f"Tool Failures    : {tool_failures_count}")
            print(f"Human Approvals  : {human_approvals_count}")
            print(f"Elapsed Time     : {elapsed_sec:.2f}s")
            print(f"Final Screenshot : {screenshot_path}")
            
            print("\nRemembered Facts :")
            if memory.facts:
                for k, v in memory.facts.items():
                    print(f"  - {k}: {v}")
            else:
                print("  (None)")

            print("\nVerifier Checks  :")
            if checks:
                for c in checks:
                    mark = "[✓]" if c.get("ok") else "[✗]"
                    print(f"  {mark} {c.get('name'):<15}: Expected={c.get('expected')!r}, Actual={c.get('actual')!r}")
            else:
                reason = verifier_result.get("reason", "No verification performed") if verifier_result else "N/A"
                print(f"  (No checks passed - Reason: {reason})")

            print("=" * 65 + "\n")

            os.makedirs("runs", exist_ok=True)
            report_data = {
                "timestamp": timestamp_str,
                "status": run_status,
                "task": task,
                "record_id": rec_id,
                "steps": completed_steps,
                "tool_failures": tool_failures_count,
                "human_approvals": human_approvals_count,
                "elapsed_time_seconds": round(elapsed_sec, 2),
                "screenshot_path": screenshot_path,
                "remembered_facts": memory.facts,
                "verifier_result": verifier_result,
                "action_log": memory.action_log
            }
            json_report_path = os.path.join("runs", f"run_{timestamp_str}.json")
            with open(json_report_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)

            print(f"Run report saved to '{json_report_path}'.\n")

            return {
                "success": run_status == "SUCCESS",
                "status": run_status,
                "summary": final_summary,
                "steps": completed_steps,
                "memory_facts": memory.facts,
                "json_report_path": json_report_path
            }
