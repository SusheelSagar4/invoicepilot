"""
Test LLM Connection.
Calls agent.llm.ask() with a test prompt and prints the reply or a safe error summary.
NEVER prints or logs any API keys.
"""

import sys
from pathlib import Path

# Add project root to sys.path so "from agent import llm" works from any CWD
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent import llm


def main():
    try:
        reply = llm.ask("Reply with exactly the word: OK")
        print(f"LLM Reply: {reply}")
    except ValueError as ve:
        print(f"Configuration Error: {ve}")
    except Exception as e:
        err_msg = str(e)
        print("LLM Request Failed.")
        if "404" in err_msg or "NOT_FOUND" in err_msg:
            print("Likely Cause: Invalid or deprecated model name.")
        elif "401" in err_msg or "403" in err_msg or "API_KEY" in err_msg.upper() or "UNAUTHENTICATED" in err_msg.upper():
            print("Likely Cause: Invalid or missing API key.")
        elif "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "QUOTA" in err_msg.upper():
            print("Likely Cause: Quota or rate limit exceeded.")
        elif "connection" in err_msg.lower() or "socket" in err_msg.lower() or "dns" in err_msg.lower():
            print("Likely Cause: Network connectivity issue.")
        else:
            print(f"Likely Cause: {type(e).__name__} - {err_msg[:120]}")


if __name__ == "__main__":
    main()
