"""
Main Entry Point for InvoicePilot.
Configures application endpoints, verifiers, approval policies, and CLI options,
then executes the autonomous AI browser worker.

Default Example Task:
"Find the latest invoice from Acme Technologies in the invoice portal, then enter its invoice number, vendor, amount and due date into the finance system."
"""

import sys
import argparse
from agent.agent import Agent
from agent.verifier import verify_finance_record

# Configuration list defining available enterprise mock applications
APPS_CONFIG = [
    {
        "name": "Invoice Portal",
        "url": "http://localhost:8001",
        "description": "Portal for searching and inspecting vendor invoices."
    },
    {
        "name": "Finance System",
        "url": "http://localhost:8002",
        "description": "Enterprise database system for recording processed invoice payment authorizations."
    }
]

# Configurable verifier registry mapping task types to independent verifier functions
VERIFIERS = {
    "finance_record": verify_finance_record
}

# Default task instruction
DEFAULT_TASK = (
    "Find the latest invoice from Acme Technologies in the invoice portal, "
    "then enter its invoice number, vendor, amount and due date into the finance system."
)


def main():
    """
    Parse task instruction and options from CLI arguments, then launch the agent loop.
    """
    parser = argparse.ArgumentParser(description="InvoicePilot Autonomous AI Browser Agent")
    parser.add_argument("task", nargs="?", default=DEFAULT_TASK, help="Task instruction string for the agent")
    parser.add_argument("--auto-approve", action="store_true", default=False, help="Skip terminal approval prompts for sensitive actions")
    parser.add_argument("--max-steps", type=int, default=25, help="Maximum number of loop steps allowed")

    args = parser.parse_args()

    task = args.task.strip()
    if not task:
        task = DEFAULT_TASK

    print(f"Task Instruction: {task}")
    if args.auto_approve:
        print("⚠️ WARNING: --auto-approve is ENABLED. All sensitive actions will execute without human confirmation!")
    else:
        print("Approval Gate: ENABLED (Human approval required for sensitive actions)")

    # Select verifier for finance record task
    verifier_fn = VERIFIERS.get("finance_record")

    # Instantiate and run autonomous agent
    agent = Agent(
        apps_config=APPS_CONFIG,
        verifier_fn=verifier_fn,
        auto_approve=args.auto_approve,
        headless=False,
        slow_mo=300
    )
    agent.run(task=task, max_steps=args.max_steps)


if __name__ == "__main__":
    main()
