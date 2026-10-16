"""Verify that every drafted source_quote appears word-for-word in the notice."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QuoteCheckResult:
    passed: bool
    items: list[dict[str, Any]] = field(default_factory=list)
    failed_ids: list[str] = field(default_factory=list)


class QuoteGate:
    def check(self, notice_text: str, draft: dict[str, Any]) -> QuoteCheckResult:
        text = notice_text or ""
        items: list[dict[str, Any]] = []
        failed: list[str] = []

        for condition in draft.get("conditions") or []:
            cid = condition.get("id") or ""
            quote = condition.get("source_quote")
            ok = isinstance(quote, str) and quote != "" and quote in text
            items.append(
                {
                    "id": cid,
                    "source_quote": quote,
                    "ok": ok,
                }
            )
            if not ok:
                failed.append(cid)

        return QuoteCheckResult(passed=not failed, items=items, failed_ids=failed)
