"""
Gemini API Client for Natural Language SQL Generation.
Integrates google-genai SDK with schema grounding, prompt formatting,
and graceful offline fallback.
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Load .env file
load_dotenv(BASE_DIR / ".env")

from intelligence.query_templates import DATABASE_SCHEMA_PROMPT


class GeminiClient:
    """Client for generating SQL and natural language financial insights via Gemini."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[GeminiClient] Warning: Could not initialize Google GenAI SDK: {e}")
                self.client = None

    def is_configured(self) -> bool:
        """Returns True if Gemini API key is configured and client initialized."""
        return bool(self.client and self.api_key)

    def generate_sql(self, question: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Calls Gemini to convert natural language question to SQL.
        Returns: (sql_query, explanation) or (None, None) if unavailable.
        """
        if not self.is_configured():
            return None, "Gemini API key not configured. Operating in deterministic offline mode."

        prompt = f"""
{DATABASE_SCHEMA_PROMPT}

User Question: "{question}"

Generate the precise SQLite query to answer this question.
Enclose the query strictly within ```sql ... ``` code block.
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )
            raw_text = response.text.strip()

            # Extract SQL from code block
            sql_match = re.search(r"```(?:sql)?\s*([\s\S]*?)\s*```", raw_text, re.IGNORECASE)
            if sql_match:
                sql = sql_match.group(1).strip()
            else:
                sql = raw_text

            explanation = f"Generated via Gemini ({self.model_name}) based on relational portfolio schema."
            return sql, explanation
        except Exception as e:
            return None, f"Gemini API generation failed: {str(e)}"


# Singleton instance
default_gemini_client = GeminiClient()

if __name__ == "__main__":
    client = GeminiClient()
    print("Gemini Configured:", client.is_configured())
    if client.is_configured():
        sql, exp = client.generate_sql("How many portfolios do we have in total?")
        print("Generated SQL:", sql)
        print("Explanation:", exp)
    else:
        print("Offline mode active: No GEMINI_API_KEY detected in environment.")
