"""Tiny JSON-over-HTTP helper (stdlib only, so no SDK dependencies)."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def api_key(env_name: str) -> str:
    key = os.environ.get(env_name, "")
    if not key:
        raise RuntimeError(f"Environment variable {env_name} is not set. Keys are never stored in the repo.")
    return key


def post_json(url: str, headers: dict[str, str], body: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise RuntimeError(f"HTTP {e.code} from {url.split('/')[2]}: {detail}") from None
