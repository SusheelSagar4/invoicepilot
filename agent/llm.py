"""
LLM Access Layer for InvoicePilot.
This module is the ONLY file in the project authorized to communicate
with the LLM provider (Google Gemini API).
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

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


def ask(prompt: str) -> str:
    """
    Sends a text prompt to the Gemini LLM and returns the generated text response.

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
