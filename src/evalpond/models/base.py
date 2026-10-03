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
    raise ValueError(f"Unknown adapter: {cfg.adapter}")
