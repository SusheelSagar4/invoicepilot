"""
Main Entry Point for InvoicePilot.
Configures application endpoints and executes the autonomous AI browser worker.

Default Example Task:
"Find the latest invoice from Acme Technologies in the invoice portal, then enter its invoice number, vendor, amount and due date into the finance system."
"""

import sys
from agent.agent import Agent

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

# Default task instruction
DEFAULT_TASK = (
    "Find the latest invoice from Acme Technologies in the invoice portal, "
    "then enter its invoice number, vendor, amount and due date into the finance system."
)


def main():
    """
    Parse task instruction from CLI arguments or user input, then launch the agent loop.
    """
    if len(sys.argv) > 1 and sys.argv[1].strip():
        task = sys.argv[1].strip()
    else:
        print(f"No task provided via command line.")
        print(f"Default task: '{DEFAULT_TASK}'")
        user_input = input("Enter task (or press Enter to run default): ").strip()
        task = user_input if user_input else DEFAULT_TASK

    # Instantiate and run autonomous agent
    agent = Agent(apps_config=APPS_CONFIG, headless=False, slow_mo=300)
    agent.run(task=task, max_steps=25)


if __name__ == "__main__":
    main()
