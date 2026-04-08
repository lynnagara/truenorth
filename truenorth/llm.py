from abc import ABC, abstractmethod
from typing import Any

import anthropic
import ollama

from truenorth.config import LLMConfig, LLMProvider

_UNSUPPORTED_KEYWORDS = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}


def _clean_schema(schema: dict) -> dict:
    """Recursively remove JSON schema keywords unsupported by Anthropic's structured outputs."""
    return {
        k: (
            _clean_schema(v)
            if isinstance(v, dict)
            else [_clean_schema(i) if isinstance(i, dict) else i for i in v]
            if isinstance(v, list)
            else v
        )
        for k, v in schema.items()
        if k not in _UNSUPPORTED_KEYWORDS
    }


class LLM(ABC):
    @abstractmethod
    def generate(self, prompt: str, json_schema: dict[str, Any] | None = None) -> str: ...


class OllamaLLM(LLM):
    def __init__(self, model: str):
        self._model = model

    def generate(self, prompt: str, json_schema: dict[str, Any] | None = None) -> str:
        response = ollama.chat(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            format=json_schema,
        )
        if response.message.content is None:
            raise ValueError("LLM returned empty response")
        return response.message.content


class AnthropicLLM(LLM):
    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int,
    ):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, prompt: str, json_schema: dict[str, Any] | None = None) -> str:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if json_schema is not None:
            kwargs["output_config"] = {
                "format": {"type": "json_schema", "schema": _clean_schema(json_schema)}
            }
        response = self._client.messages.create(**kwargs)
        block = response.content[0]
        if not hasattr(block, "text"):
            raise ValueError("Anthropic returned no text content")
        return block.text  # type: ignore[attr-defined]


def create_llm(
    config: LLMConfig,
    anthropic_api_key: str | None = None,
) -> LLM:
    if config.provider == LLMProvider.LOCAL:
        return OllamaLLM(model=config.model)
    if config.provider == LLMProvider.ANTHROPIC:
        assert anthropic_api_key is not None
        return AnthropicLLM(
            api_key=anthropic_api_key,
            model=config.model,
            max_tokens=config.max_tokens,
        )
    raise ValueError(f"Unsupported LLM provider: {config.provider}")
