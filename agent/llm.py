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
from typing import Dict, Any, Optional, List, Tuple
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
    """Raised when the LLM provider remains unavailable after rate-limit retries or daily quota depletion."""
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


def _parse_retry_delay_and_quota(err: Exception) -> Tuple[float, str]:
    """
    Extract float retry delay (seconds) and quotaId string from Gemini API error details/message.
    Handles values like '57s', '58.3s', and '60.0'.
    """
    err_str = str(err)
    
    # Extract quotaId string (e.g., quotaId: "GenerateRequestsPerDayPerProject")
    quota_match = re.search(r"['\"]?quotaId['\"]?\s*:\s*['\"]?([^'\"]+)['\"]?", err_str, re.IGNORECASE)
    quota_id = quota_match.group(1).strip() if quota_match else "UnknownQuota"

    # Extract retryDelay float (e.g., '57s' or '58.3s')
    delay_match = re.search(r"['\"]?retryDelay['\"]?\s*:\s*['\"]?([\d.]+)s?['\"]?", err_str, re.IGNORECASE)
    retry_delay = 60.0
    if delay_match:
        try:
            retry_delay = float(delay_match.group(1))
        except ValueError:
            retry_delay = 60.0

    # Also inspect error.details if available
    details = getattr(err, "details", None)
    if details and isinstance(details, (list, tuple)):
        for d in details:
            if isinstance(d, dict):
                if "quotaId" in d:
                    quota_id = str(d["quotaId"]).strip()
                if "retryDelay" in d:
                    d_str = str(d["retryDelay"]).rstrip("s")
                    try:
                        retry_delay = float(d_str)
                    except ValueError:
                        pass

    return retry_delay, quota_id


def ask(prompt: str) -> str:
    """
    Sends a plain text prompt to the Gemini LLM and returns the generated text response.
    Enforces rate-limiting and quota checking up to 3 retries.
    """
    max_retries = 3
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
            if is_rate_limit:
                parsed_delay, quota_id = _parse_retry_delay_and_quota(e)
                print(f"Rate limited (Quota: {quota_id}, Delay: {parsed_delay:.1f}s)")
                
                # Check for PerDay quota or long wait times (> 120s)
                if "perday" in quota_id.lower() or parsed_delay > 120.0:
                    raise LLMUnavailableError(
                        f"Daily or long-term quota limit hit ({quota_id}). Requested delay is {parsed_delay:.1f}s. Resets later."
                    )
                
                if attempt < max_retries - 1:
                    wait_time = min(parsed_delay, 90.0) + 1.0
                    print(f"Rate limited, waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    raise LLMUnavailableError(f"LLM ask() failed after {max_retries} retries ({quota_id}).")
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
    Sends conversation history and registered tool schemas to Gemini.
    Enforces float delay parsing, PerDay quota circuit breaking, and up to 3 retries.
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

    max_retries = 3
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
                parsed_delay, quota_id = _parse_retry_delay_and_quota(e)
                print(f"Rate limited (Quota: {quota_id}, Delay: {parsed_delay:.1f}s)")
                
                # Check for PerDay quota or long wait times (> 120s)
                if "perday" in quota_id.lower() or parsed_delay > 120.0:
                    raise LLMUnavailableError(
                        f"Daily or long-term quota limit hit ({quota_id}). Requested delay is {parsed_delay:.1f}s. Resets later."
                    )

                if attempt < max_retries - 1:
                    wait_time = min(parsed_delay, 90.0) + 1.0
                    print(f"Rate limited, waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    raise LLMUnavailableError(f"LLM unavailable after {max_retries} retries ({quota_id}).")
            else:
                return DecisionResult(
                    is_tool_call=False,
                    error=f"LLM decision error: {err_msg}"
                )

    raise LLMUnavailableError(f"LLM unavailable after {max_retries} retries.")
