"""
Thin wrapper around the OpenAI client that:
- reads config from settings
- supports structured output via Pydantic response_format
- provides a simple chat() helper for plain text completions

Works with OpenAI and any compatible provider (Ollama, vLLM, etc.)
by pointing OPENAI_BASE_URL at the local endpoint.
"""
from __future__ import annotations

import json
from typing import Optional, Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)

_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    return _client


def chat(system: str, user: str, temperature: float = 0.2) -> str:
    """Plain text completion. Returns the assistant message content string."""
    client = get_client()
    response = client.chat.completions.create(
        model=settings.model_name,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content or ""


def chat_structured(
    system: str,
    user: str,
    response_model: Type[T],
    temperature: float = 0.2,
    max_retries: int = 2,
) -> T:
    """
    Structured output completion that returns a validated Pydantic model.
    Uses json_object mode with field hints in the prompt — works reliably
    with gpt-4o and any OpenAI-compatible provider.
    """
    client = get_client()

    schema = response_model.model_json_schema()
    field_hints = ", ".join(
        f'"{k}": <value>'
        for k in response_model.model_fields.keys()
    )
    json_instruction = (
        f"\n\nRespond with ONLY a JSON object (no markdown, no extra text) "
        f"with exactly these top-level fields: {{{field_hints}}}.\n"
        f"Full schema:\n{json.dumps(schema, indent=2)}"
    )

    last_error: Exception = RuntimeError("unknown")
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=settings.model_name,
                temperature=temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system + json_instruction},
                    {"role": "user", "content": user},
                ],
            )
            raw = response.choices[0].message.content or "{}"
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return response_model.model_validate_json(raw.strip())
        except Exception as e:
            last_error = e
            if attempt == max_retries:
                raise RuntimeError(
                    f"Failed to get structured output after {max_retries + 1} attempts: {last_error}"
                ) from last_error

    raise RuntimeError("chat_structured: unexpected state")