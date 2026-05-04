"""Thin OpenAI client wrapper with retries and JSON-mode."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from ..config import openai_api_key, openai_model


@dataclass
class LlmCall:
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class OpenAiClient:
    def __init__(self, model: str | None = None):
        self.model = model or openai_model()
        self._client = None

    def _ensure(self):
        if self._client is not None:
            return
        api_key = openai_api_key()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY missing — set it in .env")
        # Use the Langfuse-instrumented OpenAI wrapper so each chat completion
        # is logged as a generation under the active trace.
        from ..tracing import init_langfuse_env

        init_langfuse_env()
        from langfuse.openai import OpenAI

        self._client = OpenAI(api_key=api_key)

    def chat_json(
        self,
        system: str,
        user: str,
        max_tokens: int = 1500,
        retries: int = 3,
    ) -> tuple[list | dict, LlmCall]:
        self._ensure()
        last_err: Exception | None = None
        for attempt in range(retries):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format={"type": "json_object"},
                    max_completion_tokens=max_tokens,
                )
                content = resp.choices[0].message.content or "{}"
                parsed = json.loads(content)
                call = LlmCall(
                    model=self.model,
                    prompt_tokens=getattr(resp.usage, "prompt_tokens", 0) or 0,
                    completion_tokens=getattr(resp.usage, "completion_tokens", 0) or 0,
                )
                return parsed, call
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"OpenAI call failed after {retries} attempts: {last_err}")
