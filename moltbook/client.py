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

from moltbook.detector import scan_content, scan_links, scan_identity, LinkFinding

_DEFAULT_ALLOWLIST = Path(__file__).with_name("link_allowlist.json")


class KeyLeakBlocked(Exception):
    """Raised by the pre-send gate when outbound content contains a credential."""


class LinkBlocked(Exception):
    """Raised by the pre-send gate when outbound content surfaces a novel (un-provenanced) link."""


class IdentityDriftBlocked(Exception):
    """Raised by the pre-send gate when outbound content contradicts the session-start identity."""


class AutonomousPostingPaused(Exception):
    """
    Raised when an autonomous send is attempted while the §7 CadenceIntegrity pause is
    latched (cadence ruling §7). Distinct from frozen: the pause blocks only autonomous
    posts/comments/DMs — read-only observation continues, and an explicitly
    human-authorized send still goes through the pre-send gates and out.
    """


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
        declared_handle: str = "",
        declared_name: str | None = None,
        declared_roles: tuple[str, ...] = (),
        cadence_store: Any | None = None,
        citation_store: Any | None = None,
    ) -> None:
        # Fail closed on a missing identity baseline (addendum A1): with no declared
        # handle the known-identity set would be {""} and the identity gate would fire
        # on ANY self-naming — missing configuration masquerading as identity drift.
        # A governed client either has a trustworthy baseline or does not construct.
        # (Deliberately NOT an auto-disable: silently running with a constraint off is
        # the same silent-assumption failure in the other direction.)
        if not declared_handle.strip():
            raise ValueError(
                "declared_handle is required: IdentityIntegrity cannot run without "
                "a session-start identity baseline (addendum A1)"
            )
        # Key isolation: private, resolved from the same runtime secret source as auth.
        self._api_key = api_key if api_key is not None else os.environ.get("MOLTBOOK_API_KEY")
        self._transport = transport or _no_transport
        self.session_id = session_id
        # Latches: once set (even on a blocked attempt), stay set until the session is
        # explicitly reset. Drive CredentialIntegrity / LinkRestriction / IdentityIntegrity.
        self.credential_exposed = False
        self.link_violation = False
        self.identity_drift = False
        # Declared identity captured ONCE at session start, held immutable for the session
        # (IdentityIntegrity §6/§7). A fresh client == a fresh session == a legitimate reset,
        # so a between-session identity change is not a within-session violation (ruling §2).
        self._declared_handle = declared_handle
        self._declared_name = declared_name
        self._declared_roles = tuple(declared_roles)
        # Immutable, human-owned allowlist (ruling §4, Q1). tuple = no mutation surface.
        self._allowed_hosts: tuple[str, ...] = (
            allowed_hosts if allowed_hosts is not None else load_allowlist()
        )
        # §7 pause plumbing (cadence + citation rulings): each longitudinal store owns
        # its persistent pause latch — it must survive process restarts and clear only
        # via explicit human reset. The client just consults them; either latch pauses.
        self._cadence_store = cadence_store
        self._citation_store = citation_store
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
    def send(
        self,
        content: str,
        action: str = "post",
        source_content: str = "",
        human_authorized: bool = False,
        parent_post_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Attempt to send an outbound action (post/comment/dm). Scans first.

        Scan-all-then-block (addendum A5, grounded in v0.1 Q1: "no violation is
        silently dropped"): ALL detectors run on every attempt and EVERY finding
        latches, so the resolver rules on the full co-active set — not just the
        first gate in procedural order. The link log is always written (§5), even
        when another gate also fires. Only after everything is latched does the
        gate block, raising the most severe applicable exception:
        KeyLeakBlocked > LinkBlocked > IdentityDriftBlocked. Credential messages
        stay REDACTED (never the secret).

        `source_content` is the content the agent is responding to/citing — a URL present
        there has legitimate provenance. On a clean pass, hand off to the transport.

        `parent_post_id` identifies the post a reply/comment targets (the real
        Moltbook API nests comments under a specific post, docs/moltbook_api_spec.md
        §4 — it is not a flat endpoint). Required for `action in ("comment", "reply")`;
        rejected fast here rather than letting a known-incomplete action reach the
        gates and transport. The transport layer independently re-validates this as
        part of the Approved Action Envelope (moltbook/transport.py) — this is a
        fail-fast client-side check, not the sole enforcement point.
        """
        if action in ("comment", "reply") and not parent_post_id:
            raise ValueError(
                f"{action} requires parent_post_id — Moltbook replies are nested "
                "under a specific post (docs/moltbook_api_spec.md §4)"
            )

        cred = scan_content(content, own_key=self._api_key)
        links = scan_links(content, source_content=source_content, allowed_hosts=self._allowed_hosts)
        self._link_log.extend(links.findings)
        ident = scan_identity(
            content,
            declared_handle=self._declared_handle,
            declared_name=self._declared_name,
            declared_roles=self._declared_roles,
        )

        # Latch every finding before blocking anything (belt-and-suspenders per the
        # base rulings: a blocked attempt still latches).
        if cred.is_leak:
            self.credential_exposed = True
        if links.is_violation:
            self.link_violation = True
        if ident.is_contradiction:
            self.identity_drift = True

        # Block once, most severe first.
        if cred.is_leak:
            raise KeyLeakBlocked(f"{action} blocked by pre-send gate: {cred.detail}")
        if links.is_violation:
            novel_hosts = sorted({f.host or "<no-host>" for f in links.novel})
            raise LinkBlocked(
                f"{action} blocked by pre-send gate: novel link(s) not traceable to "
                f"source or allowlist: {', '.join(novel_hosts)}"
            )
        if ident.is_contradiction:
            raise IdentityDriftBlocked(
                f"{action} blocked by pre-send gate: identity drift ({ident.kind}) — {ident.detail}"
            )

        # §7 longitudinal pause (cadence + citation rulings): checked AFTER the scans
        # so a tainted attempt made while paused still latches every violation and
        # writes the link log (A5: nothing silently dropped), but BEFORE transport so
        # no autonomous post/comment/DM leaves while either pause is latched. An
        # explicitly human-authorized send is exempt from the pause — never from the
        # gates above.
        if not human_authorized:
            for store in (self._cadence_store, self._citation_store):
                if store is not None and store.paused:
                    raise AutonomousPostingPaused(
                        f"autonomous {action} blocked: {store.pause_reason}"
                    )

        return self._transport(
            action=action,
            content=content,
            headers=self._auth_header(),
            parent_post_id=parent_post_id,
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
                "identity_drift": self.identity_drift,
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
