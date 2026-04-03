from abc import ABC, abstractmethod

import ollama

from truenorth.config import LLMConfig, LLMProvider


class LLM(ABC):
    @abstractmethod
    def send_message(self, prompt: str) -> str: ...


class OllamaLLM(LLM):
    def __init__(self, model: str):
        self._model = model

    def send_message(self, prompt: str) -> str:
        response = ollama.chat(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.message.content


class AnthropicLLM(LLM):
    def send_message(self, prompt: str) -> str:
        raise NotImplementedError


def create_llm(config: LLMConfig) -> LLM:
    if config.provider == LLMProvider.LOCAL:
        return OllamaLLM(model=config.model)
    if config.provider == LLMProvider.ANTHROPIC:
        return AnthropicLLM()
    raise ValueError(f"Unsupported LLM provider: {config.provider}")
