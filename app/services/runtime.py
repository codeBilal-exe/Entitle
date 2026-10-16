"""Process-local runtime flags (kill switch) stored beside the SQLite DB."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RUNTIME_PATH = Path("data/runtime.json")


def _read() -> dict[str, Any]:
    if not RUNTIME_PATH.exists():
        return {"send_enabled": True}
    try:
        return json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"send_enabled": True}


def _write(data: dict[str, Any]) -> None:
    RUNTIME_PATH.parent.mkdir(exist_ok=True)
    RUNTIME_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def is_send_enabled() -> bool:
    return bool(_read().get("send_enabled", True))


def set_send_enabled(enabled: bool) -> dict[str, Any]:
    data = _read()
    data["send_enabled"] = bool(enabled)
    _write(data)
    return data
