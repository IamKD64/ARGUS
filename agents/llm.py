
"""Ollama client for the NEXUS multi-agent BI system."""

import json
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")
KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "600"))

# Reuse HTTP connections across agent calls.
http = requests.Session()


def chat(
    prompt: str,
    system: str = "You are a precise assistant.",
    temperature: float = 0,
    num_predict: int = 384,
) -> str:
    """Send a chat request to the local Ollama model."""

    response = http.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": LLM_MODEL,
            "stream": False,
            "keep_alive": KEEP_ALIVE,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "options": {
                "temperature": temperature,
                "num_predict": num_predict,
                "num_ctx": 4096,
            },
        },
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()
    message = data.get("message", {}).get("content", "")

    if not message.strip():
        raise ValueError("Ollama returned an empty response.")

    return message.strip()


def extract_json(text: str):
    """Extract a JSON object or array from an LLM response."""

    cleaned = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)

    for opener, closer in (("{", "}"), ("[", "]")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)

        if start != -1 and end > start:
            candidate = cleaned[start:end + 1]

            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    raise ValueError(f"No valid JSON found: {text[:200]!r}")


def clean_sql(text: str) -> str:
    """Remove Markdown fences from generated SQL."""

    match = re.search(
        r"```(?:sql)?\s*(.*?)```",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    sql = match.group(1) if match else text

    return sql.strip().rstrip(";")
