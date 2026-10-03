"""Anthropic, OpenAI and OpenAI-compatible adapters. Plain HTTP, no vendor SDKs.

Model ids and prices change often, so neither is hard-coded: set `model` in models.yaml, and set
`price_in` / `price_out` (USD per million tokens) in `params` if you want cost estimates.
These adapters never send the task's expected answer (`DocumentRef.oracle` is mock-only).
"""
from __future__ import annotations

import base64
from pathlib import Path

from ..schema import DocumentRef, ModelConfig, ModelOutput
from .http import api_key, post_json


def _b64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode()


def _cost(cfg: ModelConfig, tin: int, tout: int) -> float:
    p_in, p_out = float(cfg.params.get("price_in", 0)), float(cfg.params.get("price_out", 0))
    return round(tin * p_in / 1e6 + tout * p_out / 1e6, 6)


class AnthropicAdapter:
    def __init__(self, cfg: ModelConfig):
        self.cfg, self.name = cfg, cfg.name
        self.url = cfg.params.get("base_url", "https://api.anthropic.com") + "/v1/messages"

    def build_body(self, prompt: str, doc: DocumentRef) -> tuple[dict, str]:
        native = doc.prefer_native and bool(doc.pdf_paths)
        content: list[dict] = []
        if native:
            for p in doc.pdf_paths:
                content.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": _b64(p)}})
        content.append({"type": "text", "text": prompt})
        body = {"model": self.cfg.model, "max_tokens": int(self.cfg.params.get("max_tokens", 1024)),
                "temperature": float(self.cfg.params.get("temperature", 0)),
                "messages": [{"role": "user", "content": content}]}
        return body, "native" if native else "text"

    def run(self, prompt: str, doc: DocumentRef) -> ModelOutput:
        body, mode = self.build_body(prompt, doc)
        data = post_json(self.url, {"x-api-key": api_key(self.cfg.api_key_env or "ANTHROPIC_API_KEY"),
                                    "anthropic-version": "2023-06-01"}, body)
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        u = data.get("usage", {})
        return ModelOutput(text=text, input_tokens=u.get("input_tokens", 0), output_tokens=u.get("output_tokens", 0),
                           cost_usd=_cost(self.cfg, u.get("input_tokens", 0), u.get("output_tokens", 0)),
                           raw={"id": data.get("id"), "stop_reason": data.get("stop_reason")}, doc_mode=mode)


class OpenAIAdapter:
    """OpenAI Responses API. Sends PDFs natively when asked, otherwise the text layer."""

    def __init__(self, cfg: ModelConfig):
        self.cfg, self.name = cfg, cfg.name
        self.url = cfg.params.get("base_url", "https://api.openai.com") + "/v1/responses"

    def build_body(self, prompt: str, doc: DocumentRef) -> tuple[dict, str]:
        native = doc.prefer_native and bool(doc.pdf_paths)
        content: list[dict] = []
        if native:
            for p in doc.pdf_paths:
                content.append({"type": "input_file", "filename": Path(p).name,
                                "file_data": f"data:application/pdf;base64,{_b64(p)}"})
        content.append({"type": "input_text", "text": prompt})
        body = {"model": self.cfg.model, "input": [{"role": "user", "content": content}],
                "max_output_tokens": int(self.cfg.params.get("max_tokens", 1024))}
        if "temperature" in self.cfg.params:
            body["temperature"] = float(self.cfg.params["temperature"])
        return body, "native" if native else "text"

    def run(self, prompt: str, doc: DocumentRef) -> ModelOutput:
        body, mode = self.build_body(prompt, doc)
        data = post_json(self.url, {"authorization": "Bearer " + api_key(self.cfg.api_key_env or "OPENAI_API_KEY")}, body)
        text = data.get("output_text") or "".join(
            c.get("text", "") for item in data.get("output", []) for c in item.get("content", []) if c.get("type") == "output_text")
        u = data.get("usage", {})
        return ModelOutput(text=text, input_tokens=u.get("input_tokens", 0), output_tokens=u.get("output_tokens", 0),
                           cost_usd=_cost(self.cfg, u.get("input_tokens", 0), u.get("output_tokens", 0)),
                           raw={"id": data.get("id")}, doc_mode=mode)


class OpenAICompatibleAdapter:
    """Any /v1/chat/completions endpoint (local servers, LiteLLM proxy, other vendors). Text only."""

    def __init__(self, cfg: ModelConfig):
        self.cfg, self.name = cfg, cfg.name
        base = cfg.params.get("base_url")
        if not base:
            raise ValueError("litellm/openai-compatible adapter needs params.base_url, e.g. http://localhost:4000")
        self.url = base.rstrip("/") + "/v1/chat/completions"

    def build_body(self, prompt: str, doc: DocumentRef) -> tuple[dict, str]:
        return ({"model": self.cfg.model, "messages": [{"role": "user", "content": prompt}],
                 "temperature": float(self.cfg.params.get("temperature", 0)),
                 "max_tokens": int(self.cfg.params.get("max_tokens", 1024))}, "text")

    def run(self, prompt: str, doc: DocumentRef) -> ModelOutput:
        body, mode = self.build_body(prompt, doc)
        headers = {}
        if self.cfg.api_key_env:
            headers["authorization"] = "Bearer " + api_key(self.cfg.api_key_env)
        data = post_json(self.url, headers, body)
        text = data["choices"][0]["message"]["content"] or ""
        u = data.get("usage", {})
        return ModelOutput(text=text, input_tokens=u.get("prompt_tokens", 0), output_tokens=u.get("completion_tokens", 0),
                           cost_usd=_cost(self.cfg, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)),
                           raw={"id": data.get("id")}, doc_mode=mode)
