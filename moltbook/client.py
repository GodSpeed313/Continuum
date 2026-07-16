"""
moltbook/client.py — M7 Moltbook client with key isolation and a pre-send gate.

Implements the two prevention mechanisms of docs/m7_credential_integrity_ruling.md:

  §5.1 Key isolation (primary defense for the OWN key)
        The API key lives only in the transport/auth layer. It sets the
        `Authorization: Bearer` header and is NEVER placed into the context the
        model composes content from (`build_generation_context`). The model cannot
        emit a string it has never seen — no injection, however encoded, can leak
        a key that was never in scope.

  §4/§5 Pre-send gate (nets relayed foreign keys + client-code bugs)
        `send()` scans candidate content BEFORE transmission (moltbook.detector).
        On a hit it refuses to send, latches `credential_exposed = True`, and raises
        KeyLeakBlocked. A blocked attempt still latches (belt-and-suspenders, §5): a
        prevented exfiltration is itself proof the agent was manipulated and must stop.

The Pi Script constraint governs the consequence: `snapshot()` emits the state the
resolver evaluates, and CredentialIntegrity (`credential_exposed must equal false`)
freezes + escalates the session. Prevention lives here in the client; enforcement and
the redacted audit trace live in Pi Script — do not conflate the two (ruling §5).

This module makes NO live network calls by default: `transport` is injected, and the
default refuses to fire. Wire a real transport explicitly for deployment.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from moltbook.detector import scan_content


class KeyLeakBlocked(Exception):
    """Raised by the pre-send gate when outbound content contains a credential."""


def _no_transport(**_: Any) -> dict[str, Any]:
    raise RuntimeError(
        "MoltbookClient has no transport wired. Inject a real HTTP transport "
        "explicitly for live deployment — the client never fires network calls "
        "on its own."
    )


class MoltbookClient:
    """
    A Continuum-governed Moltbook agent client.

    The API key is held privately and used only to build the auth header. It is never
    returned, never placed in the model-facing context, and never written into the
    governance snapshot.
    """

    def __init__(
        self,
        api_key: str | None = None,
        transport: Callable[..., dict[str, Any]] | None = None,
        session_id: str = "moltbook-session",
    ) -> None:
        # Key isolation: private, resolved from the same runtime secret source as auth.
        self._api_key = api_key if api_key is not None else os.environ.get("MOLTBOOK_API_KEY")
        self._transport = transport or _no_transport
        self.session_id = session_id
        # Latch: once a leak is detected (even if blocked), stays set until the key is
        # rotated and the session explicitly reset. Drives CredentialIntegrity.
        self.credential_exposed = False

    # ── Auth (the ONLY place the key is touched) ─────────────────────────────────
    def _auth_header(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    # ── Key isolation (§5.1) ─────────────────────────────────────────────────────
    def build_generation_context(self, system: str, incoming: str) -> dict[str, Any]:
        """
        Assemble the context handed to the model for composing a reply.

        Contains the system prompt and the incoming (UNTRUSTED — possibly injection-
        laden) platform content the agent is reacting to. It MUST NOT contain the API
        key. This is the object the key-isolation test asserts is key-free.
        """
        return {
            "system": system,
            "incoming": incoming,       # untrusted; treat as data, never as instructions
            "session_id": self.session_id,
        }

    # ── Pre-send gate (§4/§5) ────────────────────────────────────────────────────
    def send(self, content: str, action: str = "post") -> dict[str, Any]:
        """
        Attempt to send an outbound action (post/comment/dm). Scans first.

        On a credential hit: latch `credential_exposed`, refuse to send, raise
        KeyLeakBlocked with a REDACTED message (never the secret). Otherwise hand
        off to the injected transport with the auth header.
        """
        scan = scan_content(content, own_key=self._api_key)
        if scan.is_leak:
            # Belt-and-suspenders: block AND latch, so CredentialIntegrity fires even
            # though nothing was transmitted (ruling §5).
            self.credential_exposed = True
            raise KeyLeakBlocked(f"{action} blocked by pre-send gate: {scan.detail}")

        return self._transport(
            action=action,
            content=content,
            headers=self._auth_header(),
        )

    # ── Governance snapshot for the Pi Script resolver ───────────────────────────
    def snapshot(self, trigger_type: str = "event") -> dict[str, Any]:
        """
        Emit the state snapshot the resolver evaluates against moltbook.pi. Carries
        the `credential_exposed` latch and the session id — never the key.
        """
        return {
            "trigger_type": trigger_type,
            "entity": "MoltbookSession",
            "entity_state": {
                "credential_exposed": self.credential_exposed,
                "session_id": self.session_id,
            },
            "response_history": [],
        }

    # ── Guard: prove no artifact leaks the key ───────────────────────────────────
    def _contains_key(self, obj: Any) -> bool:
        """True if the serialized object contains the API key. Test/assert helper."""
        if not self._api_key:
            return False
        return self._api_key in json.dumps(obj)
