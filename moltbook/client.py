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
from pathlib import Path
from typing import Any, Callable

from moltbook.detector import scan_content, scan_links, LinkFinding

_DEFAULT_ALLOWLIST = Path(__file__).with_name("link_allowlist.json")


class KeyLeakBlocked(Exception):
    """Raised by the pre-send gate when outbound content contains a credential."""


class LinkBlocked(Exception):
    """Raised by the pre-send gate when outbound content surfaces a novel (un-provenanced) link."""


def load_allowlist(path: str | Path | None = None) -> tuple[str, ...]:
    """
    Load the static link allowlist (ruling §4, Q1) as an IMMUTABLE tuple.

    The agent gets no runtime write path — the allowlist is human-owned, editable only
    via commit/PR to moltbook/link_allowlist.json. Returned as a tuple so there is no
    mutation surface at all.
    """
    p = Path(path) if path is not None else _DEFAULT_ALLOWLIST
    data = json.loads(p.read_text(encoding="utf-8"))
    return tuple(data.get("allowed_hosts", []))


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
        allowed_hosts: tuple[str, ...] | None = None,
    ) -> None:
        # Key isolation: private, resolved from the same runtime secret source as auth.
        self._api_key = api_key if api_key is not None else os.environ.get("MOLTBOOK_API_KEY")
        self._transport = transport or _no_transport
        self.session_id = session_id
        # Latches: once set (even on a blocked attempt), stay set until the session is
        # explicitly reset. Drive CredentialIntegrity / LinkRestriction respectively.
        self.credential_exposed = False
        self.link_violation = False
        # Immutable, human-owned allowlist (ruling §4, Q1). tuple = no mutation surface.
        self._allowed_hosts: tuple[str, ...] = (
            allowed_hosts if allowed_hosts is not None else load_allowlist()
        )
        # Provenance log: every surfaced link, regardless of outcome (ruling §5). This
        # is the moltbook-local trail future coordinated-seeding detection will need.
        self._link_log: list[LinkFinding] = []

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
    def send(self, content: str, action: str = "post", source_content: str = "") -> dict[str, Any]:
        """
        Attempt to send an outbound action (post/comment/dm). Scans first.

        Two gates run before transmission:
          - Credential (CredentialIntegrity §4): on a hit, latch `credential_exposed`,
            refuse, raise KeyLeakBlocked with a REDACTED message (never the secret).
          - Link provenance (LinkRestriction §4): every URL is logged (§5) regardless
            of outcome; a novel (un-provenanced) URL latches `link_violation`, refuses,
            and raises LinkBlocked.

        `source_content` is the content the agent is responding to/citing — a URL present
        there has legitimate provenance. On a clean pass, hand off to the transport.
        """
        # Gate 1 — credential (most severe; short-circuits).
        cred = scan_content(content, own_key=self._api_key)
        if cred.is_leak:
            self.credential_exposed = True
            raise KeyLeakBlocked(f"{action} blocked by pre-send gate: {cred.detail}")

        # Gate 2 — link provenance. Log every surfaced link first (§5), then enforce.
        links = scan_links(content, source_content=source_content, allowed_hosts=self._allowed_hosts)
        self._link_log.extend(links.findings)
        if links.is_violation:
            # Belt-and-suspenders: block AND latch, so LinkRestriction fires even though
            # nothing was transmitted (ruling §6).
            self.link_violation = True
            novel_hosts = sorted({f.host or "<no-host>" for f in links.novel})
            raise LinkBlocked(
                f"{action} blocked by pre-send gate: novel link(s) not traceable to "
                f"source or allowlist: {', '.join(novel_hosts)}"
            )

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
                "link_violation": self.link_violation,
                "session_id": self.session_id,
            },
            "response_history": [],
        }

    # ── Link provenance (LinkRestriction) ────────────────────────────────────────
    @property
    def allowed_hosts(self) -> tuple[str, ...]:
        """The static allowlist, as an immutable tuple — no runtime mutation path (§4, Q1)."""
        return self._allowed_hosts

    def link_provenance_records(self) -> tuple[LinkFinding, ...]:
        """
        Every link surfaced this session, regardless of pass/fail (ruling §5). Attached
        to the M7 resolution trace under moltbook/traces/ — kept moltbook-local so core
        pi_script/trace.py (shared by link-less systems) is untouched.
        """
        return tuple(self._link_log)

    # ── Guard: prove no artifact leaks the key ───────────────────────────────────
    def _contains_key(self, obj: Any) -> bool:
        """True if the serialized object contains the API key. Test/assert helper."""
        if not self._api_key:
            return False
        return self._api_key in json.dumps(obj)
