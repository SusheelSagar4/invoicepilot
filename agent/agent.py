"""
Agent Core Execution Loop for InvoicePilot.
Manages the step-by-step reasoning cycle:
1. Build prompt context (Task goal + Remembered facts + Trimmed interaction history)
2. Obtain LLM decision via llm.decide()
3. Execute selected tool through ToolRegistry
4. Log step action and update state
5. Cleanly shut down browser resources upon completion or termination
"""

import sys
from typing import List, Dict, Any, Optional
from tools.browser import BrowserTools
from agent.memory import Memory
from agent.tool_registry import ToolRegistry
from agent.prompts import build_system_prompt
from agent import llm


class Agent:
    """
    Autonomous AI Browser Worker Agent.
    Executes tasks using Playwright tools, memory storage, and function-calling decisions.
    """

    def __init__(self, apps_config: List[Dict[str, str]], headless: bool = False, slow_mo: int = 300):
        """
        Initialize Agent with application config and browser settings.
        """
        self.apps_config = apps_config
        self.headless = headless
        self.slow_mo = slow_mo

    def run(self, task: str, max_steps: int = 25) -> Dict[str, Any]:
        """
        Execute the autonomous agent loop up to max_steps.

        Args:
            task: User-defined task instruction string.
            max_steps: Maximum number of loop iterations allowed (default 25).

        Returns:
            Dict containing {'success': bool, 'summary': str, 'steps': int, 'memory_facts': dict}
        """
        print(f"\n==================== Starting Agent Loop ====================")
        print(f"Task: {task}")
        print(f"Max Steps: {max_steps}")
        print(f"============================================================\n")

        # Initialize browser tools and memory
        browser = BrowserTools(headless=self.headless, slow_mo=self.slow_mo)
        memory = Memory()
        registry = ToolRegistry()

        # State flags for task completion
        finished = False
        final_summary = ""

        def finish_impl(summary: str) -> Dict[str, Any]:
            nonlocal finished, final_summary
            finished = True
            final_summary = summary
            return {"ok": True, "observation": f"Task finished with summary: {summary}", "error": None}

        # Register tools in ToolRegistry
        registry.register(
            name="goto",
            func=browser.goto,
            description="Navigate browser to the specified URL.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "url": {"type": "STRING", "description": "Target URL to navigate to (e.g. http://localhost:8001)"}
                },
                "required": ["url"]
            }
        )

        registry.register(
            name="read_page",
            func=browser.read_page,
            description="Inspect current DOM state and return visible text and tagged interactive elements.",
            parameters={
                "type": "OBJECT",
                "properties": {}
            }
        )

        registry.register(
            name="click",
            func=browser.click,
            description="Click an interactive element by its integer data-agent-id tag.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "element_id": {"type": "INTEGER", "description": "The data-agent-id integer of the element to click"}
                },
                "required": ["element_id"]
            }
        )

        registry.register(
            name="type_text",
            func=browser.type_text,
            description="Type text into an input field by its integer data-agent-id tag.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "element_id": {"type": "INTEGER", "description": "The data-agent-id integer of the target element"},
                    "text": {"type": "STRING", "description": "Text string to type into the field"}
                },
                "required": ["element_id", "text"]
            }
        )

        registry.register(
            name="remember",
            func=memory.remember,
            description="Store a key-value fact into memory for access in future steps.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "key": {"type": "STRING", "description": "Fact label or key name"},
                    "value": {"type": "STRING", "description": "Fact value to store"}
                },
                "required": ["key", "value"]
            }
        )

        registry.register(
            name="finish",
            func=finish_impl,
            description="Signal that the task is complete and provide a final summary.",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "summary": {"type": "STRING", "description": "Detailed summary of completed actions and results"}
                },
                "required": ["summary"]
            }
        )

        # Raw step history list for message construction
        history_steps: List[Dict[str, str]] = []

        try:
            for step in range(1, max_steps + 1):
                print(f"\n--- Step {step}/{max_steps} ---")

                # Build system prompt with application configuration
                system_prompt = build_system_prompt(self.apps_config)

                # Format current memory facts and prompt text
                facts_text = memory.get_facts_text()
                
                # Construct messages list for LLM context
                messages = [
                    {
                        "role": "user",
                        "content": f"Task Goal: {task}\n\n{facts_text}\n\nProceed with the next step."
                    }
                ]

                # History trimming: find index of the most recent read_page observation
                latest_read_index = -1
                for idx, item in enumerate(history_steps):
                    if item.get("tool") == "read_page" and item.get("role") == "observation":
                        latest_read_index = idx

                # Build trimmed history items for LLM
                for idx, item in enumerate(history_steps):
                    role = item["role"]
                    content = item["content"]
                    
                    # Trim older read_page snapshots to save token context space
                    if item.get("tool") == "read_page" and role == "observation" and idx != latest_read_index:
                        content = "[earlier page snapshot omitted]"
                    
                    messages.append({"role": role, "content": content})

                # Call LLM decision engine
                tool_schemas = registry.get_schemas()
                decision = llm.decide(
                    system_prompt=system_prompt,
                    messages=messages,
                    tools=tool_schemas
                )

                if decision.error:
                    print(f"LLM Error: {decision.error}")
                    break

                if decision.is_tool_call:
                    tool_name = decision.tool_name
                    tool_args = decision.tool_args
                    print(f"Action: {tool_name}({tool_args})")

                    # TODO: Approval Gate (Insert user confirmation check before high-impact actions like submit)
                    # TODO: Retry Logic (Insert automated retry loop for transient Playwright timeout / navigation failures)
                    
                    # Execute tool via ToolRegistry
                    result = registry.execute(tool_name, tool_args)
                    
                    # TODO: Verifier Check (Insert state verification check against database/API after mutation)
                    
                    obs_str = result.get("observation", "")
                    short_obs = obs_str.replace("\n", " ")[:120]
                    print(f"Result (ok={result.get('ok')}): {short_obs}...")

                    # Log execution into agent memory
                    memory.log_action(tool_name, tool_args, result)

                    # Append action and observation to step history
                    history_steps.append({
                        "role": "model",
                        "content": f"Selected tool '{tool_name}' with args {tool_args}",
                        "tool": tool_name
                    })
                    history_steps.append({
                        "role": "user",
                        "content": f"Tool '{tool_name}' result:\n{obs_str}",
                        "tool": tool_name
                    })

                    # Check if finish tool was invoked
                    if finished:
                        print(f"\n==================== Task Finished ====================")
                        print(f"Summary: {final_summary}")
                        print(f"=======================================================\n")
                        return {
                            "success": True,
                            "summary": final_summary,
                            "steps": step,
                            "memory_facts": memory.facts
                        }
                else:
                    # Model returned plain text instead of a tool call
                    text = decision.text or ""
                    print(f"Model Thought: {text}")
                    history_steps.append({"role": "model", "content": text})

                # TODO: Eval Logging (Record step evaluation metrics and trajectory trace for benchmark analysis)

            print(f"\n==================== Max Steps Reached ====================")
            print(f"Agent reached maximum step limit ({max_steps}) without calling finish.")
            print(f"===========================================================\n")
            return {
                "success": False,
                "summary": "Reached maximum steps without finishing.",
                "steps": max_steps,
                "memory_facts": memory.facts
            }

        finally:
            # Always ensure browser resources are cleanly closed
            browser.close()
