"""
moltbook/transport.py — Moltbook execution transport.

Implements docs/m7_moltbook_transport_boundary_and_deployment_spec.md (LOCKED
2026-07-20, plus Implementation Note A, same date). This module is the **non-semantic
execution adapter** the spec's core invariant (§2) describes: it moves an
already-approved action to Moltbook and normalizes what comes back. It has no opinion
about content, timing, or governance — the resolver/Arbiter decides; this module only
executes, and only what was explicitly approved.

Section map (this file mirrors the locked spec's numbering in its comments):
  §4  ActionEnvelope + freshness validation (expiry / config drift / payload hash)
  §7  OperationalFreeze — the event class distinct from a Pi Script violation
  §8  RetryCategory — the four-way retry taxonomy
  §9  reconcile() / resolve_ambiguous_write() — reconciliation authority split
  §10 KillSwitch — fail-closed, operator-only re-enablement
  §11 DryRunTransport — full pipeline, no network call, structurally isolated
  §12 MoltbookHTTPTransport — the MVP slice (auth, health check, feed read, post, reply)
  §14 Dormant automated triggers (repeated integrity failures, authentication anomaly)
  Implementation Note A — EligibilityGate (claim-status pass-through, not governed)
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Any, Callable, Mapping, Optional

from moltbook.dryrun import DRY_RUN_ID_PREFIX, is_dry_run_id

MOLTBOOK_BASE_URL = "https://www.moltbook.com/api/v1"


# ───────────────────────── §4 Approved Action Envelope ──────────────────────────

class ActionType(str, Enum):
    POST = "post"
    REPLY = "reply"


def canonical_payload_hash(payload: dict) -> str:
    """sha256 over the canonical (sorted-key, no whitespace) JSON serialization of
    `payload` (§4). Canonical form means the hash is stable regardless of dict
    insertion order, so it only ever changes when the actual content changes."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ActionEnvelope:
    """
    The ONLY input the transport is allowed to act on (§4). Built by the approval side
    (the resolver, on SATISFIED) — never by the transport. `approve()` is a helper for
    that approval side; the transport only ever validates an envelope, never builds one.
    """
    action_id: str
    action_type: ActionType
    payload: dict
    approval_trace_id: str
    approval_timestamp: datetime
    approval_expiry: datetime
    governance_config_version: str
    payload_hash: str

    @classmethod
    def approve(
        cls,
        *,
        action_type: ActionType,
        payload: dict,
        approval_trace_id: str,
        governance_config_version: str,
        execution_window_seconds: float = 300.0,
        action_id: str | None = None,
        approved_at: datetime | None = None,
    ) -> "ActionEnvelope":
        now = approved_at or datetime.now(timezone.utc)
        return cls(
            action_id=action_id or str(uuid.uuid4()),
            action_type=action_type,
            payload=payload,
            approval_trace_id=approval_trace_id,
            approval_timestamp=now,
            approval_expiry=now + timedelta(seconds=execution_window_seconds),
            governance_config_version=governance_config_version,
            payload_hash=canonical_payload_hash(payload),
        )


class EnvelopeRejectionReason(str, Enum):
    EXPIRED = "expired"
    CONFIG_DRIFT = "config_drift"
    PAYLOAD_DRIFT = "payload_drift"


class EnvelopeRejected(Exception):
    """§4: raised before any network transmission. No outbound call may follow this."""

    def __init__(self, reason: EnvelopeRejectionReason, detail: str) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(f"envelope rejected ({reason.value}): {detail}")


def validate_envelope(
    envelope: ActionEnvelope,
    *,
    live_config_version: str,
    now: datetime | None = None,
) -> None:
    """
    §4: the three freshness checks, in the order the spec lists them. Raises
    EnvelopeRejected on the first failure found; returns None if the envelope is fresh.
    Recomputes the payload hash from the envelope's own payload — this is the
    structural proof that the payload wasn't mutated after approval (§5/§6).
    """
    now = now or datetime.now(timezone.utc)
    if now > envelope.approval_expiry:
        raise EnvelopeRejected(
            EnvelopeRejectionReason.EXPIRED,
            f"approved {envelope.approval_timestamp.isoformat()}, expired "
            f"{envelope.approval_expiry.isoformat()}, now {now.isoformat()}",
        )
    if live_config_version != envelope.governance_config_version:
        raise EnvelopeRejected(
            EnvelopeRejectionReason.CONFIG_DRIFT,
            f"envelope approved under config {envelope.governance_config_version!r}, "
            f"live config is {live_config_version!r}",
        )
    recomputed = canonical_payload_hash(envelope.payload)
    if recomputed != envelope.payload_hash:
        raise EnvelopeRejected(
            EnvelopeRejectionReason.PAYLOAD_DRIFT,
            "recomputed payload hash does not match the approved hash — payload was "
            "mutated after approval",
        )


# ───────────────────── §7 Operational freeze vs governance violation ─────────────

class OperationalFreeze(Exception):
    """
    §7: an operational freeze — ambiguous write outcome, reconciliation uncertainty,
    authentication anomaly, or another transport safety condition. A DIFFERENT event
    class from a Pi Script constraint violation. Callers must route this through a
    moltbook-local operational trace, never through pi_script/trace.py's
    violation-trace path — the two must remain permanently distinct (§7).
    """

    def __init__(self, reason: str, action_class: str) -> None:
        self.reason = reason
        self.action_class = action_class
        super().__init__(f"operational freeze ({action_class}): {reason}")


# ───────────────────────────── §8 Retry taxonomy ─────────────────────────────────

class TransportOutcome(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    OUTCOME_UNKNOWN = "outcome_unknown"


class RetryCategory(str, Enum):
    SAFE_READ = "safe_read"                # freely retryable
    IDEMPOTENT_WRITE = "idempotent_write"   # retryable only pre-response, w/ idempotency key
    AMBIGUOUS_WRITE = "ambiguous_write"     # never retried; goes to reconciliation (§9)
    GOVERNANCE_DENIAL = "governance_denial"  # never retried; terminal
    RATE_LIMITED = "rate_limited"
    """
    Added against docs/moltbook_api_spec.md §5/§6 (429, Retry-After) — a response
    classification refinement, not a change to retry AUTHORITY: the transport still
    never retries on its own (§2 invariant unaffected). Distinct from
    GOVERNANCE_DENIAL specifically because a 429 IS eventually retryable (after
    Retry-After elapses), unlike a terminal denial — lumping it into
    GOVERNANCE_DENIAL would mislead a caller into never trying again.
    """


def describe_retry_category(category: RetryCategory) -> str:
    """
    Exhaustive, human-readable description of a RetryCategory — the canonical place
    any audit/trace rendering or reconciliation branch-logic should route through,
    rather than re-deriving its own mapping (Implementation Note C's repo-wide
    consumer sweep). Deliberately exhaustive: an unrecognized value is a loud
    ValueError, never a silent default/fallthrough — a future 6th category added
    without updating this function must fail fast here, not silently render as some
    other category's description.
    """
    if category is RetryCategory.SAFE_READ:
        return "safe read — freely retryable"
    if category is RetryCategory.IDEMPOTENT_WRITE:
        return "idempotent write — retryable only pre-response, with an idempotency key"
    if category is RetryCategory.AMBIGUOUS_WRITE:
        return "ambiguous write — never retried by the transport; routes to §9 reconciliation"
    if category is RetryCategory.GOVERNANCE_DENIAL:
        return "governance denial — terminal, never retried"
    if category is RetryCategory.RATE_LIMITED:
        return (
            "rate limited — never retried by the transport itself; the underlying "
            "action may remain eligible for a later, newly authorized attempt "
            "(Implementation Note C)"
        )
    raise ValueError(
        f"unsupported RetryCategory: {category!r} — no rendering defined; add an "
        "explicit branch here, do not fall back to a default description"
    )


# ─────────────── Implementation Note D: request_fn response contract ───────────────

@dataclass(frozen=True)
class RateLimitInfo:
    """
    Implementation Note D: the four documented rate-limit headers
    (docs/moltbook_api_spec.md §5), normalized from HTTPResponse.headers — derived
    from the generic capture, never parsed out-of-band from it. Best-effort typed
    parses only: a malformed value is None, never an exception (the transport reports
    facts). §5 does not document X-RateLimit-Reset's value format (epoch vs. delta),
    so `reset` is just the integer as sent; the raw string stays in headers.
    Metadata only — nothing here schedules, sleeps, or retries (Note C condition (b)
    is still unmet).
    """
    limit: int | None = None
    remaining: int | None = None
    reset: int | None = None
    retry_after_delay_seconds: int | None = None
    retry_after_http_date: datetime | None = None

    @classmethod
    def from_headers(cls, headers: "Mapping[str, str]") -> "RateLimitInfo":
        def _int(name: str) -> int | None:
            raw = headers.get(name)
            if raw is None:
                return None
            raw = raw.strip()
            return int(raw) if re.fullmatch(r"-?\d+", raw) else None

        delay: int | None = None
        http_date: datetime | None = None
        retry_raw = headers.get("retry-after")
        if retry_raw is not None:
            retry_raw = retry_raw.strip()
            if re.fullmatch(r"\d+", retry_raw):  # RFC 9110: delay-seconds is non-negative
                delay = int(retry_raw)
            else:
                try:
                    http_date = parsedate_to_datetime(retry_raw)
                except (TypeError, ValueError):
                    http_date = None  # malformed: neither form — both fields stay None
        return cls(
            limit=_int("x-ratelimit-limit"),
            remaining=_int("x-ratelimit-remaining"),
            reset=_int("x-ratelimit-reset"),
            retry_after_delay_seconds=delay,
            retry_after_http_date=http_date,
        )


@dataclass(frozen=True)
class HTTPResponse:
    """
    Implementation Note D: the explicit return contract of the `request_fn` seam,
    replacing the old bare `(status_code, json_body)` two-tuple — deliberately a shape
    change, not an additive smuggle. Header names are normalized to lowercase at
    construction so lookup is case-insensitive by normalization. There is no
    two-tuple compatibility adapter (Note D records why).
    """
    status_code: int
    body: dict
    headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "headers", {str(k).lower(): v for k, v in dict(self.headers).items()}
        )

    @property
    def rate_limit(self) -> RateLimitInfo:
        return RateLimitInfo.from_headers(self.headers)


# Implementation Note E: a write's outcome is three independent questions, not one.
# `TransportOutcome` (above) already answers the first — did the write reach the
# platform (§8's existing concern, unchanged). These two answer the others; neither
# is derivable from transmission success, because a transmitted write lands hidden
# in `pending` until verification publishes it (or never does).

class PublicationStatus(str, Enum):
    """Is the content actually public? NOT_PUBLISHED is terminal for that content —
    the platform documents no publication path after a failed/expired verification;
    a fresh write with a fresh challenge is the only recovery (Note E)."""
    PENDING_VERIFICATION = "pending_verification"
    PUBLISHED = "published"
    NOT_PUBLISHED = "not_published"


class VerificationStatus(str, Enum):
    """NOT_REQUIRED is the first-class trusted-agent path (Note E): the write
    response carried no `verification` block and the content published immediately —
    a positive, classifiable fact, not a degenerate case of the other paths."""
    REQUIRED = "required"
    PASSED = "passed"
    FAILED = "failed"
    EXPIRED = "expired"
    NOT_REQUIRED = "not_required"


@dataclass(frozen=True)
class TransportResult:
    outcome: TransportOutcome
    retry_category: RetryCategory
    detail: str = ""
    platform_response: dict | None = None
    # Implementation Note D: populated whenever this result was built from a real
    # platform response; None where no response exists (e.g. pre-response transport
    # failure). Capture and surface only — no consumer in this module acts on them.
    platform_headers: Mapping[str, str] | None = None
    rate_limit: RateLimitInfo | None = None
    # Implementation Note E: populated only for write results whose transmission
    # succeeded (a created-content response is the only thing that HAS a publication
    # or verification status). None on reads, failed transmissions, and ambiguous
    # outcomes. Transport-visible facts only — no governance semantics attached.
    publication_status: PublicationStatus | None = None
    verification_status: VerificationStatus | None = None

    @property
    def transmission_status(self) -> TransportOutcome:
        """Note E's first status field, by its note name — an alias of `outcome`,
        which has answered 'did the write reach the platform' since the spec locked."""
        return self.outcome


# ────────────────────────── §9 Reconciliation authority ──────────────────────────

class ReconciliationOutcome(str, Enum):
    CONFIRMED_SUCCESS = "confirmed_success"
    CONFIRMED_FAILURE = "confirmed_failure"
    OUTCOME_UNKNOWN = "outcome_unknown"


@dataclass(frozen=True)
class ReconciliationResult:
    outcome: ReconciliationOutcome
    method: str | None = None  # which lookup resolved it, if any


def reconcile(
    envelope: ActionEnvelope,
    *,
    idempotency_lookup: Optional[Callable[[str], Optional[bool]]] = None,
    receipt_lookup: Optional[Callable[[str], Optional[bool]]] = None,
    id_match_lookup: Optional[Callable[[str], Optional[bool]]] = None,
) -> ReconciliationResult:
    """
    §9: attempt deterministic confirmation of an OUTCOME_UNKNOWN write, trying each
    supplied lookup in order. Each lookup returns True (confirmed success), False
    (confirmed failure), or None (inconclusive — try the next). This function only
    ever reads; it never retries the original write (§8 category 3, §2 invariant).
    """
    for method_name, lookup in (
        ("idempotency_lookup", idempotency_lookup),
        ("receipt_lookup", receipt_lookup),
        ("id_match_lookup", id_match_lookup),
    ):
        if lookup is None:
            continue
        result = lookup(envelope.action_id)
        if result is True:
            return ReconciliationResult(ReconciliationOutcome.CONFIRMED_SUCCESS, method_name)
        if result is False:
            return ReconciliationResult(ReconciliationOutcome.CONFIRMED_FAILURE, method_name)
    return ReconciliationResult(ReconciliationOutcome.OUTCOME_UNKNOWN, None)


def resolve_ambiguous_write(
    result: TransportResult,
    envelope: ActionEnvelope,
    kill_switch: "KillSwitch",
    *,
    idempotency_lookup: Optional[Callable[[str], Optional[bool]]] = None,
    receipt_lookup: Optional[Callable[[str], Optional[bool]]] = None,
    id_match_lookup: Optional[Callable[[str], Optional[bool]]] = None,
) -> ReconciliationResult:
    """
    §7/§9: the only path allowed to act on an OUTCOME_UNKNOWN result. On a confirmed
    resolution, just returns it — the caller records SUCCESS or FAILURE. On genuine
    irresolvability, engages the kill switch (the "unresolved_ambiguous_write" active
    automated trigger, §10) and raises OperationalFreeze — never a governance
    violation, never retried, never routed through the Arbiter's trace path.

    Authority split (§9): the Arbiter decided permission; this function determines
    fact, never permission; an unresolved outcome escalates to the operator, who
    alone resolves irreducible uncertainty. No layer here has authority over another.
    """
    if result.outcome is not TransportOutcome.OUTCOME_UNKNOWN:
        raise ValueError("resolve_ambiguous_write called on a non-ambiguous result")
    recon = reconcile(
        envelope,
        idempotency_lookup=idempotency_lookup,
        receipt_lookup=receipt_lookup,
        id_match_lookup=id_match_lookup,
    )
    if recon.outcome is ReconciliationOutcome.OUTCOME_UNKNOWN:
        kill_switch.activate_ambiguous_write(
            action_class=envelope.action_type.value,
            detail=f"reconciliation exhausted for action_id={envelope.action_id}",
        )
        raise OperationalFreeze(
            reason="unresolved ambiguous write after reconciliation attempts",
            action_class=envelope.action_type.value,
        )
    return recon


# ─────────────────────────────── §10 Kill switch ─────────────────────────────────

@dataclass(frozen=True)
class KillSwitchActivation:
    mode: str  # "manual" | "automated"
    trigger: str
    timestamp: datetime
    affected_action_class: str
    detail: str = ""
    # Trigger-specific structured audit fields (e.g. captcha_suspension_risk's action/
    # challenge ID, confirmed failure count, thresholds, last platform response).
    # Empty for triggers that don't need it — §10's "a boolean flag is insufficient"
    # requirement is satisfied per-trigger here, not by inventing new dataclasses per
    # trigger type.
    extra: dict = field(default_factory=dict)


class KillSwitchEngaged(Exception):
    """Raised by check_write() while the kill switch is engaged."""


class KillSwitch:
    """
    §10. Fail-closed: engaged blocks ALL outbound writes; reads are unaffected.
    `check_write()` must be called immediately before the actual network write, not
    just once somewhere upstream — this IS the "final outbound boundary" enforcement
    the spec requires, not a convenience check callers may relocate.

    Manual activation and THREE automated triggers are active at lock time plus
    Implementation Note B: `activate_ambiguous_write`, `activate_reconciliation_contradiction`
    (locked spec §10), and `activate_captcha_suspension_risk` (Implementation Note B,
    2026-07-20 — NOT the §14.1 dormant "repeated integrity failures" trigger; a
    separate, deliberately conservative, immediately-active trigger of its own). The
    two §14 dormant triggers are unaffected — their `activate_*` methods exist and are
    callable, but remain permanent no-ops until their own formal amendment.
    Only `clear()`, called by an operator, may re-enable outbound writes; nothing
    else in this class (or anywhere else) restores execution automatically.
    """

    def __init__(self) -> None:
        self._engaged = False
        self._log: list[KillSwitchActivation] = []

    @property
    def engaged(self) -> bool:
        return self._engaged

    @property
    def activation_log(self) -> tuple[KillSwitchActivation, ...]:
        return tuple(self._log)

    def check_write(self) -> None:
        if self._engaged:
            raise KillSwitchEngaged("kill switch engaged — all outbound writes blocked")

    # ── Manual + the two active automated triggers ──────────────────────────────
    def activate_manual(self, *, operator: str, detail: str = "", affected_action_class: str = "*") -> None:
        self._engage("manual", trigger="operator_command",
                     detail=f"operator={operator} {detail}".strip(),
                     affected_action_class=affected_action_class)

    def activate_ambiguous_write(self, *, action_class: str, detail: str = "") -> None:
        """§9/§10 active automated trigger: reconciliation could not resolve OUTCOME_UNKNOWN."""
        self._engage("automated", trigger="unresolved_ambiguous_write",
                     detail=detail, affected_action_class=action_class)

    def activate_reconciliation_contradiction(self, *, action_class: str, detail: str = "") -> None:
        """§10 active automated trigger: reconciliation lookups returned contradictory facts."""
        self._engage("automated", trigger="reconciliation_contradiction",
                     detail=detail, affected_action_class=action_class)

    def activate_captcha_suspension_risk(
        self,
        *,
        action_class: str,
        action_id: str,
        verification_code: str,
        confirmed_failure_count: int,
        platform_response: dict | None,
        detail: str = "",
    ) -> None:
        """
        Implementation Note B (2026-07-20, non-binding on the locked spec): active
        automated trigger, engaged by CaptchaVerifier on the 3rd CONSECUTIVE
        PLATFORM-CONFIRMED captcha failure. This is Continuum's own conservative
        safety margin (CAPTCHA_LOCAL_FAILURE_THRESHOLD = 3). Moltbook's documented
        suspension rule (PLATFORM_CAPTCHA_SUSPENSION_LIMIT) is a DIFFERENT rule over
        a DIFFERENT window — last 10 attempts all failures, expiry counted — per
        Note E these are deliberately NOT equivalent and ours must never be described
        as mapping onto theirs; ours is simply the stricter margin. Deliberately NOT
        routed through §14.1's dormant "repeated integrity failures" trigger — that
        one stays undefined pending its own amendment; this one is scoped,
        conservative, and active now on its own terms.

        This is an operational condition, not a governance violation (§7) — it must
        never be recorded through the Arbiter's violation-trace path.
        """
        self._engage(
            "automated", trigger="captcha_suspension_risk",
            detail=detail or (
                f"{confirmed_failure_count} consecutive confirmed captcha failures "
                f"(Continuum local threshold {CAPTCHA_LOCAL_FAILURE_THRESHOLD}, "
                f"Moltbook-documented platform suspension limit "
                f"{PLATFORM_CAPTCHA_SUSPENSION_LIMIT})"
            ),
            affected_action_class=action_class,
            extra={
                "action_id": action_id,
                "verification_code": verification_code,
                "confirmed_failure_count": confirmed_failure_count,
                "local_threshold": CAPTCHA_LOCAL_FAILURE_THRESHOLD,
                "platform_suspension_limit": PLATFORM_CAPTCHA_SUSPENSION_LIMIT,
                "last_platform_response": platform_response,
            },
        )

    # ── §14 dormant triggers — permanent no-ops until their own amendment ───────
    def activate_repeated_integrity_failures(self, *args: Any, **kwargs: Any) -> None:
        """
        §14.1: DORMANT. Defined but never activates the kill switch until a formal
        amendment sets a concrete threshold (event type, count, window, scope,
        duplicate-handling, reset semantics, required audit evidence). This method
        exists so callers have a stable name to call — its no-op body IS the
        dormancy guarantee, not just a docstring claim. Do not implement engagement
        logic here without the amendment landing first.
        """
        return None

    def activate_authentication_anomaly(self, *args: Any, **kwargs: Any) -> None:
        """§14.2: DORMANT, mirrors §14.1 exactly. Permanently inert until amendment."""
        return None

    # ── Re-enablement (§10: operator-only, no auto-recovery anywhere) ───────────
    def clear(self, *, operator: str, detail: str = "") -> None:
        self._engaged = False
        self._log.append(KillSwitchActivation(
            mode="manual", trigger="operator_clear",
            timestamp=datetime.now(timezone.utc),
            affected_action_class="*",
            detail=f"operator={operator} {detail}".strip(),
        ))

    def _engage(
        self, mode: str, *, trigger: str, detail: str, affected_action_class: str,
        extra: dict | None = None,
    ) -> None:
        self._engaged = True
        self._log.append(KillSwitchActivation(
            mode=mode, trigger=trigger,
            timestamp=datetime.now(timezone.utc),
            affected_action_class=affected_action_class,
            detail=detail,
            extra=extra or {},
        ))


# ──── Implementation Notes B + E: captcha verification (2026-07-20 / 2026-07-21) ────
#
# Non-binding on the locked spec, same status as Implementation Note A. Moltbook
# requires solving an obfuscated math-word-problem challenge before any post/comment
# PUBLISHES; if the account's last 10 challenge attempts are all failures (expired or
# incorrect) the account is suspended. Note E (2026-07-21, signed off) amended Note B's
# mechanics after the live protocol was discovered: the WRITE issues the challenge
# inside its own response (no standalone issuance endpoint — fetch_captcha_challenge
# is retired), verification gates PUBLICATION not transmission, and verification_code
# replaced challenge_id contract-wide. Note B's core treatment stands unchanged
# (operator decision, 2026-07-20):
#   - This is a TRANSPORT-MECHANICAL publishing precondition, NOT a new governed
#     action type and NOT its own Approved Action Envelope. It may run only against
#     a write that already has a valid envelope (§4) — see MoltbookHTTPTransport.send.
#   - The solver is deterministic and narrowly scoped to the platform's documented
#     challenge shape. It never uses unrestricted model generation and never touches
#     the approved post/reply payload — solving the challenge is orthogonal to what
#     gets posted.
#   - Every attempt is bound to the originating action_id, approval_trace_id, and
#     verification_code (see CaptchaAttemptRecord). Ambiguous outcomes (timeout, unclear
#     response) are never counted as confirmed failures and never blindly retried;
#     the same answer is never resubmitted across challenges.
#   - A NEW active kill-switch trigger, `captcha_suspension_risk` (KillSwitch, above),
#     engages on the 3rd CONSECUTIVE PLATFORM-CONFIRMED failure. This is deliberately
#     NOT the §14.1 dormant "repeated integrity failures" trigger — that one stays
#     undefined pending its own amendment. This trigger is scoped, active now, and
#     uses a number Continuum chose as a safety margin, not one Moltbook supplied.

CAPTCHA_LOCAL_FAILURE_THRESHOLD = 3
"""Continuum's own conservative safety margin. NOT platform-supplied — see
PLATFORM_CAPTCHA_SUSPENSION_LIMIT below for the actual Moltbook-documented number
this margin is deliberately set well under."""

PLATFORM_CAPTCHA_SUSPENSION_LIMIT = 10
"""Moltbook-documented (live skill.md capture 2026-07-21): if the account's LAST 10
challenge attempts are ALL failures (expired or incorrect), the account is
automatically suspended. A trailing-10 window, NOT a consecutive count — and therefore
NOT the same rule as Continuum's consecutive-confirmed threshold above (Note E:
different rules over different windows; ours is the deliberately stricter margin,
never to be described as equivalent). Recorded here only so activation audit events
can show both numbers together."""


class CaptchaOutcome(str, Enum):
    CONFIRMED_SUCCESS = "confirmed_success"
    CONFIRMED_FAILURE = "confirmed_failure"
    AMBIGUOUS = "ambiguous"  # timeout / unclear platform response — never counted


@dataclass(frozen=True)
class CaptchaChallenge:
    """Implementation Note E: parsed from the `verification` block the platform
    embeds in a write response — there is no standalone issuance endpoint.
    `verification_code` is the platform's lookup key (it replaced `challenge_id`
    contract-wide per Note E); `expires_at` is the platform's value, never a
    caller-invented one."""
    verification_code: str
    prompt: str
    expires_at: datetime


def parse_verification_block(body: dict) -> CaptchaChallenge | None:
    """
    Implementation Note E: extract the embedded challenge from a successful write
    response. The documented shape (live skill.md capture, 2026-07-21) nests it under
    the created content — `post.verification` / `comment.verification` /
    `submolt.verification` — carrying `verification_code`, `challenge_text`, and
    `expires_at` (ISO-8601).

    Returns None when NO verification block exists — the documented trusted-agent
    immediate-publish signal, a positive fact, not an error. A verification block
    that IS present but missing its documented fields contradicts the captured
    protocol shape and raises loudly (Note E stop condition: re-fixture, don't
    bridge the gap with guesses).
    """
    candidates = [body.get(k) for k in ("post", "comment", "submolt")]
    candidates.append(body)  # tolerate a top-level block, same fields
    for content in candidates:
        if not isinstance(content, dict):
            continue
        block = content.get("verification")
        if not isinstance(block, dict):
            continue
        code = block.get("verification_code")
        prompt = block.get("challenge_text")
        expires_raw = block.get("expires_at")
        if not (isinstance(code, str) and code and isinstance(prompt, str) and prompt
                and isinstance(expires_raw, str) and expires_raw):
            raise ValueError(
                "write response contains a 'verification' block that does not match "
                "the captured protocol shape (verification_code / challenge_text / "
                "expires_at all required) — re-fixture against the live response, "
                f"do not guess (Note E). Got keys: {sorted(block.keys())!r}"
            )
        try:
            expires_at = datetime.fromisoformat(expires_raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                f"verification.expires_at is not ISO-8601: {expires_raw!r} — "
                "contradicts the captured protocol shape (Note E)"
            ) from exc
        return CaptchaChallenge(verification_code=code, prompt=prompt, expires_at=expires_at)
    return None


@dataclass(frozen=True)
class CaptchaAttemptRecord:
    """Binds one verification attempt to its originating action and challenge, per
    Implementation Note B's binding requirement (key renamed to the platform's
    `verification_code` by Note E)."""
    action_id: str
    approval_trace_id: str
    verification_code: str
    outcome: CaptchaOutcome
    platform_response: dict | None
    timestamp: datetime


def solve_captcha_deterministic(prompt: str) -> str:
    """
    Deterministic, narrowly-scoped solver for Moltbook's documented math-word-problem
    challenge (docs/moltbook_api_spec.md §6: numeric string, 2 decimals, e.g. "15.00").
    Extracts two numbers and one arithmetic operator from the prompt text and computes
    the answer mechanically — no model generation, no interpretation beyond arithmetic.

    Best-effort against the documented shape: the exact challenge wording has not been
    observed live, so the operator-word list below may need extending once real
    challenge text is seen. This is flagged here deliberately rather than papered
    over — a solver that silently guesses on unrecognized wording would defeat the
    "deterministic and narrowly scoped" requirement.
    """
    numbers = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", prompt)]
    if len(numbers) < 2:
        raise ValueError(f"captcha prompt does not contain two numbers: {prompt!r}")
    a, b = numbers[0], numbers[1]
    lowered = prompt.lower()

    word_to_op = (
        ("added to", "+"), ("plus", "+"), ("add", "+"),
        ("subtracted from", "-"), ("minus", "-"), ("subtract", "-"),
        ("multiplied by", "*"), ("times", "*"),
        ("divided by", "/"), ("divide", "/"),
    )
    op = next((sym for word, sym in word_to_op if word in lowered), None)
    if op is None:
        op = next((sym for sym in ("+", "-", "*", "/") if sym in prompt), None)
    if op is None:
        raise ValueError(f"captcha prompt has no recognizable operator: {prompt!r}")

    result = {"+": a + b, "-": a - b, "*": a * b, "/": (a / b if b else float("nan"))}[op]
    return f"{result:.2f}"


# Note E retired CaptchaVerificationFailed / CaptchaVerificationAmbiguous: those
# exceptions blocked a write BEFORE transmission, which the real protocol makes
# impossible — the write has already happened by the time verification runs, so a
# verification outcome is a classified fact on the TransportResult
# (publication_status / verification_status), never an exception that discards the
# transmission facts.


class CaptchaVerifier:
    """
    Implementation Note B. Tracks CONSECUTIVE PLATFORM-CONFIRMED captcha failures for
    the deployed agent/account and engages the `captcha_suspension_risk` kill-switch
    trigger on the 3rd. Only a CONFIRMED_FAILURE increments the counter; AMBIGUOUS
    outcomes (timeout, unclear response) never count and never reset the counter
    either — an ambiguous result is simply not evidence either way. Only a
    CONFIRMED_SUCCESS resets the counter to zero.
    """

    def __init__(self, kill_switch: "KillSwitch", *, solver: Callable[[str], str] | None = None) -> None:
        self._kill_switch = kill_switch
        self._solver = solver or solve_captcha_deterministic
        self._consecutive_confirmed_failures = 0
        self._log: list[CaptchaAttemptRecord] = []

    @property
    def consecutive_confirmed_failures(self) -> int:
        return self._consecutive_confirmed_failures

    @property
    def log(self) -> tuple[CaptchaAttemptRecord, ...]:
        return tuple(self._log)

    def verify(
        self,
        envelope: ActionEnvelope,
        challenge: CaptchaChallenge,
        *,
        submit_fn: Callable[[str, str], tuple[CaptchaOutcome, Optional[dict]]],
    ) -> CaptchaOutcome:
        """
        `submit_fn(verification_code, answer) -> (CaptchaOutcome, platform_response)`
        is the injectable network seam (mirrors MoltbookHTTPTransport's request_fn
        pattern) — the real network call happens only there; every test supplies a
        fake. Solves exactly once per call — this method never resubmits the same
        answer, and never retries an ambiguous outcome on its own.
        """
        answer = self._solver(challenge.prompt)
        outcome, platform_response = submit_fn(challenge.verification_code, answer)

        self._log.append(CaptchaAttemptRecord(
            action_id=envelope.action_id,
            approval_trace_id=envelope.approval_trace_id,
            verification_code=challenge.verification_code,
            outcome=outcome,
            platform_response=platform_response,
            timestamp=datetime.now(timezone.utc),
        ))

        if outcome is CaptchaOutcome.CONFIRMED_SUCCESS:
            self._consecutive_confirmed_failures = 0
        elif outcome is CaptchaOutcome.CONFIRMED_FAILURE:
            self._consecutive_confirmed_failures += 1
            if self._consecutive_confirmed_failures >= CAPTCHA_LOCAL_FAILURE_THRESHOLD:
                self._kill_switch.activate_captcha_suspension_risk(
                    action_class=envelope.action_type.value,
                    action_id=envelope.action_id,
                    verification_code=challenge.verification_code,
                    confirmed_failure_count=self._consecutive_confirmed_failures,
                    platform_response=platform_response,
                )
        # AMBIGUOUS falls through untouched: not counted, not reset, not retried here.
        return outcome


# ───────────────────── Implementation Note A: eligibility gate ──────────────────

class EligibilityState(str, Enum):
    CLAIMED = "claimed"
    PENDING_CLAIM = "pending_claim"


class EligibilityBlocked(Exception):
    """
    Implementation Note A (2026-07-20, non-binding on the locked spec): platform
    eligibility is not 'claimed'. NOT a kill-switch activation, NOT an Arbiter event,
    NOT a reconciliation freeze — a third category, a direct pass-through of a
    platform-declared fact. Reads are unaffected; only writes are blocked.
    """


@dataclass
class EligibilityGate:
    """
    Implementation Note A: `GET /agents/status` (§5/§12 health check, §8 safe read).
    `claimed` -> writes proceed normally. `pending_claim` -> writes rejected, state
    logged, operator notified; reads continue. No kill-switch trigger, no threshold,
    no amendment path — this is a permanent direct pass-through of platform fact,
    unlike the §14 dormant triggers, which is exactly why it needs neither.
    """

    state: EligibilityState = EligibilityState.CLAIMED
    _log: list[dict] = field(default_factory=list)

    def update(self, state: EligibilityState) -> None:
        self.state = state
        self._log.append({"state": state.value, "timestamp": datetime.now(timezone.utc).isoformat()})

    @property
    def log(self) -> tuple[dict, ...]:
        return tuple(self._log)

    def check_write(self) -> None:
        if self.state is not EligibilityState.CLAIMED:
            raise EligibilityBlocked(
                f"outbound write blocked: platform eligibility is {self.state.value!r}, "
                "not 'claimed' — operator notified, read access unaffected"
            )


# ───────────────────────────── §11 Dry run mode ──────────────────────────────────

def make_dry_run_action_id() -> str:
    """A fresh action_id in the reserved dry-run namespace (§11)."""
    return f"{DRY_RUN_ID_PREFIX}{uuid.uuid4()}"


@dataclass(frozen=True)
class DryRunOutcome:
    """
    §11: a simulated transport outcome. Deliberately a DIFFERENT type from
    TransportResult so a caller cannot accidentally treat a simulation as confirmed —
    there is no shared base class and no implicit conversion between the two.
    """
    envelope: ActionEnvelope
    simulated_outcome: TransportOutcome
    detail: str = "dry-run: no network call made"
    # Note E mechanical decision: with no network call there is no platform to issue
    # a challenge, so the simulation mirrors the documented no-verification-block
    # path (NOT_REQUIRED + PUBLISHED). The `simulated_` prefix and this type's
    # deliberate separation from TransportResult keep it impossible to read as a
    # real publication fact.
    simulated_publication_status: PublicationStatus = PublicationStatus.PUBLISHED
    simulated_verification_status: VerificationStatus = VerificationStatus.NOT_REQUIRED


class DryRunTransport:
    """
    §11. Runs real envelope validation (§4) so a dry run genuinely exercises the same
    freshness checks a live send would — but performs NO network call and returns a
    DryRunOutcome, recorded only to this instance's own `trace`, never to the
    cadence/citation stores. Even if a caller mistakenly fed a dry-run outcome into a
    store's `ingest()`, the store's own `is_dry_run_id()` guard (moltbook/cadence.py,
    moltbook/citation.py) rejects it structurally — this class does not rely on that
    guard, it simply never calls those stores at all.
    """

    def __init__(self, *, live_config_version: str) -> None:
        self._live_config_version = live_config_version
        self._trace: list[DryRunOutcome] = []

    def send(self, envelope: ActionEnvelope) -> DryRunOutcome:
        if not is_dry_run_id(envelope.action_id):
            raise ValueError(
                f"DryRunTransport requires an action_id in the reserved dry-run "
                f"namespace (prefix {DRY_RUN_ID_PREFIX!r}); got {envelope.action_id!r}"
            )
        validate_envelope(envelope, live_config_version=self._live_config_version)
        outcome = DryRunOutcome(envelope=envelope, simulated_outcome=TransportOutcome.SUCCESS)
        self._trace.append(outcome)
        return outcome

    @property
    def trace(self) -> tuple[DryRunOutcome, ...]:
        return tuple(self._trace)


# ───────────────── §12 MVP slice: the real Moltbook HTTP transport ──────────────

class MoltbookHTTPTransport:
    """
    §5/§12: the MVP slice only — auth, health check, claim-status read (Note A), feed
    read, governed post, governed reply. DMs, mentions, notifications, deletions,
    edits, account mutation, and registration automation are explicitly deferred
    (§12) and have NO methods here at all, not even unused stubs — there is no
    "escape hatch" endpoint surface (§6).

    All actual network I/O goes through the single injectable `request_fn` seam
    (method, path, json_body, headers) -> HTTPResponse (Implementation Note D — the
    old bare (status, body) two-tuple shape is gone, no adapter). Production wiring
    leaves it as the real `urllib`-based default; every test supplies a fake, so no
    test in this suite ever makes a real network call.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = MOLTBOOK_BASE_URL,
        kill_switch: KillSwitch | None = None,
        eligibility_gate: EligibilityGate | None = None,
        live_config_version: str = "",
        request_fn: Optional[Callable[[str, str, dict | None, dict], HTTPResponse]] = None,
        captcha_verifier: Optional[CaptchaVerifier] = None,
        submit_captcha_fn: Optional[Callable[[str, str], tuple[CaptchaOutcome, Optional[dict]]]] = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self.kill_switch = kill_switch or KillSwitch()
        self.eligibility = eligibility_gate or EligibilityGate()
        self._live_config_version = live_config_version
        self._request_fn = request_fn or self._real_request
        # Implementation Note E fail-closed invariant: the captcha surface is exactly
        # two pieces (issuance is embedded in the write response — there is nothing
        # to fetch, so Note B's fetch_captcha_challenge is retired). Both configured,
        # or neither — a partial configuration is the latent-crash-after-live-issuance
        # failure mode Note B's three-optional constructor permitted, and it fails
        # HERE, at construction, never later.
        if (captcha_verifier is None) != (submit_captcha_fn is None):
            raise ValueError(
                "partial captcha configuration (Note E fail-closed invariant): "
                "captcha_verifier and submit_captcha_fn must be BOTH configured or "
                "BOTH absent — got "
                f"captcha_verifier={'set' if captcha_verifier is not None else 'None'}, "
                f"submit_captcha_fn={'set' if submit_captcha_fn is not None else 'None'}"
            )
        # Unconfigured remains legal: a write that comes back pending-verification is
        # reported outward as exactly that (PENDING_VERIFICATION), never guessed at.
        self.captcha_verifier = captcha_verifier
        self._submit_captcha_fn = submit_captcha_fn

    @property
    def live_config_version(self) -> str:
        return self._live_config_version

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._api_key}"}

    def _real_request(self, method: str, path: str, body: dict | None, headers: dict) -> HTTPResponse:
        url = f"{self._base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            url, data=data, headers={**headers, "Content-Type": "application/json"}, method=method,
        )
        # Implementation Note D: headers are captured identically on BOTH paths —
        # a 429 arrives via HTTPError, so capturing only on the success path would
        # silently fail on the exact case header capture exists for.
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
                return HTTPResponse(
                    resp.status, (json.loads(raw) if raw else {}), dict(resp.headers),
                )
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8")
            return HTTPResponse(
                exc.code, (json.loads(raw) if raw else {}), dict(exc.headers),
            )

    # ── Safe reads (§8) ──────────────────────────────────────────────────────────
    def health_check(self) -> TransportResult:
        """
        Moltbook's documented surface (docs/moltbook_api_spec.md, from skill.md) has no
        dedicated `/health` endpoint — realized here as `GET /agents/status`, the only
        confirmed cheap authenticated read, which also happens to be the eligibility
        check (Implementation Note A). One real network call serves both purposes.
        """
        return self._status_result(self.check_eligibility())

    def _status_result(self, state: "EligibilityState") -> TransportResult:
        outcome = TransportOutcome.SUCCESS
        return TransportResult(outcome, RetryCategory.SAFE_READ, platform_response={"status": state.value})

    def check_eligibility(self) -> EligibilityState:
        """Implementation Note A: GET /api/v1/agents/status, a safe read."""
        response = self._request_fn("GET", "/agents/status", None, self._auth_headers())
        state = (
            EligibilityState.CLAIMED
            if response.body.get("status") == "claimed"
            else EligibilityState.PENDING_CLAIM
        )
        self.eligibility.update(state)
        return state

    def read_feed(self) -> TransportResult:
        """GET /api/v1/posts (docs/moltbook_api_spec.md §4) — NOT `/feed`, which does
        not exist on the real API. Corrected against that reference before first use."""
        response = self._request_fn("GET", "/posts", None, self._auth_headers())
        outcome = TransportOutcome.SUCCESS if response.status_code == 200 else TransportOutcome.FAILURE
        return TransportResult(
            outcome, RetryCategory.SAFE_READ, platform_response=response.body,
            platform_headers=response.headers, rate_limit=response.rate_limit,
        )

    # ── Governed writes (§4, §10, Note A, §12) ──────────────────────────────────
    def send(self, envelope: ActionEnvelope) -> TransportResult:
        """
        The single write entry point for post/reply. Order matches the spec plus
        Note E exactly: envelope freshness (§4) -> kill switch (§10) -> eligibility
        gate (Note A) -> network call -> transmission classification (§8) -> on a
        created-content response, verification classification (Note E: parse the
        embedded `verification` block -> solve -> submit -> classify publication).
        Verification gates PUBLICATION, not transmission — the write has already
        happened by the time it runs. Nothing here inspects or alters
        `envelope.payload` — it is transmitted exactly as approved (§2/§5/§6).

        Real endpoint shapes (docs/moltbook_api_spec.md §4): posts go to
        `POST /api/v1/posts`; a reply is `POST /api/v1/posts/{POST_ID}/comments` — it
        is NOT a flat `/replies` endpoint, so a REPLY envelope's payload must carry
        `parent_post_id`. Reading that one routing field is still non-semantic (§2) —
        the transport doesn't interpret content, it just needs to know which URL to
        hit, the same way it already needs `action_type` to pick /posts vs. this path.

        `parent_post_id` stays part of `envelope.payload` (so it's still covered by
        the §4 payload-hash tamper check) but is NOT itself a documented request-body
        field — docs/moltbook_api_spec.md §4 puts the post ID only in the URL path.
        It is stripped from the body actually transmitted; only documented fields
        (`content`, and the optional documented `parent_id` for nested comment
        threading, if present) are sent. Nested threading itself is NOT wired at the
        MoltbookClient level yet — Phase One supports flat, top-level comments only;
        `parent_id` passthrough exists here so a caller that already has a comment ID
        to thread under can use it, without requiring a client.send() signature change
        to unlock that passthrough.
        """
        if envelope.action_type not in (ActionType.POST, ActionType.REPLY):
            raise ValueError(f"MVP slice supports post/reply only, got {envelope.action_type!r}")

        validate_envelope(envelope, live_config_version=self._live_config_version)
        self.kill_switch.check_write()
        self.eligibility.check_write()

        if envelope.action_type is ActionType.POST:
            path = "/posts"
            body_to_send = envelope.payload
        else:
            parent_post_id = envelope.payload.get("parent_post_id")
            if not parent_post_id:
                raise ValueError(
                    "REPLY envelope payload must include 'parent_post_id' "
                    "(docs/moltbook_api_spec.md §4: comments are POSTed under a "
                    "specific post, not a flat endpoint)"
                )
            path = f"/posts/{parent_post_id}/comments"
            # parent_post_id routes the URL only — it is not a documented body field
            # (docs/moltbook_api_spec.md §4) and must not be sent on the wire.
            body_to_send = {k: v for k, v in envelope.payload.items() if k != "parent_post_id"}
        try:
            response = self._request_fn("POST", path, body_to_send, self._auth_headers())
        except (TimeoutError, ConnectionError, OSError) as exc:
            # §8 category 2 (idempotent write retry candidate): transport-level
            # failure BEFORE any response was received. This call does not retry —
            # the transport never decides to retry on its own (§2) — it reports the
            # fact and leaves any retry decision to the caller. No response exists,
            # so platform_headers/rate_limit stay None (Note D).
            return TransportResult(
                TransportOutcome.OUTCOME_UNKNOWN, RetryCategory.IDEMPOTENT_WRITE,
                detail=f"no response received: {exc}",
            )

        status, body = response.status_code, response.body
        # Implementation Note D: every result below was built from a real platform
        # response, so all of them surface the captured headers + normalized
        # rate-limit fields — capture and surface only, nothing acts on them here.
        resp_meta: dict = {
            "platform_headers": response.headers, "rate_limit": response.rate_limit,
        }
        if status in (401, 403):
            return TransportResult(
                TransportOutcome.FAILURE, RetryCategory.GOVERNANCE_DENIAL,
                detail="platform denial", platform_response=body, **resp_meta,
            )
        if status == 409:
            # docs/moltbook_api_spec.md §6: platform-documented conflict — the
            # write may already have happened (duplicate submission). Never assume
            # success or failure here; this is exactly what §9's reconciliation
            # (idempotency/receipt/ID-match lookups) exists to resolve. Never retried.
            return TransportResult(
                TransportOutcome.OUTCOME_UNKNOWN, RetryCategory.AMBIGUOUS_WRITE,
                detail="409 conflict — candidate for reconciliation's deterministic "
                       "duplicate-detection path (§9), not assumed success or failure",
                platform_response=body, **resp_meta,
            )
        if status == 410:
            # docs/moltbook_api_spec.md §6: platform-documented "gone/expired" —
            # unlike 409, this is unambiguous: the target resource no longer exists
            # for this action to complete against. Terminal, never retried.
            return TransportResult(
                TransportOutcome.FAILURE, RetryCategory.GOVERNANCE_DENIAL,
                detail="410 gone/expired — terminal, never retried", platform_response=body,
                **resp_meta,
            )
        if status == 429:
            # docs/moltbook_api_spec.md §5: rate limited. Deliberately NOT
            # GOVERNANCE_DENIAL — a 429 is eventually retryable (after Retry-After
            # elapses), unlike a terminal denial. The transport itself still never
            # retries on its own (§2). Retry-After/X-RateLimit-* values now ride
            # along in rate_limit/platform_headers (Implementation Note D) — facts
            # surfaced outward; scheduling on them stays unspecified (Note C (b)).
            return TransportResult(
                TransportOutcome.FAILURE, RetryCategory.RATE_LIMITED,
                detail="429 rate limited — retry only after Retry-After elapses; "
                       "header values surfaced in rate_limit (Note D), never acted "
                       "on by this transport",
                platform_response=body, **resp_meta,
            )
        if 200 <= status < 300:
            # Note E: transmission succeeded and content was created — now classify
            # publication, which is a separate question the verification flow answers.
            return self._classify_created_content(envelope, body, resp_meta)
        if 500 <= status < 600:
            # §8 category 3: a response WAS received but its meaning is uncertain —
            # ambiguous, never retried automatically here, goes to reconciliation (§9).
            return TransportResult(
                TransportOutcome.OUTCOME_UNKNOWN, RetryCategory.AMBIGUOUS_WRITE,
                detail=f"5xx response: {status}", platform_response=body, **resp_meta,
            )
        return TransportResult(
            TransportOutcome.FAILURE, RetryCategory.GOVERNANCE_DENIAL,
            detail=f"unexpected status {status}", platform_response=body, **resp_meta,
        )

    def _classify_created_content(
        self, envelope: ActionEnvelope, body: dict, resp_meta: dict,
    ) -> TransportResult:
        """
        Implementation Note E: a created-content (2xx) write response carries the
        publication question. Four outcomes, all classified facts on the result —
        never exceptions, never retries, never guessed timing:

          no verification block  -> NOT_REQUIRED + PUBLISHED (trusted-agent path,
                                    first-class — zero verify calls)
          captcha unconfigured   -> REQUIRED + PENDING_VERIFICATION (left pending,
                                    reported exactly as that, never guessed at)
          challenge expired      -> EXPIRED + NOT_PUBLISHED (expiry read from the
                                    platform's expires_at only — no constant)
          verify runs            -> PASSED/FAILED/REQUIRED per the platform's answer
        """
        challenge = parse_verification_block(body)
        if challenge is None:
            return TransportResult(
                TransportOutcome.SUCCESS, RetryCategory.IDEMPOTENT_WRITE,
                detail="no verification block — published immediately (trusted-agent "
                       "path, Note E)",
                platform_response=body,
                publication_status=PublicationStatus.PUBLISHED,
                verification_status=VerificationStatus.NOT_REQUIRED,
                **resp_meta,
            )
        if self.captcha_verifier is None:
            return TransportResult(
                TransportOutcome.SUCCESS, RetryCategory.IDEMPOTENT_WRITE,
                detail="verification required but captcha is not configured — content "
                       "left pending on the platform, reported as exactly that (Note E)",
                platform_response=body,
                publication_status=PublicationStatus.PENDING_VERIFICATION,
                verification_status=VerificationStatus.REQUIRED,
                **resp_meta,
            )
        if datetime.now(timezone.utc) >= challenge.expires_at:
            # Platform-supplied expiry has already passed — submitting would be a
            # documented-to-fail call (410). No attempt is made, no attempt record
            # exists (nothing was submitted, so nothing is platform-confirmed), and
            # the failure counter does not move. The platform may count the expiry
            # against its own trailing-10 rule regardless — out of our control,
            # and per Note E the two rules are not equivalent anyway.
            return TransportResult(
                TransportOutcome.SUCCESS, RetryCategory.IDEMPOTENT_WRITE,
                detail=f"verification challenge {challenge.verification_code!r} "
                       "already expired at receipt (platform expires_at) — content "
                       "not published; a fresh write is the only recovery (Note E)",
                platform_response=body,
                publication_status=PublicationStatus.NOT_PUBLISHED,
                verification_status=VerificationStatus.EXPIRED,
                **resp_meta,
            )
        outcome = self.captcha_verifier.verify(
            envelope, challenge, submit_fn=self._submit_captcha_fn,
        )
        if outcome is CaptchaOutcome.CONFIRMED_SUCCESS:
            publication = PublicationStatus.PUBLISHED
            verification = VerificationStatus.PASSED
            detail = "verification passed — content published"
        elif outcome is CaptchaOutcome.CONFIRMED_FAILURE:
            publication = PublicationStatus.NOT_PUBLISHED
            verification = VerificationStatus.FAILED
            detail = (
                f"verification confirmed failed for {challenge.verification_code!r} — "
                "content not published; a fresh write with a fresh challenge is the "
                "only recovery (Note E), never an automatic resubmit"
            )
        else:  # AMBIGUOUS
            publication = PublicationStatus.PENDING_VERIFICATION
            verification = VerificationStatus.REQUIRED
            detail = (
                f"verification response ambiguous for {challenge.verification_code!r} — "
                "content remains pending; not counted as a failure, not retried (Note B)"
            )
        return TransportResult(
            TransportOutcome.SUCCESS, RetryCategory.IDEMPOTENT_WRITE,
            detail=detail, platform_response=body,
            publication_status=publication, verification_status=verification,
            **resp_meta,
        )


# ───────────────── MoltbookClient integration adapter ──────────────────────────

def as_client_transport(
    http_transport: MoltbookHTTPTransport,
    *,
    governance_config_version: str,
    approval_trace_id_fn: Optional[Callable[[], str]] = None,
) -> Callable[..., dict[str, Any]]:
    """
    Adapts MoltbookHTTPTransport to the `Callable[..., dict]` signature
    `MoltbookClient.__init__`'s `transport` param expects (moltbook/client.py). By the
    time MoltbookClient.send() reaches the transport, its own pre-send gates
    (credential/link/identity scans, §7 pause check) have already run and passed —
    this adapter wraps that already-approved action in an envelope; it is not a
    second governance decision (§2: Continuum decides, transport executes).

    `action="dm"` is refused here: DMs are explicitly deferred past Phase One (§12).

    RESOLVED (was a known gap; fixed 2026-07-20): `MoltbookClient.send()` now accepts
    `parent_post_id`, required for `action in ("comment", "reply")`, and passes it
    through as a `_transport(..., parent_post_id=...)` kwarg (moltbook/client.py). This
    adapter carries it into the envelope payload, so it becomes part of the payload
    hash (§4) — a real reply is `POST /api/v1/posts/{POST_ID}/comments`
    (docs/moltbook_api_spec.md §4), and the transport (MoltbookHTTPTransport.send)
    independently re-validates `parent_post_id` is present before ever building that
    URL, so this adapter is not the only enforcement point.
    """
    trace_id_fn = approval_trace_id_fn or (lambda: str(uuid.uuid4()))

    def _transport(
        *, action: str, content: str, headers: dict, parent_post_id: str | None = None,
    ) -> dict[str, Any]:
        if action == "post":
            action_type = ActionType.POST
            payload: dict[str, Any] = {"content": content}
        elif action in ("comment", "reply"):
            action_type = ActionType.REPLY
            if not parent_post_id:
                raise ValueError(
                    "reply/comment requires parent_post_id (docs/moltbook_api_spec.md "
                    "§4) — MoltbookClient.send() should have rejected this already"
                )
            payload = {"content": content, "parent_post_id": parent_post_id}
        else:
            raise ValueError(
                f"Phase One transport supports post/reply only — {action!r} "
                "(e.g. 'dm') is explicitly deferred (spec §12)"
            )
        envelope = ActionEnvelope.approve(
            action_type=action_type,
            payload=payload,
            approval_trace_id=trace_id_fn(),
            governance_config_version=governance_config_version,
        )
        result = http_transport.send(envelope)
        return {
            "outcome": result.outcome.value,
            "retry_category": result.retry_category.value,
            "detail": result.detail,
            "platform_response": result.platform_response,
            # Note E: additive — publication/verification facts ride along for the
            # caller; None whenever the result has no created-content response.
            "publication_status": (
                result.publication_status.value if result.publication_status else None
            ),
            "verification_status": (
                result.verification_status.value if result.verification_status else None
            ),
        }

    return _transport
