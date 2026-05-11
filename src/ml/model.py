from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


class LLMConfigError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


def get_client() -> OpenAI:
    api_key = os.getenv("AI_API_KEY")
    base_url = os.getenv("AI_BASE_URL", "https://ai.api.cloud.yandex.net/v1")

    if not api_key:
        raise LLMConfigError(
            "AI_API_KEY is not set. create .env file or set environment variable"
        )

    return OpenAI(api_key=api_key, base_url=base_url)


def get_model_name() -> str:
    model = os.getenv("AI_MODEL")

    if not model:
        raise LLMConfigError(
            "AI_MODEL is not set. add it to .env, for example gpt://folder_id/yandexgpt/rc"
        )

    return model


def complete_text(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 2000,
) -> str:
    client = get_client()
    model = get_model_name()

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    content = response.choices[0].message.content

    if not content:
        raise LLMResponseError("model returned empty response")

    return content.strip()


def extract_json_object(text: str) -> str:
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise LLMResponseError("model response does not contain json object")

    return match.group(0)


def complete_json(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.1,
    max_tokens: int = 2500,
) -> dict[str, Any]:
    text = complete_text(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    json_text = extract_json_object(text)

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as error:
        raise LLMResponseError(f"model returned invalid json: {error}") from error


def is_llm_configured() -> bool:
    return bool(os.getenv("AI_API_KEY") and os.getenv("AI_MODEL"))