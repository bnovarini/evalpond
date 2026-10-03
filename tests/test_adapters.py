import base64

import pytest

from evalpond.models import cloud
from evalpond.models.base import build_adapter
from evalpond.schema import DocumentRef, ModelConfig


@pytest.fixture
def pdf(tmp_path):
    p = tmp_path / "d.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    return str(p)


def test_anthropic_request_shape_and_parse(monkeypatch, pdf):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    seen = {}

    def fake(url, headers, body, timeout=0):
        seen.update(url=url, headers=headers, body=body)
        return {"content": [{"type": "text", "text": '{"a": 1}'}], "usage": {"input_tokens": 1000, "output_tokens": 100}}

    monkeypatch.setattr(cloud, "post_json", fake)
    cfg = ModelConfig(name="c", adapter="anthropic", model="m", params={"price_in": 3, "price_out": 15})
    out = build_adapter(cfg).run("PROMPT", DocumentRef(pdf_paths=[pdf], oracle={"secret": "answer"}))
    assert out.text == '{"a": 1}' and out.doc_mode == "native"
    assert abs(out.cost_usd - (1000 * 3 + 100 * 15) / 1e6) < 1e-9
    blocks = seen["body"]["messages"][0]["content"]
    assert blocks[0]["type"] == "document" and base64.b64decode(blocks[0]["source"]["data"]).startswith(b"%PDF")
    assert "secret" not in str(seen["body"])  # the oracle must never reach a real model


def test_text_fallback_when_not_native(monkeypatch, pdf):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setattr(cloud, "post_json", lambda *a, **k: {"output_text": "{}", "usage": {}})
    cfg = ModelConfig(name="o", adapter="openai", model="m")
    out = build_adapter(cfg).run("P", DocumentRef(pdf_paths=[pdf], prefer_native=False))
    assert out.doc_mode == "text"


def test_missing_key_is_a_clear_error(monkeypatch, pdf):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = ModelConfig(name="c", adapter="anthropic", model="m")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        build_adapter(cfg).run("P", DocumentRef())


def test_compatible_adapter_needs_base_url():
    with pytest.raises(ValueError):
        build_adapter(ModelConfig(name="x", adapter="litellm", model="m"))
