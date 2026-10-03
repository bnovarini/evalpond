from __future__ import annotations

from typing import Protocol

from ..schema import DocumentRef, ModelConfig, ModelOutput


class ModelAdapter(Protocol):
    name: str

    def run(self, prompt: str, document: DocumentRef) -> ModelOutput: ...


def build_adapter(cfg: ModelConfig) -> ModelAdapter:
    if cfg.adapter == "mock":
        from .mock import MockAdapter

        return MockAdapter(cfg)
    if cfg.adapter == "anthropic":
        from .cloud import AnthropicAdapter

        return AnthropicAdapter(cfg)
    if cfg.adapter == "openai":
        from .cloud import OpenAIAdapter

        return OpenAIAdapter(cfg)
    if cfg.adapter in ("litellm", "openai-compatible"):
        from .cloud import OpenAICompatibleAdapter

        return OpenAICompatibleAdapter(cfg)
    raise ValueError(f"Unknown adapter: {cfg.adapter}")
