"""Circular Groq key pool. Stay on a key until Groq exhausts or rejects it."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

import httpx

from app.config import get_settings

logger = logging.getLogger("rightpath.groq")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# A key that is limited, revoked, or rejected cannot serve the next draft.
_EXHAUSTED_STATUS = {401, 403, 429}
_EXHAUSTED_MARKERS = (
    "rate limit",
    "rate_limit",
    "quota",
    "insufficient",
    "exceeded",
    "invalid api key",
    "invalid_api_key",
    "over capacity",
)


Poster = Callable[[str, dict[str, Any], float], httpx.Response]


def parse_keys(*chunks: str) -> list[str]:
    """Split comma-separated key lists. Drop blanks and duplicates, keep order."""
    keys: list[str] = []
    seen: set[str] = set()
    for chunk in chunks:
        for part in (chunk or "").replace("\n", ",").split(","):
            key = part.strip().strip('"').strip("'")
            if not key or key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return keys


def is_exhausted(status_code: int, body: str) -> bool:
    if status_code in _EXHAUSTED_STATUS:
        return True
    lowered = (body or "").lower()
    return any(marker in lowered for marker in _EXHAUSTED_MARKERS)


def _default_post(key: str, payload: dict[str, Any], timeout: float) -> httpx.Response:
    return httpx.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )


class GroqKeyPool:
    def __init__(self, keys: list[str], poster: Poster | None = None) -> None:
        self._keys = list(keys)
        self._index = 0
        self._lock = threading.Lock()
        self._poster = poster or _default_post

    def __len__(self) -> int:
        return len(self._keys)

    @property
    def index(self) -> int:
        return self._index

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float = 0,
        response_format: dict[str, str] | None = None,
        timeout: float = 45.0,
    ) -> str | None:
        """Return message content. On an exhausted key, try the next one in a circle."""
        if not self._keys:
            return None

        payload: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "messages": messages,
        }
        if response_format:
            payload["response_format"] = response_format

        with self._lock:
            start = self._index

        for step in range(len(self._keys)):
            idx = (start + step) % len(self._keys)
            try:
                response = self._poster(self._keys[idx], payload, timeout)
            except Exception as exc:
                logger.warning(
                    "Groq request failed on key %s of %s: %s",
                    idx + 1,
                    len(self._keys),
                    exc.__class__.__name__,
                )
                return None

            if response.status_code == 200:
                with self._lock:
                    self._index = idx
                try:
                    return response.json()["choices"][0]["message"]["content"]
                except Exception:
                    logger.warning("Groq key %s of %s returned an unreadable body", idx + 1, len(self._keys))
                    return None

            body = response.text[:400]
            if is_exhausted(response.status_code, body):
                logger.warning(
                    "Groq key %s of %s is exhausted (%s); switching to the next key",
                    idx + 1,
                    len(self._keys),
                    response.status_code,
                )
                with self._lock:
                    self._index = (idx + 1) % len(self._keys)
                continue

            logger.warning(
                "Groq key %s of %s returned %s: %s",
                idx + 1,
                len(self._keys),
                response.status_code,
                " ".join(body.split())[:180],
            )
            return None

        logger.warning("Every Groq key is exhausted")
        return None


_pool: GroqKeyPool | None = None
_signature: tuple[str, ...] | None = None
_pool_lock = threading.Lock()


def get_groq_pool() -> GroqKeyPool:
    global _pool, _signature
    settings = get_settings()
    keys = parse_keys(settings.groq_api_keys, settings.groq_api_key)
    signature = tuple(keys)
    with _pool_lock:
        if _pool is None or _signature != signature:
            _pool = GroqKeyPool(keys)
            _signature = signature
        return _pool


def reset_groq_pool() -> None:
    global _pool, _signature
    with _pool_lock:
        _pool = None
        _signature = None
