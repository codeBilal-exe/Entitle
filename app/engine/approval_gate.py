"""Consent-gated sending. Requires APPROVED state and matching payload hash."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ApplicationState(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    APPROVED = "approved"
    SENT = "sent"
    FAILED = "failed"


@dataclass
class GateDecision:
    allowed: bool
    reason: str
    application_id: str | None = None


class ApprovalGate:
    def payload_hash(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def approve(self, state: str, payload: dict[str, Any]) -> tuple[str, str]:
        """Return (new_state, approval_hash)."""
        if state not in {ApplicationState.DRAFT.value, ApplicationState.READY.value}:
            raise ValueError(f"Cannot approve from state {state}")
        return ApplicationState.APPROVED.value, self.payload_hash(payload)

    def authorize_send(
        self,
        *,
        application_id: str,
        state: str,
        stored_hash: str | None,
        payload: dict[str, Any],
        already_sent_ids: set[str] | None = None,
    ) -> GateDecision:
        already_sent_ids = already_sent_ids or set()
        if application_id in already_sent_ids or state == ApplicationState.SENT.value:
            return GateDecision(
                allowed=False,
                reason="already_sent",
                application_id=application_id,
            )
        if state != ApplicationState.APPROVED.value:
            return GateDecision(
                allowed=False,
                reason="not_approved",
                application_id=application_id,
            )
        if not stored_hash:
            return GateDecision(
                allowed=False,
                reason="missing_approval_hash",
                application_id=application_id,
            )
        current = self.payload_hash(payload)
        if current != stored_hash:
            return GateDecision(
                allowed=False,
                reason="hash_mismatch",
                application_id=application_id,
            )
        return GateDecision(allowed=True, reason="ok", application_id=application_id)
