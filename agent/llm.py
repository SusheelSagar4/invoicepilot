"""
LLM Access Layer for InvoicePilot.
This module is the ONLY file in the project authorized to communicate
with the LLM provider (Google Gemini API).
"""

import os
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

# Initialize Google GenAI client
_client = genai.Client(api_key=API_KEY)


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


def ask(prompt: str) -> str:
    """
    Sends a plain text prompt to the Gemini LLM and returns the generated text response.

    Args:
        prompt: Plain text prompt string.

    Returns:
        Generated text reply from the model as a string.
    """
    response = _client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )
    return response.text.strip() if response.text else ""


def decide(
    system_prompt: str,
    messages: List[Dict[str, str]],
    tools: List[Dict[str, Any]]
) -> DecisionResult:
    """
    Function-calling entry point for the agent loop.
    Sends conversation history and registered tool schemas to Gemini,
    returning a structured DecisionResult with a tool call or text response.

    Implements automatic retry logic (up to 3 attempts) for HTTP 429 / quota rate-limit errors.
    """
    # Build FunctionDeclarations from tool schemas
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

    # Construct generation config with system prompt and tools
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=tool_config,
        temperature=0.0
    )

    # Format message history into SDK Content items
    contents = []
    for msg in messages:
        role = "user" if msg.get("role") == "user" else "model"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg.get("content", ""))]
            )
        )

    # Retry loop for 429 / quota errors
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = _client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=config
            )

            # Check if model returned function calls
            if response.function_calls:
                call = response.function_calls[0]
                tool_args = dict(call.args) if call.args else {}
                return DecisionResult(
                    is_tool_call=True,
                    tool_name=call.name,
                    tool_args=tool_args
                )

            # Fallback to plain text response
            text_res = response.text.strip() if response.text else ""
            return DecisionResult(
                is_tool_call=False,
                text=text_res
            )

        except Exception as e:
            err_msg = str(e)
            is_rate_limit = "429" in err_msg or "quota" in err_msg.lower() or "resource" in err_msg.lower()
            if is_rate_limit and attempt < max_retries - 1:
                wait_time = 2 * (attempt + 1)
                print(f"[llm.decide] Rate limit / quota error encountered. Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            else:
                return DecisionResult(
                    is_tool_call=False,
                    error=f"LLM decision error: {err_msg}"
                )

    return DecisionResult(is_tool_call=False, error="LLM call failed after maximum retries.")
