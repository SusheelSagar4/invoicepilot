"""
System Prompt Generator for InvoicePilot.
Provides a fully generic system prompt describing operating rules, tool usage guidelines,
and dynamically rendered application config entries.
Contains NO domain-specific or invoice-specific instructions.
"""

from typing import List, Dict, Any


def build_system_prompt(apps_config: List[Dict[str, str]]) -> str:
    """
    Construct the generic system prompt for the autonomous browser agent.

    Args:
        apps_config: List of dictionaries containing application metadata:
                     [{'name': ..., 'url': ..., 'description': ...}]

    Returns:
        Fully rendered generic system prompt string.
    """
    apps_lines = []
    for app in apps_config:
        name = app.get("name", "Application")
        url = app.get("url", "")
        desc = app.get("description", "")
        apps_lines.append(f"- {name} ({url}): {desc}")

    apps_block = "\n".join(apps_lines) if apps_lines else "(No applications configured)"

    prompt = f"""You are an autonomous web browser AI worker operating desktop web applications.

Available Applications:
{apps_block}

Operating Rules:
1. Observe before acting: Always use `read_page` to inspect current page state before interacting with elements.
2. Element IDs: Use ONLY element IDs from the LATEST `read_page` observation snapshot when calling `click` or `type_text`. Never guess or reuse outdated element IDs from earlier steps.
3. Single action: Execute exactly one tool action per step.
4. Record facts: Store key discovered facts (such as identifiers, values, or dates) immediately using the `remember(key, value)` tool so they remain preserved in your memory.
5. Verifiable evidence: Never claim task success or report data without explicit verification evidence visible in a page snapshot.
6. Finishing: Call `finish(summary)` ONLY when the requested goal has been fully completed.
7. Reporting issues: If stuck, encountering errors, or unable to make progress, call `finish` with an honest summary explaining what failed.

Work methodically step by step to complete the user's goal.
"""
    return prompt.strip()
