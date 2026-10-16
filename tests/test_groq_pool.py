"""Groq key circle: an exhausted key advances, and the next call starts there."""

import httpx

from app.services.groq_pool import GroqKeyPool, is_exhausted, parse_keys


def _response(status: int, body: str) -> httpx.Response:
    return httpx.Response(status, text=body)


def test_parse_keys_keeps_order_and_drops_blanks():
    keys = parse_keys(" a , b,a ", "", "c")
    assert keys == ["a", "b", "c"]


def test_exhausted_statuses_and_quota_text():
    assert is_exhausted(429, "")
    assert is_exhausted(401, "")
    assert is_exhausted(200, "rate_limit_exceeded")
    assert not is_exhausted(400, "invalid json schema")
    assert not is_exhausted(500, "internal error")


def test_circle_switches_when_a_key_runs_out_and_stays_on_the_working_key():
    used: list[str] = []

    def poster(key: str, payload: dict, timeout: float) -> httpx.Response:
        used.append(key)
        if key == "k1":
            return _response(429, '{"error":{"code":"rate_limit_exceeded"}}')
        return _response(
            200,
            '{"choices":[{"message":{"content":"ok"}}]}',
        )

    pool = GroqKeyPool(["k1", "k2", "k3"], poster=poster)
    assert pool.complete([{"role": "user", "content": "hi"}], model="llama") == "ok"
    assert used == ["k1", "k2"]
    assert pool.index == 1

    assert pool.complete([{"role": "user", "content": "again"}], model="llama") == "ok"
    assert used == ["k1", "k2", "k2"]


def test_circle_wraps_after_the_last_key_and_stops_when_all_are_exhausted():
    used: list[str] = []

    def poster(key: str, payload: dict, timeout: float) -> httpx.Response:
        used.append(key)
        return _response(429, "quota exceeded")

    pool = GroqKeyPool(["k1", "k2"], poster=poster)
    pool._index = 1
    assert pool.complete([{"role": "user", "content": "hi"}], model="llama") is None
    assert used == ["k2", "k1"]
    # Next call starts again at k2, the key that followed the last failure.
    assert pool.index == 1


def test_other_errors_do_not_burn_the_remaining_keys():
    used: list[str] = []

    def poster(key: str, payload: dict, timeout: float) -> httpx.Response:
        used.append(key)
        return _response(500, "upstream down")

    pool = GroqKeyPool(["k1", "k2"], poster=poster)
    assert pool.complete([{"role": "user", "content": "hi"}], model="llama") is None
    assert used == ["k1"]
    assert pool.index == 0
