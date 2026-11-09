"""
Gemini API Client for Natural Language SQL Generation.
Integrates google-genai SDK with schema grounding, prompt formatting,
runtime key configuration, live connection testing, and graceful offline fallback.
"""

import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Load .env file
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

from intelligence.query_templates import DATABASE_SCHEMA_PROMPT

FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash"]


class GeminiClient:
    """Client for generating SQL and natural language financial insights via Gemini."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.client = None
        self._init_client()

    def _init_client(self):
        """Initializes the Google GenAI SDK client if an API key is available."""
        if self.api_key and self.api_key.strip():
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key.strip())
            except Exception as e:
                print(f"[GeminiClient] Warning: Could not initialize Google GenAI SDK: {e}")
                self.client = None
        else:
            self.client = None

    def is_configured(self) -> bool:
        """Returns True if Gemini API key is configured and client initialized."""
        return bool(self.client and self.api_key and self.api_key.strip())

    def get_status(self) -> Dict[str, Any]:
        """Returns safe status metadata for UI display."""
        configured = self.is_configured()
        masked = ""
        if configured and self.api_key:
            k = self.api_key.strip()
            if len(k) > 8:
                masked = f"{k[:6]}...{k[-4:]}"
            else:
                masked = "********"
        return {
            "configured": configured,
            "masked_key": masked,
            "model": self.model_name,
            "provider": "Google Gemini",
            "status_label": "CONNECTED" if configured else "OFFLINE / LOCAL HYBRID",
        }

    def set_api_key(self, api_key: str, save_to_env: bool = False) -> Tuple[bool, str]:
        """
        Updates the active API key at runtime and optionally persists to .env file.
        """
        clean_key = api_key.strip() if api_key else ""
        if not clean_key:
            self.api_key = None
            self.client = None
            if save_to_env and ENV_PATH.exists():
                try:
                    lines = [l for l in ENV_PATH.read_text(encoding="utf-8").splitlines() if not l.startswith("GEMINI_API_KEY=")]
                    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
                except Exception:
                    pass
            return True, "API key cleared. System reverted to local deterministic engine."

        self.api_key = clean_key
        self._init_client()

        if save_to_env:
            try:
                content = ""
                if ENV_PATH.exists():
                    lines = [l for l in ENV_PATH.read_text(encoding="utf-8").splitlines() if not l.startswith("GEMINI_API_KEY=")]
                    lines.append(f"GEMINI_API_KEY={clean_key}")
                    content = "\n".join(lines) + "\n"
                else:
                    content = f"GEMINI_API_KEY={clean_key}\n"
                ENV_PATH.write_text(content, encoding="utf-8")
            except Exception as e:
                print(f"[GeminiClient] Warning: Could not save key to .env: {e}")

        return True, "API key configured successfully."

    def test_connection(self, test_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Tests live communication with Google Gemini API by generating a minimal SQL token.
        """
        target_key = (test_key or self.api_key or "").strip()
        if not target_key:
            return {
                "success": False,
                "error": "No API key provided. Please supply a valid Google Gemini API key.",
                "latency_ms": 0,
            }

        try:
            from google import genai
            test_client = genai.Client(api_key=target_key)
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to initialize Google GenAI SDK: {str(e)}",
                "latency_ms": 0,
            }

        start = time.perf_counter()
        last_error = None
        for model in [self.model_name] + [m for m in FALLBACK_MODELS if m != self.model_name]:
            try:
                prompt = "Respond with strictly ```sql SELECT 1; ``` and nothing else."
                resp = test_client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                latency = round((time.perf_counter() - start) * 1000.0, 2)
                self.model_name = model
                # If testing succeeded and no key had been active, set it
                if test_key and not self.api_key:
                    self.api_key = test_key
                    self.client = test_client

                return {
                    "success": True,
                    "message": f"Successfully verified connection to Google Gemini ({model}).",
                    "model": model,
                    "latency_ms": latency,
                    "response_preview": (resp.text or "").strip()[:60],
                }
            except Exception as e:
                last_error = str(e)
                continue

        latency = round((time.perf_counter() - start) * 1000.0, 2)
        return {
            "success": False,
            "error": f"API verification failed: {last_error}",
            "latency_ms": latency,
        }

    def generate_sql(
        self,
        question: str,
        target_dataset: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Calls Gemini to convert natural language question to validated SQL.
        Returns: (sql_query, explanation) or (None, error_message)
        """
        if not self.is_configured():
            return None, "Gemini API key not configured. Operating in deterministic offline mode."

        scope_instruction = ""
        if target_dataset and target_dataset.strip() and target_dataset.lower() not in ["all", "auto"]:
            clean_ds = target_dataset.strip().lower()
            scope_instruction = f"""
### User Selected Scope:
The user has explicitly selected the table '{clean_ds}'.
Prioritize querying '{clean_ds}' or joining it with related tables as needed.
"""

        prompt = f"""
{DATABASE_SCHEMA_PROMPT}

{scope_instruction}

User Question: "{question}"

Generate the precise SQLite query to answer this question.
Enclose the query strictly within ```sql ... ``` code block.
"""
        last_err = None
        for model in [self.model_name] + [m for m in FALLBACK_MODELS if m != self.model_name]:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                raw_text = response.text.strip()

                # Extract SQL from code block
                sql_match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", raw_text, re.IGNORECASE)
                if sql_match:
                    sql = sql_match.group(1).strip()
                else:
                    sql = raw_text

                explanation = f"Generated dynamically via Google Gemini ({model}) grounded in relational schema."
                return sql, explanation
            except Exception as e:
                last_err = str(e)
                continue

        return None, f"Gemini API generation failed across models: {last_err}"


# Singleton instance
default_gemini_client = GeminiClient()
