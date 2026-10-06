"""
LLM Access Layer for InvoicePilot.
This module is the ONLY file in the project authorized to communicate
with the LLM provider (Google Gemini API).
"""

import os
import re
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Resolve the absolute path to .env in the project root relative to this file
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

# Load environment variables from project root .env
load_dotenv(dotenv_path=ENV_PATH)

# Retrieve and validate GEMINI_API_KEY
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is missing! Please create a .env file in the project root "
        "based on .env.example and set your GEMINI_API_KEY."
    )

# Model configuration constant (Single source of truth)
MODEL_NAME = "gemini-3.5-flash"

# Minimum delay in seconds between consecutive API calls to comply with rate limits (5 RPM free tier)
MIN_SECONDS_BETWEEN_CALLS = 13
_last_call_timestamp: float = 0.0

# Initialize Google GenAI client
_client = genai.Client(api_key=API_KEY)


class LLMUnavailableError(Exception):
    """Raised when the LLM provider remains unavailable after maximum rate-limit retries."""
    pass


@dataclass
class DecisionResult:
    """
    Structured result returned by llm.decide().
    Contains either a tool call (name + args) or a plain text response.
    """
    is_tool_call: bool
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = field(default_factory=dict)
    text: Optional[str] = None
    error: Optional[str] = None


def _enforce_min_delay():
    """
    Ensure API requests are spaced at least MIN_SECONDS_BETWEEN_CALLS seconds apart.
    """
    global _last_call_timestamp
    now = time.time()
    elapsed = now - _last_call_timestamp
    if _last_call_timestamp > 0 and elapsed < MIN_SECONDS_BETWEEN_CALLS:
        sleep_needed = MIN_SECONDS_BETWEEN_CALLS - elapsed
        time.sleep(sleep_needed)
    _last_call_timestamp = time.time()


def _extract_retry_delay(err: Exception) -> int:
    """
    Extract suggested retry delay in seconds from Gemini API error payload/details.
    Defaults to 60 seconds if not specified.
    """
    err_str = str(err)
    match = re.search(r"['\"]?retryDelay['\"]?\s*:\s*['\"]?(\d+)s?['\"]?", err_str, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    details = getattr(err, "details", None)
    if details and isinstance(details, (list, tuple)):
        for d in details:
            if isinstance(d, dict) and "retryDelay" in d:
                delay_str = str(d["retryDelay"]).rstrip("s")
                if delay_str.isdigit():
                    return int(delay_str)

    return 60


def ask(prompt: str) -> str:
    """
    Sends a plain text prompt to the Gemini LLM and returns the generated text response.
    Respects MIN_SECONDS_BETWEEN_CALLS and retries on 429 quota errors.

    Args:
        prompt: Plain text prompt string.

    Returns:
        Generated text reply from the model as a string.
    """
    max_retries = 5
    for attempt in range(max_retries):
        _enforce_min_delay()
        try:
            response = _client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            return response.text.strip() if response.text else ""
        except Exception as e:
            err_msg = str(e)
            is_rate_limit = "429" in err_msg or "quota" in err_msg.lower() or "resource_exhausted" in err_msg.lower()
            if is_rate_limit and attempt < max_retries - 1:
                suggested_delay = _extract_retry_delay(e)
                wait_time = suggested_delay + 1
                print(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise LLMUnavailableError(f"LLM ask() failed: {err_msg}")

    raise LLMUnavailableError("LLM unavailable after maximum retries.")


def decide(
    system_prompt: str,
    messages: List[Dict[str, str]],
    tools: List[Dict[str, Any]]
) -> DecisionResult:
    """
    Function-calling entry point for the agent loop.
    Sends conversation history and registered tool schemas to Gemini,
    returning a structured DecisionResult with a tool call or text response.

    Enforces MIN_SECONDS_BETWEEN_CALLS and handles 429 rate limits up to 5 retries.
    Raises LLMUnavailableError if all retries fail.
    """
    func_declarations = []
    for tool_schema in tools:
        func_declarations.append(
            types.FunctionDeclaration(
                name=tool_schema["name"],
                description=tool_schema["description"],
                parameters=tool_schema.get("parameters", {})
            )
        )

    tool_config = [types.Tool(function_declarations=func_declarations)] if func_declarations else None

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=tool_config,
        temperature=0.0
    )

    contents = []
    for msg in messages:
        role = "user" if msg.get("role") == "user" else "model"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg.get("content", ""))]
            )
        )

    max_retries = 5
    for attempt in range(max_retries):
        _enforce_min_delay()
        try:
            response = _client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=config
            )

            if response.function_calls:
                call = response.function_calls[0]
                tool_args = dict(call.args) if call.args else {}
                return DecisionResult(
                    is_tool_call=True,
                    tool_name=call.name,
                    tool_args=tool_args
                )

            text_res = response.text.strip() if response.text else ""
            return DecisionResult(
                is_tool_call=False,
                text=text_res
            )

        except Exception as e:
            err_msg = str(e)
            is_rate_limit = "429" in err_msg or "quota" in err_msg.lower() or "resource_exhausted" in err_msg.lower()
            if is_rate_limit:
                if attempt < max_retries - 1:
                    suggested_delay = _extract_retry_delay(e)
                    wait_time = suggested_delay + 1
                    print(f"Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise LLMUnavailableError(f"LLM unavailable after {max_retries} retries: {err_msg}")
            else:
                return DecisionResult(
                    is_tool_call=False,
                    error=f"LLM decision error: {err_msg}"
                )

    raise LLMUnavailableError(f"LLM unavailable after {max_retries} retries.")
