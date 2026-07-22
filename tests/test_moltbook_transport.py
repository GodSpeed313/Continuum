"""
test_moltbook_transport.py — M7 Moltbook Transport Boundary and Deployment.

Covers docs/m7_moltbook_transport_boundary_and_deployment_spec.md (LOCKED 2026-07-20,
plus Implementation Note A) §13 acceptance tests, one deliberate-violation / clean-pass
pair per invariant, matching the convention every other M7 constraint used:

    - Core boundary: no raw-send path exists that bypasses an ActionEnvelope.
    - Approval freshness: expiry / config drift / payload-hash mismatch, each rejected
      before any network transmission; a fresh envelope sends normally.
    - Transport authority: payload is transmitted byte-identical to what was approved;
      the write path is fixed by action_type, never by external input.
    - Retry taxonomy: safe reads retry-eligible, governance denials never retried,
      ambiguous writes land in OUTCOME_UNKNOWN with no retry attempted.
    - Reconciliation: confirmed success/failure resolve cleanly; an unresolvable
      ambiguous write engages the kill switch and raises OperationalFreeze, never a
      governance violation.
    - Kill switch: manual and the two ACTIVE automated triggers block all outbound
      writes and leave reads unaffected; only an explicit operator clear() restores
      writes; the two DORMANT §14 triggers are proven inert, not just asserted so.
    - Dry run: full envelope validation runs, but no network call is made and the
      cadence/citation stores structurally reject a dry-run-namespaced ID even under
      direct attempted ingestion — proving isolation is structural, not conventional.
    - Implementation Note A: claim-status eligibility gate blocks writes (not reads)
      on `pending_claim`, is not a kill-switch/Arbiter/reconciliation event, and has
      no threshold of its own (unlike the §14 dormant triggers).
    - Implementation Note B: captcha verification is a transport-mechanical
      publishing precondition, never a new governed action/envelope. Deterministic
      solving; consecutive PLATFORM-CONFIRMED failures (never ambiguous ones) drive a
      NEW active kill-switch trigger (`captcha_suspension_risk`) at Continuum's own
      conservative threshold of 3 — distinct from Moltbook's documented 10 and from
      the §14.1 dormant trigger. Captcha events never enter the Arbiter's
      violation-trace path.
    - Reply parent identifier: MoltbookClient.send() requires `parent_post_id` for
      reply/comment actions; it is part of the Approved Action Envelope payload and
      therefore its hash — a post-approval mutation is caught the same way any other
      payload tamper is (§4 payload-hash check), no special-cased logic needed.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from moltbook.cadence import CadenceObservationStore
from moltbook.citation import CitationEdgeStore
from moltbook.client import MoltbookClient
from moltbook.dryrun import DRY_RUN_ID_PREFIX, is_dry_run_id
from moltbook.transport import (
    CAPTCHA_LOCAL_FAILURE_THRESHOLD,
    PLATFORM_CAPTCHA_SUSPENSION_LIMIT,
    ActionEnvelope,
    ActionType,
    CaptchaChallenge,
    CaptchaOutcome,
    CaptchaVerifier,
    DryRunTransport,
    EligibilityBlocked,
    EligibilityGate,
    EligibilityState,
    EnvelopeRejected,
    EnvelopeRejectionReason,
    HTTPResponse,
    KillSwitch,
    KillSwitchEngaged,
    MoltbookHTTPTransport,
    OperationalFreeze,
    PublicationStatus,
    RateLimitInfo,
    ReconciliationOutcome,
    RetryCategory,
    TransportOutcome,
    TransportResult,
    VerificationStatus,
    as_client_transport,
    canonical_payload_hash,
    describe_retry_category,
    make_dry_run_action_id,
    parse_verification_block,
    reconcile,
    resolve_ambiguous_write,
    solve_captcha_deterministic,
    validate_envelope,
)
from moltbook.transport import _WORD_NUMBER_VALUES, _collapse_letter_runs

CONFIG_V1 = "config-v1"
BASE = datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)


def _envelope(**overrides) -> ActionEnvelope:
    """
    A freshly-approved envelope (approved_at defaults to real now), for tests that go
    through an actual .send() call — those validate against the real clock. Freshness
    tests that need a controlled clock pass both `approved_at=BASE` and a matching
    `now=` explicitly to validate_envelope() instead of relying on this default.
    """
    defaults = dict(
        action_type=ActionType.POST,
        payload={"content": "hello moltbook"},
        approval_trace_id="trace-1",
        governance_config_version=CONFIG_V1,
    )
    defaults.update(overrides)
    return ActionEnvelope.approve(**defaults)


def _fake_request(status: int, body: dict | None = None, headers: dict | None = None):
    """A canned request_fn: ignores its args, always returns the same HTTPResponse
    (Implementation Note D shape — the old (status, body) tuple contract is gone)."""
    def _fn(method, path, json_body, headers_arg):
        return HTTPResponse(status, (body if body is not None else {}), headers or {})
    return _fn


# ───────────────────────────── Core boundary ─────────────────────────────────────

class TestCoreBoundary:
    def test_send_requires_an_action_envelope(self):
        """There is no write method on the transport that accepts raw content instead
        of an ActionEnvelope — the only write entry point is `send(envelope)`."""
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(200), live_config_version=CONFIG_V1)
        with pytest.raises(AttributeError):
            transport.send_raw("hello")  # no such method exists, by design

    def test_no_envelope_no_transmission(self):
        """Calling send() with something that is not an ActionEnvelope fails before
        any request_fn call — proven by a request_fn that raises if ever invoked."""
        def _boom(*_a, **_kw):
            raise AssertionError("network call must not happen")
        transport = MoltbookHTTPTransport("key", request_fn=_boom, live_config_version=CONFIG_V1)
        with pytest.raises(AttributeError):
            transport.send(object())  # not an ActionEnvelope — no action_type attr


# ───────────────────────────── Approval freshness ────────────────────────────────

class TestApprovalFreshness:
    def test_expired_envelope_rejected(self):
        env = _envelope(approved_at=BASE, execution_window_seconds=1)
        with pytest.raises(EnvelopeRejected) as exc:
            validate_envelope(env, live_config_version=CONFIG_V1, now=BASE + timedelta(seconds=5))
        assert exc.value.reason is EnvelopeRejectionReason.EXPIRED

    def test_fresh_envelope_sends(self):
        env = _envelope(approved_at=BASE)
        validate_envelope(env, live_config_version=CONFIG_V1, now=BASE + timedelta(seconds=1))  # no raise

    def test_config_drift_rejected(self):
        env = _envelope(approved_at=BASE, governance_config_version=CONFIG_V1)
        with pytest.raises(EnvelopeRejected) as exc:
            validate_envelope(env, live_config_version="config-v2", now=BASE)
        assert exc.value.reason is EnvelopeRejectionReason.CONFIG_DRIFT

    def test_matching_config_sends(self):
        env = _envelope(approved_at=BASE, governance_config_version=CONFIG_V1)
        validate_envelope(env, live_config_version=CONFIG_V1, now=BASE)  # no raise

    def test_payload_hash_mismatch_rejected(self):
        env = _envelope(approved_at=BASE)
        tampered = ActionEnvelope(
            **{**env.__dict__, "payload": {"content": "TAMPERED"}},
        )
        with pytest.raises(EnvelopeRejected) as exc:
            validate_envelope(tampered, live_config_version=CONFIG_V1, now=BASE)
        assert exc.value.reason is EnvelopeRejectionReason.PAYLOAD_DRIFT

    def test_untampered_payload_hash_matches(self):
        env = _envelope()
        assert env.payload_hash == canonical_payload_hash(env.payload)
        validate_envelope(env, live_config_version=CONFIG_V1, now=BASE)  # no raise


# ───────────────────────────── Transport authority ───────────────────────────────

class TestTransportAuthority:
    def test_payload_transmitted_byte_identical(self):
        captured = {}
        def _capture(method, path, body, headers):
            captured["body"] = body
            return HTTPResponse(200, {"id": "post123"})
        env = _envelope(payload={"content": "exact bytes", "tag": "m7"})
        transport = MoltbookHTTPTransport("key", request_fn=_capture, live_config_version=CONFIG_V1)
        transport.send(env)
        assert captured["body"] == env.payload

    def test_write_path_fixed_by_action_type_not_external_input(self):
        """Real endpoint shapes per docs/moltbook_api_spec.md §4: posts go to
        /posts; a reply is nested under its parent post, not a flat endpoint."""
        captured = {}
        def _capture(method, path, body, headers):
            captured["path"] = path
            return HTTPResponse(200, {})
        transport = MoltbookHTTPTransport("key", request_fn=_capture, live_config_version=CONFIG_V1)
        transport.send(_envelope(action_type=ActionType.POST))
        assert captured["path"] == "/posts"
        transport.send(_envelope(
            action_type=ActionType.REPLY, action_id="a2",
            payload={"content": "hi", "parent_post_id": "p1"},
        ))
        assert captured["path"] == "/posts/p1/comments"

    def test_reply_without_parent_post_id_rejected(self):
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(200), live_config_version=CONFIG_V1)
        with pytest.raises(ValueError):
            transport.send(_envelope(action_type=ActionType.REPLY, action_id="a3"))

    def test_parent_post_id_not_transmitted_in_reply_body(self):
        """docs/moltbook_api_spec.md §4: the post ID belongs only in the URL path —
        it is not a documented request-body field, so it must be stripped before
        transmission even though it stays part of the approved (and hashed) payload."""
        captured = {}
        def _capture(method, path, body, headers):
            captured["body"] = body
            return HTTPResponse(200, {})
        transport = MoltbookHTTPTransport("key", request_fn=_capture, live_config_version=CONFIG_V1)
        transport.send(_envelope(
            action_type=ActionType.REPLY, action_id="a4",
            payload={"content": "hi", "parent_post_id": "p1"},
        ))
        assert captured["body"] == {"content": "hi"}

    def test_documented_parent_id_passthrough_for_nested_threading(self):
        """The platform's OWN optional `parent_id` (nested comment threading,
        docs/moltbook_api_spec.md §4) is a real, documented body field — distinct
        from parent_post_id (routing only) — and passes through untouched if a
        caller supplies it. Not wired at the MoltbookClient level (Phase One is flat
        top-level comments only); this only proves the transport doesn't drop it."""
        captured = {}
        def _capture(method, path, body, headers):
            captured["body"] = body
            return HTTPResponse(200, {})
        transport = MoltbookHTTPTransport("key", request_fn=_capture, live_config_version=CONFIG_V1)
        transport.send(_envelope(
            action_type=ActionType.REPLY, action_id="a5",
            payload={"content": "hi", "parent_post_id": "p1", "parent_id": "comment-9"},
        ))
        assert captured["body"] == {"content": "hi", "parent_id": "comment-9"}


# ───────────────────────────── Retry taxonomy ────────────────────────────────────

class TestRetryTaxonomy:
    def test_safe_read_classified(self):
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(200), live_config_version=CONFIG_V1)
        result = transport.read_feed()
        assert result.outcome is TransportOutcome.SUCCESS
        assert result.retry_category is RetryCategory.SAFE_READ

    def test_governance_denial_never_retried(self):
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(403), live_config_version=CONFIG_V1)
        result = transport.send(_envelope())
        assert result.outcome is TransportOutcome.FAILURE
        assert result.retry_category is RetryCategory.GOVERNANCE_DENIAL

    def test_409_conflict_is_a_reconciliation_duplicate_candidate(self):
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(409), live_config_version=CONFIG_V1)
        result = transport.send(_envelope())
        assert result.outcome is TransportOutcome.OUTCOME_UNKNOWN
        assert result.retry_category is RetryCategory.AMBIGUOUS_WRITE

    def test_409_conflict_resolves_via_reconciliation_like_any_ambiguous_write(self):
        env = _envelope()
        kill_switch = KillSwitch()
        result = transport_ambiguous_result()
        recon = resolve_ambiguous_write(result, env, kill_switch, idempotency_lookup=lambda aid: True)
        assert recon.outcome is ReconciliationOutcome.CONFIRMED_SUCCESS

    def test_410_gone_is_terminal_never_retried(self):
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(410), live_config_version=CONFIG_V1)
        result = transport.send(_envelope())
        assert result.outcome is TransportOutcome.FAILURE
        assert result.retry_category is RetryCategory.GOVERNANCE_DENIAL

    def test_429_rate_limited_not_governance_denial(self):
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(429), live_config_version=CONFIG_V1)
        result = transport.send(_envelope())
        assert result.outcome is TransportOutcome.FAILURE
        assert result.retry_category is RetryCategory.RATE_LIMITED
        assert result.retry_category is not RetryCategory.GOVERNANCE_DENIAL

    def test_ambiguous_write_no_retry_attempted(self):
        calls = []
        def _fn(method, path, body, headers):
            calls.append(1)
            return HTTPResponse(503, {})
        transport = MoltbookHTTPTransport("key", request_fn=_fn, live_config_version=CONFIG_V1)
        result = transport.send(_envelope())
        assert result.outcome is TransportOutcome.OUTCOME_UNKNOWN
        assert result.retry_category is RetryCategory.AMBIGUOUS_WRITE
        assert len(calls) == 1  # exactly one attempt — no automatic retry


# ───────────────── Implementation Note C: rate-limit retry category ────────────

class TestRateLimitedCategory:
    """
    §8's fifth category (Implementation Note C). All six required proofs from the
    note: 429 maps only to RATE_LIMITED; it never enters the governance-denial or
    ambiguous-write reconciliation paths; the transport performs no autonomous
    retry; unsupported categories fail loudly rather than silently defaulting; and a
    "later retry" must revalidate approval freshness rather than reusing a stale
    envelope.
    """

    def test_429_maps_only_to_rate_limited(self):
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(429), live_config_version=CONFIG_V1)
        result = transport.send(_envelope())
        assert result.retry_category is RetryCategory.RATE_LIMITED
        assert result.retry_category not in (
            RetryCategory.GOVERNANCE_DENIAL,
            RetryCategory.AMBIGUOUS_WRITE,
            RetryCategory.SAFE_READ,
            RetryCategory.IDEMPOTENT_WRITE,
        )

    def test_429_never_enters_the_governance_denial_trace_path(self):
        """A governance denial is terminal by definition (§8) — 429 must never be
        classified that way, since the underlying action may still be retriable
        later. This is the same assertion as above from the opposite direction: the
        outcome must not collapse into denial-shaped handling anywhere."""
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(429), live_config_version=CONFIG_V1)
        result = transport.send(_envelope())
        assert result.retry_category is not RetryCategory.GOVERNANCE_DENIAL
        assert result.outcome is TransportOutcome.FAILURE  # a definite fact, not a violation

    def test_429_never_enters_ambiguous_write_reconciliation(self):
        """resolve_ambiguous_write (§9) is typed for OUTCOME_UNKNOWN only. A 429
        result is TransportOutcome.FAILURE, not OUTCOME_UNKNOWN, so attempting to
        route it through reconciliation must fail structurally, not silently
        proceed as if it were an ambiguous write."""
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(429), live_config_version=CONFIG_V1)
        result = transport.send(_envelope())
        kill_switch = KillSwitch()
        with pytest.raises(ValueError):
            resolve_ambiguous_write(result, _envelope(), kill_switch)

    def test_transport_performs_no_autonomous_retry_after_429(self):
        calls = []
        def _fn(method, path, body, headers):
            calls.append(1)
            return HTTPResponse(429, {"error": "rate_limited"})
        transport = MoltbookHTTPTransport("key", request_fn=_fn, live_config_version=CONFIG_V1)
        transport.send(_envelope())
        assert len(calls) == 1  # exactly one attempt — the transport never retries itself

    def test_describe_retry_category_covers_every_known_category(self):
        for category in RetryCategory:
            description = describe_retry_category(category)
            assert isinstance(description, str) and description

    def test_unsupported_retry_category_fails_loudly(self):
        """A value that isn't a real RetryCategory member must never silently
        render as some other category's description — it must raise."""
        with pytest.raises(ValueError):
            describe_retry_category("not_a_real_category")  # type: ignore[arg-type]

    def test_unsupported_retry_category_in_transport_result_also_fails_loudly(self):
        bogus_result = TransportResult(TransportOutcome.FAILURE, "not_a_real_category")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            describe_retry_category(bogus_result.retry_category)

    def test_a_later_retry_must_revalidate_approval_freshness(self):
        """
        Implementation Note C: a future retry attempt must revalidate approval
        freshness, governance config version, and payload hash — never blindly
        reuse an expired approval. Simulated here as: a 429 comes back, time
        passes, and something naively attempts to reuse the SAME (now-expired)
        envelope for a 'retry' — ordinary §4 freshness validation must reject it,
        with no rate-limit-specific bypass anywhere.
        """
        env = _envelope(execution_window_seconds=60)  # approved_at defaults to real now
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(429), live_config_version=CONFIG_V1)
        # First attempt, still within the fresh window: reaches the network call and
        # gets the 429.
        result = transport.send(env)
        assert result.retry_category is RetryCategory.RATE_LIMITED
        # A naive "retry" reusing the identical envelope, attempted once the approval
        # window has elapsed, must be rejected by §4 — not silently sent. Simulated
        # by advancing the clock passed to validate_envelope rather than sleeping.
        with pytest.raises(EnvelopeRejected) as exc:
            validate_envelope(env, live_config_version=CONFIG_V1, now=env.approval_expiry + timedelta(seconds=1))
        assert exc.value.reason is EnvelopeRejectionReason.EXPIRED


# ───────────────── Implementation Note D: request_fn header capture ────────────

class TestHeaderCapture:
    """
    Implementation Note D: the request_fn seam returns HTTPResponse (status, body,
    headers) — the old two-tuple is gone, no compatibility adapter. Required proofs:
    headers captured on the success path AND the HTTPError path (429 arrives via the
    latter); missing/malformed Retry-After parse to None, never raise; header lookup
    is case-insensitive by lowercase normalization; both RFC 9110 Retry-After forms
    parse; capture never triggers a retry (request count stays exactly one); and a
    pre-response transport failure surfaces no headers at all.
    """

    RL_HEADERS = {
        "X-RateLimit-Limit": "100",
        "X-RateLimit-Remaining": "99",
        "X-RateLimit-Reset": "3600",
    }

    def test_success_response_headers_captured_and_surfaced(self):
        transport = MoltbookHTTPTransport(
            "key", request_fn=_fake_request(200, {"id": "p1"}, self.RL_HEADERS),
            live_config_version=CONFIG_V1,
        )
        result = transport.send(_envelope())
        assert result.outcome is TransportOutcome.SUCCESS
        assert result.platform_headers == {
            "x-ratelimit-limit": "100", "x-ratelimit-remaining": "99", "x-ratelimit-reset": "3600",
        }
        assert result.rate_limit == RateLimitInfo(limit=100, remaining=99, reset=3600)

    def test_429_response_headers_captured_and_surfaced(self):
        transport = MoltbookHTTPTransport(
            "key",
            request_fn=_fake_request(429, {"error": "rate_limited"}, {**self.RL_HEADERS, "Retry-After": "120"}),
            live_config_version=CONFIG_V1,
        )
        result = transport.send(_envelope())
        assert result.retry_category is RetryCategory.RATE_LIMITED
        assert result.rate_limit.retry_after_delay_seconds == 120
        assert result.rate_limit.retry_after_http_date is None
        assert result.rate_limit.limit == 100

    def test_real_request_captures_headers_on_success_path(self, monkeypatch):
        """_real_request itself, urlopen success path: headers reach HTTPResponse."""
        import io
        import urllib.request as _ur

        class _FakeResp(io.BytesIO):
            status = 200
            headers = {"X-RateLimit-Remaining": "42"}

        monkeypatch.setattr(_ur, "urlopen", lambda req, timeout: _FakeResp(b'{"id": "p1"}'))
        transport = MoltbookHTTPTransport("key", live_config_version=CONFIG_V1)
        response = transport._real_request("POST", "/posts", {"content": "x"}, {})
        assert response.status_code == 200
        assert response.body == {"id": "p1"}
        assert response.headers["x-ratelimit-remaining"] == "42"

    def test_real_request_captures_headers_on_httperror_path(self, monkeypatch):
        """_real_request, HTTPError path — the path a real 429 actually arrives on.
        Single-path capture would silently fail exactly here (Note D)."""
        import io
        import urllib.error
        import urllib.request as _ur
        from email.message import Message

        hdrs = Message()
        hdrs["Retry-After"] = "60"
        hdrs["X-RateLimit-Remaining"] = "0"

        def _raise(req, timeout):
            raise urllib.error.HTTPError(
                "https://example.invalid/posts", 429, "Too Many Requests", hdrs,
                io.BytesIO(b'{"error": "rate_limited"}'),
            )

        monkeypatch.setattr(_ur, "urlopen", _raise)
        transport = MoltbookHTTPTransport("key", live_config_version=CONFIG_V1)
        response = transport._real_request("POST", "/posts", {"content": "x"}, {})
        assert response.status_code == 429
        assert response.body == {"error": "rate_limited"}
        assert response.rate_limit.retry_after_delay_seconds == 60
        assert response.rate_limit.remaining == 0

    def test_missing_retry_after_parses_to_none(self):
        info = HTTPResponse(429, {}, self.RL_HEADERS).rate_limit  # no Retry-After at all
        assert info.retry_after_delay_seconds is None
        assert info.retry_after_http_date is None
        assert info.limit == 100  # the documented all-response headers still parse

    def test_malformed_retry_after_parses_to_none_never_raises(self):
        """Neither valid delay-seconds nor a valid HTTP-date: both typed fields are
        None, no exception — the transport reports facts, it doesn't crash on a
        platform sending garbage. Raw value stays available in headers."""
        response = HTTPResponse(429, {}, {"Retry-After": "soon-ish", "X-RateLimit-Limit": "abc"})
        assert response.rate_limit.retry_after_delay_seconds is None
        assert response.rate_limit.retry_after_http_date is None
        assert response.rate_limit.limit is None  # malformed int also parses to None
        assert response.headers["retry-after"] == "soon-ish"

    def test_retry_after_http_date_form_parses(self):
        response = HTTPResponse(429, {}, {"Retry-After": "Wed, 22 Jul 2026 12:00:00 GMT"})
        assert response.rate_limit.retry_after_delay_seconds is None
        assert response.rate_limit.retry_after_http_date == datetime(
            2026, 7, 22, 12, 0, 0, tzinfo=timezone.utc,
        )

    def test_header_lookup_is_case_insensitive(self):
        """Names normalize to lowercase at construction, so any casing the platform
        sends resolves to the same normalized fields."""
        for name in ("retry-after", "Retry-After", "RETRY-AFTER", "rEtRy-AfTeR"):
            assert HTTPResponse(429, {}, {name: "30"}).rate_limit.retry_after_delay_seconds == 30

    def test_header_capture_triggers_no_retry(self):
        """Capturing a Retry-After value must never become acting on it: exactly one
        network call happens even when the header says when a retry would succeed."""
        calls = []
        def _fn(method, path, body, headers):
            calls.append(1)
            return HTTPResponse(429, {"error": "rate_limited"}, {"Retry-After": "1"})
        transport = MoltbookHTTPTransport("key", request_fn=_fn, live_config_version=CONFIG_V1)
        result = transport.send(_envelope())
        assert result.rate_limit.retry_after_delay_seconds == 1
        assert len(calls) == 1

    def test_pre_response_failure_surfaces_no_headers(self):
        """No response received → nothing to capture: platform_headers and
        rate_limit are None, not fabricated empties."""
        def _fn(method, path, body, headers):
            raise ConnectionError("network down")
        transport = MoltbookHTTPTransport("key", request_fn=_fn, live_config_version=CONFIG_V1)
        result = transport.send(_envelope())
        assert result.outcome is TransportOutcome.OUTCOME_UNKNOWN
        assert result.platform_headers is None
        assert result.rate_limit is None

    def test_safe_read_also_surfaces_headers(self):
        """§5: ALL responses carry X-RateLimit-* — capture isn't a write-path
        special case; read_feed surfaces them the same way."""
        transport = MoltbookHTTPTransport(
            "key", request_fn=_fake_request(200, {"posts": []}, self.RL_HEADERS),
            live_config_version=CONFIG_V1,
        )
        result = transport.read_feed()
        assert result.rate_limit == RateLimitInfo(limit=100, remaining=99, reset=3600)


# ───────────────────────────── Reconciliation ────────────────────────────────────

class TestReconciliation:
    def test_confirmed_success_updates_state(self):
        recon = reconcile(_envelope(), receipt_lookup=lambda aid: True)
        assert recon.outcome is ReconciliationOutcome.CONFIRMED_SUCCESS

    def test_confirmed_failure_updates_state(self):
        recon = reconcile(_envelope(), receipt_lookup=lambda aid: False)
        assert recon.outcome is ReconciliationOutcome.CONFIRMED_FAILURE

    def test_unresolved_outcome_freezes_and_escalates(self):
        env = _envelope()
        kill_switch = KillSwitch()
        ambiguous = transport_ambiguous_result()
        with pytest.raises(OperationalFreeze):
            resolve_ambiguous_write(ambiguous, env, kill_switch, receipt_lookup=lambda aid: None)
        assert kill_switch.engaged
        assert kill_switch.activation_log[-1].trigger == "unresolved_ambiguous_write"

    def test_reconciliation_only_reads_never_retries_the_write(self):
        """No lookup supplied means every method is a no-op read attempt; the original
        write is never reissued by reconcile() itself."""
        recon = reconcile(_envelope())
        assert recon.outcome is ReconciliationOutcome.OUTCOME_UNKNOWN


def transport_ambiguous_result():
    from moltbook.transport import TransportResult
    return TransportResult(TransportOutcome.OUTCOME_UNKNOWN, RetryCategory.AMBIGUOUS_WRITE)


# ───────────────────────────── Kill switch ───────────────────────────────────────

class TestKillSwitch:
    def test_manual_activation_blocks_all_writes(self):
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(200), live_config_version=CONFIG_V1)
        transport.kill_switch.activate_manual(operator="lamont")
        with pytest.raises(KillSwitchEngaged):
            transport.send(_envelope())

    def test_active_automated_trigger_blocks_writes(self):
        """Automated activation test exercises ONLY the two currently-active triggers
        (unresolved ambiguous write, reconciliation contradiction) — never the dormant
        §14 or auth-anomaly triggers, per the spec's own instruction."""
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(200), live_config_version=CONFIG_V1)
        transport.kill_switch.activate_reconciliation_contradiction(action_class="post")
        with pytest.raises(KillSwitchEngaged):
            transport.send(_envelope())

    def test_reads_continue_while_engaged(self):
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(200), live_config_version=CONFIG_V1)
        transport.kill_switch.activate_manual(operator="lamont")
        result = transport.read_feed()  # must not raise
        assert result.outcome is TransportOutcome.SUCCESS

    def test_operator_only_reenablement(self):
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(200), live_config_version=CONFIG_V1)
        transport.kill_switch.activate_manual(operator="lamont")
        transport.kill_switch.clear(operator="lamont", detail="incident resolved")
        transport.send(_envelope())  # no raise now

    def test_no_automatic_recovery(self):
        """A subsequent successful request must not itself clear the switch."""
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(200), live_config_version=CONFIG_V1)
        transport.kill_switch.activate_manual(operator="lamont")
        transport.read_feed()  # succeeds, but is a read — must not clear anything
        assert transport.kill_switch.engaged

    def test_structured_activation_audit(self):
        kill_switch = KillSwitch()
        kill_switch.activate_ambiguous_write(action_class="post", detail="reconciliation exhausted")
        entry = kill_switch.activation_log[-1]
        assert entry.mode == "automated"
        assert entry.trigger == "unresolved_ambiguous_write"
        assert entry.affected_action_class == "post"
        assert entry.timestamp is not None

    # ── §14 dormant-trigger non-activation (companion negative tests) ──────────
    def test_dormant_repeated_integrity_failures_never_activates(self):
        kill_switch = KillSwitch()
        kill_switch.activate_repeated_integrity_failures(count=999, window_seconds=1)
        assert not kill_switch.engaged
        assert kill_switch.activation_log == ()

    def test_dormant_authentication_anomaly_never_activates(self):
        kill_switch = KillSwitch()
        kill_switch.activate_authentication_anomaly(failure_count=999)
        assert not kill_switch.engaged
        assert kill_switch.activation_log == ()


# ───────────────────────────── Dry run isolation ─────────────────────────────────

class TestDryRunIsolation:
    def test_dry_run_produces_trace_no_network_call(self):
        def _boom(*_a, **_kw):
            raise AssertionError("dry run must never make a network call")
        dry = DryRunTransport(live_config_version=CONFIG_V1)
        env = _envelope(action_id=make_dry_run_action_id())
        outcome = dry.send(env)
        assert outcome.simulated_outcome is TransportOutcome.SUCCESS
        assert len(dry.trace) == 1

    def test_dry_run_rejects_non_namespaced_id(self):
        dry = DryRunTransport(live_config_version=CONFIG_V1)
        with pytest.raises(ValueError):
            dry.send(_envelope(action_id="real-post-1"))

    def test_cadence_store_structurally_rejects_dry_run_id(self, tmp_path):
        store = CadenceObservationStore(tmp_path / "cadence.json", "continuumagent")
        dry_id = make_dry_run_action_id()
        assert is_dry_run_id(dry_id)
        was_new = store.ingest(dry_id, BASE)
        assert was_new is False
        assert store.observation_count() == 0  # no production mutation at all

    def test_citation_store_structurally_rejects_dry_run_id(self, tmp_path):
        store = CitationEdgeStore(tmp_path / "citation.json", "continuumagent")
        dry_id = make_dry_run_action_id()
        was_new = store.ingest(dry_id, "continuumagent", ["someone_else"], BASE)
        assert was_new is False
        assert store.post_count() == 0  # no grounded longitudinal data mutation

    def test_live_confirmed_action_does_mutate_exactly_one_store_entry(self, tmp_path):
        """Contrast case: a REAL (non-dry-run) ID mutates the store exactly once —
        proves the rejection above is namespace-specific, not a store that silently
        drops all ingestion."""
        store = CadenceObservationStore(tmp_path / "cadence.json", "continuumagent")
        was_new = store.ingest("real-post-1", BASE)
        assert was_new is True
        assert store.observation_count() == 1


# ───────────────────── Implementation Note A: eligibility gate ──────────────────

class TestEligibilityGate:
    def test_claimed_allows_writes(self):
        gate = EligibilityGate(state=EligibilityState.CLAIMED)
        gate.check_write()  # no raise

    def test_pending_claim_blocks_writes(self):
        gate = EligibilityGate(state=EligibilityState.PENDING_CLAIM)
        with pytest.raises(EligibilityBlocked):
            gate.check_write()

    def test_pending_claim_does_not_block_reads(self):
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(200), live_config_version=CONFIG_V1)
        transport.eligibility.update(EligibilityState.PENDING_CLAIM)
        result = transport.read_feed()  # must not raise
        assert result.outcome is TransportOutcome.SUCCESS

    def test_pending_claim_blocks_transport_send(self):
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(200), live_config_version=CONFIG_V1)
        transport.eligibility.update(EligibilityState.PENDING_CLAIM)
        with pytest.raises(EligibilityBlocked):
            transport.send(_envelope())

    def test_eligibility_is_not_a_kill_switch_event(self):
        """Reverting to pending_claim must not touch the kill switch at all — it is a
        third, distinct category (Implementation Note A), not §10 machinery."""
        transport = MoltbookHTTPTransport("key", request_fn=_fake_request(200), live_config_version=CONFIG_V1)
        transport.eligibility.update(EligibilityState.PENDING_CLAIM)
        with pytest.raises(EligibilityBlocked):
            transport.send(_envelope())
        assert not transport.kill_switch.engaged
        assert transport.kill_switch.activation_log == ()

    def test_check_eligibility_updates_state_from_response(self):
        transport = MoltbookHTTPTransport(
            "key", request_fn=_fake_request(200, {"status": "pending_claim"}),
            live_config_version=CONFIG_V1,
        )
        state = transport.check_eligibility()
        assert state is EligibilityState.PENDING_CLAIM
        assert transport.eligibility.state is EligibilityState.PENDING_CLAIM
        assert transport.eligibility.log[-1]["state"] == "pending_claim"


# ───────────────────── MoltbookClient integration adapter ───────────────────────

class TestClientAdapter:
    def test_adapter_sends_post_through_http_transport(self):
        captured = {}
        def _capture(method, path, body, headers):
            captured["path"] = path
            captured["body"] = body
            return HTTPResponse(200, {"id": "p1"})
        http_transport = MoltbookHTTPTransport("key", request_fn=_capture, live_config_version=CONFIG_V1)
        client_transport = as_client_transport(http_transport, governance_config_version=CONFIG_V1)
        result = client_transport(action="post", content="hi", headers={})
        assert result["outcome"] == "success"
        assert captured["path"] == "/posts"
        assert captured["body"] == {"content": "hi"}

    def test_adapter_wires_comment_to_the_real_nested_endpoint(self):
        """Resolved (was a known gap): client.send()'s parent_post_id now flows
        through to the real POST /posts/{id}/comments shape (docs/moltbook_api_spec.md §4)."""
        captured = {}
        def _capture(method, path, body, headers):
            captured["path"] = path
            captured["body"] = body
            return HTTPResponse(200, {"id": "c1"})
        http_transport = MoltbookHTTPTransport("key", request_fn=_capture, live_config_version=CONFIG_V1)
        client_transport = as_client_transport(http_transport, governance_config_version=CONFIG_V1)
        result = client_transport(action="comment", content="hi", headers={}, parent_post_id="p1")
        assert result["outcome"] == "success"
        assert captured["path"] == "/posts/p1/comments"
        # parent_post_id routes the URL only — docs/moltbook_api_spec.md §4 has no
        # such body field, so it must not appear in what's actually transmitted.
        assert captured["body"] == {"content": "hi"}

    def test_adapter_reply_without_parent_post_id_rejected(self):
        http_transport = MoltbookHTTPTransport("key", request_fn=_fake_request(200), live_config_version=CONFIG_V1)
        client_transport = as_client_transport(http_transport, governance_config_version=CONFIG_V1)
        with pytest.raises(ValueError):
            client_transport(action="comment", content="hi", headers={})


# ───────────────────── Reply parent identifier (client.send()) ─────────────────

class TestReplyParentIdentifier:
    """
    MoltbookClient.send() now requires parent_post_id for reply/comment actions
    (moltbook/client.py) — it's a fail-fast client-side check, not the only
    enforcement point. parent_post_id lives inside the Approved Action Envelope's
    payload, so it's covered by the same payload-hash freshness check (§4) as any
    other payload field — no bespoke "parent changed" logic needed.
    """

    def _client(self, **kw):
        kw.setdefault("transport", lambda **k: {"ok": True, "kwargs": k})
        kw.setdefault("declared_handle", "continuumagent")
        return MoltbookClient(**kw)

    def test_reply_requires_parent_post_id_at_the_client(self):
        client = self._client()
        with pytest.raises(ValueError):
            client.send("a reply", action="comment")

    def test_reply_with_parent_post_id_reaches_transport(self):
        client = self._client()
        result = client.send("a reply", action="comment", parent_post_id="p1")
        assert result["kwargs"]["parent_post_id"] == "p1"

    def test_reply_rejected_when_parent_post_id_changes_after_approval(self):
        """The parent_post_id lives in envelope.payload, so mutating it after
        approval is caught by the ordinary payload-hash mismatch check (§4) —
        proven directly at the ActionEnvelope level, no reply-specific code path."""
        env = ActionEnvelope.approve(
            action_type=ActionType.REPLY,
            payload={"content": "hi", "parent_post_id": "p1"},
            approval_trace_id="t1",
            governance_config_version=CONFIG_V1,
        )
        tampered = ActionEnvelope(**{**env.__dict__, "payload": {"content": "hi", "parent_post_id": "p2"}})
        with pytest.raises(EnvelopeRejected) as exc:
            validate_envelope(tampered, live_config_version=CONFIG_V1)
        assert exc.value.reason is EnvelopeRejectionReason.PAYLOAD_DRIFT

    def test_successful_governed_reply_uses_the_approved_parent_id(self):
        captured = {}
        def _capture(method, path, body, headers):
            captured["path"] = path
            captured["body"] = body
            return HTTPResponse(200, {"id": "c1"})
        http_transport = MoltbookHTTPTransport("key", request_fn=_capture, live_config_version=CONFIG_V1)
        env = ActionEnvelope.approve(
            action_type=ActionType.REPLY,
            payload={"content": "hi", "parent_post_id": "p1"},
            approval_trace_id="t1",
            governance_config_version=CONFIG_V1,
        )
        result = http_transport.send(env)
        assert result.outcome is TransportOutcome.SUCCESS
        # The approved parent ID routed the request to the right URL...
        assert captured["path"] == "/posts/p1/comments"
        # ...but is not itself a documented body field (docs/moltbook_api_spec.md §4)
        # and must not be transmitted.
        assert "parent_post_id" not in captured["body"]
        assert captured["body"] == {"content": "hi"}

    def test_adapter_rejects_dm_as_out_of_phase_one_scope(self):
        http_transport = MoltbookHTTPTransport("key", request_fn=_fake_request(200), live_config_version=CONFIG_V1)
        client_transport = as_client_transport(http_transport, governance_config_version=CONFIG_V1)
        with pytest.raises(ValueError):
            client_transport(action="dm", content="hi", headers={})


# ──────────── Implementation Notes B + E: captcha verification ─────────────────

import copy
import json as _json
from pathlib import Path

CAPTCHA_FIXTURE = _json.loads(
    (Path(__file__).parent / "fixtures" / "moltbook_captcha_issuance.json")
    .read_text(encoding="utf-8")
)

CAPTCHA_PROMPT = "What is 12 plus 3.00?"


def _challenge(verification_code: str = "moltbook_verify_test1") -> CaptchaChallenge:
    return CaptchaChallenge(
        verification_code=verification_code, prompt=CAPTCHA_PROMPT,
        expires_at=BASE + timedelta(minutes=5),
    )


def _challenge_write_body(*, expires_in_seconds: int = 300, verification_code: str | None = None) -> dict:
    """The fixture's captured write-response shape (Note E), with expires_at moved
    to a live future instant so flow tests exercise the real path — structure stays
    exactly the fixture's."""
    body = copy.deepcopy(CAPTCHA_FIXTURE["write_response_with_challenge"])
    expires = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
    body["post"]["verification"]["expires_at"] = expires.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    if verification_code is not None:
        body["post"]["verification"]["verification_code"] = verification_code
    return body


def _confirmed_success(_verification_code, _answer):
    return CaptchaOutcome.CONFIRMED_SUCCESS, copy.deepcopy(CAPTCHA_FIXTURE["verify_response_success"])


def _confirmed_failure(_verification_code, _answer):
    return CaptchaOutcome.CONFIRMED_FAILURE, copy.deepcopy(CAPTCHA_FIXTURE["verify_response_failure"])


def _ambiguous(_verification_code, _answer):
    return CaptchaOutcome.AMBIGUOUS, None


class TestCaptchaSolver:
    def test_deterministic_solve(self):
        assert solve_captcha_deterministic("What is 12 plus 3.00?") == "15.00"
        assert solve_captcha_deterministic("12 plus 3.00") == solve_captcha_deterministic("12 plus 3.00")

    def test_thresholds_are_distinct_and_documented(self):
        """Continuum's margin must stay strictly under Moltbook's documented limit.
        Note E precision: these are DIFFERENT rules over DIFFERENT windows (ours:
        consecutive confirmed only; theirs: trailing-10, expiry counted) — the
        numeric comparison here proves the margin, not an equivalence."""
        assert CAPTCHA_LOCAL_FAILURE_THRESHOLD == 3
        assert PLATFORM_CAPTCHA_SUSPENSION_LIMIT == 10
        assert CAPTCHA_LOCAL_FAILURE_THRESHOLD < PLATFORM_CAPTCHA_SUSPENSION_LIMIT

    def test_solver_handles_documented_word_number_obfuscation(self):
        """The live skill.md example verbatim: 'twenty meters... slows by five' → 15.00,
        written in the platform's alternating-caps scattered-symbol style.
        Formerly the xfail pin for the pre-Note-F solver gap; Implementation
        Note F (2026-07-22) closed it, flipping this to a required pass."""
        documented_example = (
            "A] lO^bSt-Er S[wImS aT/ tW]eNn-Tyy mE^tE[rS aNd] SlO/wS bY^ fI[vE, "
            "wH-aTs] ThE/ nEw^ SpE[eD?"
        )
        assert solve_captcha_deterministic(documented_example) == "15.00"

    # ── Implementation Note F: extended solver coverage (§F.6) ────────────────

    def test_fixture_challenge_text_solves(self):
        """The redacted protocol fixture's challenge_text solves end-to-end."""
        fixture_path = (
            Path(__file__).parent / "fixtures" / "moltbook_captcha_issuance.json"
        )
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        challenge_text = (
            fixture["write_response_with_challenge"]["post"]["verification"]["challenge_text"]
        )
        assert solve_captcha_deterministic(challenge_text) == "15.00"

    def test_letter_doubling_collapses_to_vocabulary(self):
        """§F.2 doubled-letter tolerance: 'twenntyy'/'fivve' resolve via
        consecutive-duplicate collapse."""
        assert solve_captcha_deterministic("What is twenntyy plus fivve?") == "25.00"

    def test_compound_word_numbers(self):
        """§F.2: tens+unit as adjacent tokens and as one merged token."""
        assert solve_captcha_deterministic("What is twenty five plus three?") == "28.00"
        assert solve_captcha_deterministic("What is twentyfive plus three?") == "28.00"

    def test_signed_operand_parses_with_sign(self):
        """Signed-operand regression group (added at Note F sign-off — this
        path previously had NO coverage anywhere in the suite): a negative
        operand keeps its sign through normalization."""
        assert solve_captcha_deterministic("What is -12 plus 3?") == "-9.00"

    def test_negative_operand_with_operator_word_sign_not_double_read(self):
        """§F.3.3: with a recognized operator WORD present, the operand's sign
        stays attached to the number and is never also read as the operator —
        including under symbol-noise obfuscation."""
        assert solve_captcha_deterministic("wH-aTs] -12 pLuS 3?") == "-9.00"

    def test_sign_consumed_operand_ambiguity_raises(self):
        """§F.3.3 double-read regression: '12 -3' used to return '15.00' by
        reading the '-' twice (sign of -3 AND the operator). The '-' sits
        inside the extracted number's span, so no operator remains — loud
        failure, never a guess."""
        with pytest.raises(ValueError, match="operator"):
            solve_captcha_deterministic("12 -3")

    def test_freestanding_symbol_operator_still_works(self):
        """§F.1: symbols freestanding or digit-adjacent survive normalization
        and still resolve via the symbol fallback."""
        assert solve_captcha_deterministic("12 - 3") == "9.00"
        assert solve_captcha_deterministic("12+3") == "15.00"

    def test_letter_adjacent_noise_never_becomes_operator(self):
        """The Note E fixture-gotcha class, closed by §F.1/F.3.3: noise '-'
        inside a word must not be read as subtraction. With an operator word
        present the word wins; with none, the prompt fails loudly."""
        assert solve_captcha_deterministic("wH-aTs 12 mInUs 3?") == "9.00"
        with pytest.raises(ValueError, match="operator"):
            solve_captcha_deterministic("wH-aTs 12 aNd 3?")

    def test_multiple_distinct_symbols_raise(self):
        """§F.3.3 (operator ruling at sign-off): more than one distinct
        operator meaning surviving outside operand spans is ambiguous —
        neither text position nor fixed priority may pick a winner."""
        with pytest.raises(ValueError, match="ambiguous"):
            solve_captcha_deterministic("12 / 3 -")
        with pytest.raises(ValueError, match="ambiguous"):
            solve_captcha_deterministic("12 - 3 /")

    def test_repeated_same_symbol_is_not_ambiguous(self):
        """§F.3.3: repetition of ONE operator meaning is not ambiguity —
        deduplication is by meaning, not occurrence count."""
        assert solve_captcha_deterministic("12 + 3 +") == "15.00"

    def test_subtracted_from_operand_order(self):
        """§F.3.2 latent-defect fix: 'X subtracted from Y' = Y - X."""
        assert solve_captcha_deterministic("What is 3 subtracted from 12?") == "9.00"

    def test_slows_by_maps_to_subtraction(self):
        """§F.3.1: the one grounded semantic phrase, from the platform's own
        worked example."""
        assert solve_captcha_deterministic("swims at 20 and slows by 5") == "15.00"

    def test_more_than_two_numbers_raises(self):
        """§F.2 strict-two rule: silent first-two truncation was a guess."""
        with pytest.raises(ValueError, match="exactly two"):
            solve_captcha_deterministic("12 plus 3 plus 4")

    def test_fewer_than_two_numbers_raises(self):
        with pytest.raises(ValueError, match="exactly two"):
            solve_captcha_deterministic("12 plus nothing")

    def test_unknown_operator_still_raises(self):
        with pytest.raises(ValueError, match="operator"):
            solve_captcha_deterministic("combine 12 and 3")

    def test_operator_word_requires_word_boundary(self):
        """§F.3.1: the prior substring scan matched 'add' inside 'paddle';
        \\b-anchored matching must not."""
        with pytest.raises(ValueError, match="operator"):
            solve_captcha_deterministic("the paddle count is 12 and 3")

    def test_collapsed_vocabulary_has_no_collisions(self):
        """§F.2: the doubled-letter fallback is only sound if no two
        vocabulary words share a collapsed form."""
        collapsed = [
            _collapse_letter_runs(word) for word in _WORD_NUMBER_VALUES
        ]
        assert len(set(collapsed)) == len(_WORD_NUMBER_VALUES)

    @pytest.mark.xfail(
        reason="Note F §F.5 residual: whitespace-shattered words ('tW eNtY') are "
        "out of scope v1 — the documented example breaks words only with symbols, "
        "never spaces. Handling them makes this xpass and forces this pin to update.",
        strict=True,
    )
    def test_whitespace_shattered_words(self):
        assert solve_captcha_deterministic(
            "A] lO^bSt-Er aT tW eNtY mE^tErS SlO/wS bY fIvE"
        ) == "15.00"


class TestCaptchaVerifier:
    def test_deterministic_captcha_success(self):
        kill_switch = KillSwitch()
        verifier = CaptchaVerifier(kill_switch)
        env = _envelope()
        outcome = verifier.verify(env, _challenge(), submit_fn=_confirmed_success)
        assert outcome is CaptchaOutcome.CONFIRMED_SUCCESS
        assert verifier.consecutive_confirmed_failures == 0
        assert not kill_switch.engaged

    def test_one_and_two_confirmed_failures_do_not_activate(self):
        kill_switch = KillSwitch()
        verifier = CaptchaVerifier(kill_switch)
        env = _envelope()
        verifier.verify(env, _challenge("c1"), submit_fn=_confirmed_failure)
        assert verifier.consecutive_confirmed_failures == 1
        assert not kill_switch.engaged
        verifier.verify(env, _challenge("c2"), submit_fn=_confirmed_failure)
        assert verifier.consecutive_confirmed_failures == 2
        assert not kill_switch.engaged

    def test_third_consecutive_confirmed_failure_activates(self):
        kill_switch = KillSwitch()
        verifier = CaptchaVerifier(kill_switch)
        env = _envelope()
        for i in range(CAPTCHA_LOCAL_FAILURE_THRESHOLD):
            verifier.verify(env, _challenge(f"c{i}"), submit_fn=_confirmed_failure)
        assert verifier.consecutive_confirmed_failures == 3
        assert kill_switch.engaged
        entry = kill_switch.activation_log[-1]
        assert entry.trigger == "captcha_suspension_risk"
        assert entry.mode == "automated"
        assert entry.extra["confirmed_failure_count"] == 3
        assert entry.extra["local_threshold"] == CAPTCHA_LOCAL_FAILURE_THRESHOLD
        assert entry.extra["platform_suspension_limit"] == PLATFORM_CAPTCHA_SUSPENSION_LIMIT
        assert entry.extra["action_id"] == env.action_id
        assert entry.extra["verification_code"] == "c2"

    def test_successful_verification_resets_the_counter(self):
        kill_switch = KillSwitch()
        verifier = CaptchaVerifier(kill_switch)
        env = _envelope()
        verifier.verify(env, _challenge("c1"), submit_fn=_confirmed_failure)
        verifier.verify(env, _challenge("c2"), submit_fn=_confirmed_failure)
        assert verifier.consecutive_confirmed_failures == 2
        verifier.verify(env, _challenge("c3"), submit_fn=_confirmed_success)
        assert verifier.consecutive_confirmed_failures == 0
        assert not kill_switch.engaged
        # And the count starts fresh from zero afterward — two more failures still
        # don't activate, proving the reset was real, not just cosmetic.
        verifier.verify(env, _challenge("c4"), submit_fn=_confirmed_failure)
        verifier.verify(env, _challenge("c5"), submit_fn=_confirmed_failure)
        assert verifier.consecutive_confirmed_failures == 2
        assert not kill_switch.engaged

    def test_ambiguous_outcome_does_not_increment_or_reset(self):
        kill_switch = KillSwitch()
        verifier = CaptchaVerifier(kill_switch)
        env = _envelope()
        verifier.verify(env, _challenge("c1"), submit_fn=_confirmed_failure)
        assert verifier.consecutive_confirmed_failures == 1
        outcome = verifier.verify(env, _challenge("c2"), submit_fn=_ambiguous)
        assert outcome is CaptchaOutcome.AMBIGUOUS
        # Still 1 — an ambiguous (timeout/unclear) response is neither a confirmed
        # failure nor evidence of success; it must not move the counter either way.
        assert verifier.consecutive_confirmed_failures == 1
        assert not kill_switch.engaged

    def test_operator_only_clearance_after_activation(self):
        kill_switch = KillSwitch()
        verifier = CaptchaVerifier(kill_switch)
        env = _envelope()
        for i in range(CAPTCHA_LOCAL_FAILURE_THRESHOLD):
            verifier.verify(env, _challenge(f"c{i}"), submit_fn=_confirmed_failure)
        assert kill_switch.engaged
        with pytest.raises(KillSwitchEngaged):
            kill_switch.check_write()
        kill_switch.clear(operator="lamont", detail="reviewed captcha failures")
        kill_switch.check_write()  # no raise now

    def test_captcha_activation_stays_outside_the_violation_trace(self):
        """
        Implementation Note B is explicit: this is an operational condition, not a
        Pi Script violation. There is no entity field, no resolver call, and no
        moltbook.pi constraint involved anywhere in CaptchaVerifier — the only
        artifact produced is a KillSwitchActivation, the same operational-audit
        shape §7 already established for the other automated triggers.
        """
        kill_switch = KillSwitch()
        verifier = CaptchaVerifier(kill_switch)
        env = _envelope()
        for i in range(CAPTCHA_LOCAL_FAILURE_THRESHOLD):
            verifier.verify(env, _challenge(f"c{i}"), submit_fn=_confirmed_failure)
        entry = kill_switch.activation_log[-1]
        assert entry.trigger == "captcha_suspension_risk"
        assert entry.mode == "automated"
        # Structural guard: nothing about this activation is a governance violation
        # object — it's a KillSwitchActivation, not an entity_state/resolver trace.
        assert not hasattr(entry, "entity_state")
        assert not hasattr(entry, "on_violation")

    def test_attempt_binds_action_and_verification_code_identifiers(self):
        """Note E: verification_code replaced challenge_id contract-wide — the
        attempt record, the audit extra, and the submit call all key on it."""
        kill_switch = KillSwitch()
        verifier = CaptchaVerifier(kill_switch)
        env = _envelope()
        submitted = {}
        def _capture_submit(verification_code, answer):
            submitted["code"] = verification_code
            return CaptchaOutcome.CONFIRMED_SUCCESS, {"success": True}
        verifier.verify(env, _challenge("c1"), submit_fn=_capture_submit)
        record = verifier.log[-1]
        assert record.action_id == env.action_id
        assert record.approval_trace_id == env.approval_trace_id
        assert record.verification_code == "c1"
        assert submitted["code"] == "c1"  # the submit seam received the same key


def _captcha_transport(submit_fn, *, request_fn=None, kill_switch=None):
    """A transport with the Note E captcha surface fully configured (both pieces —
    the fail-closed invariant allows nothing in between)."""
    kill_switch = kill_switch or KillSwitch()
    return MoltbookHTTPTransport(
        "key",
        request_fn=request_fn or (lambda m, p, b, h: HTTPResponse(200, _challenge_write_body())),
        live_config_version=CONFIG_V1,
        kill_switch=kill_switch,
        captcha_verifier=CaptchaVerifier(kill_switch),
        submit_captcha_fn=submit_fn,
    )


class TestNoteEFailClosedConfiguration:
    def test_full_captcha_configuration_accepted(self):
        kill_switch = KillSwitch()
        MoltbookHTTPTransport(
            "key", live_config_version=CONFIG_V1, kill_switch=kill_switch,
            captcha_verifier=CaptchaVerifier(kill_switch),
            submit_captcha_fn=_confirmed_success,
        )  # no raise

    def test_no_captcha_configuration_accepted(self):
        MoltbookHTTPTransport("key", live_config_version=CONFIG_V1)  # no raise

    def test_verifier_without_submit_rejected_at_construction(self):
        kill_switch = KillSwitch()
        with pytest.raises(ValueError, match="partial captcha configuration"):
            MoltbookHTTPTransport(
                "key", live_config_version=CONFIG_V1, kill_switch=kill_switch,
                captcha_verifier=CaptchaVerifier(kill_switch),
            )

    def test_submit_without_verifier_rejected_at_construction(self):
        with pytest.raises(ValueError, match="partial captcha configuration"):
            MoltbookHTTPTransport(
                "key", live_config_version=CONFIG_V1,
                submit_captcha_fn=_confirmed_success,
            )

    def test_fetch_captcha_challenge_is_retired(self):
        """Note E: no standalone issuance endpoint exists, so no fetch seam does
        either — passing the old kwarg fails loudly rather than being ignored."""
        with pytest.raises(TypeError):
            MoltbookHTTPTransport(
                "key", live_config_version=CONFIG_V1,
                fetch_captcha_challenge=lambda: _challenge(),
            )


class TestNoteEVerificationBlockParsing:
    def test_fixture_write_response_parses_to_challenge(self):
        """The checked-in fixture IS the captured protocol shape — parsing it, not
        an assumed structure, is the whole point (Note E)."""
        challenge = parse_verification_block(CAPTCHA_FIXTURE["write_response_with_challenge"])
        assert challenge is not None
        assert challenge.verification_code == "moltbook_verify_SYNTHETIC0000000000000000"
        assert "pLuS" in challenge.prompt
        assert challenge.expires_at == datetime(2026, 7, 21, 12, 5, 0, tzinfo=timezone.utc)

    def test_trusted_fixture_response_parses_to_none(self):
        """Absence of the verification block is the documented trusted-agent signal —
        a positive fact, returned as None, never an error."""
        assert parse_verification_block(CAPTCHA_FIXTURE["write_response_trusted_no_challenge"]) is None

    def test_malformed_verification_block_raises_loudly(self):
        """Note E stop condition: a block that exists but contradicts the captured
        shape means re-fixture, not guess — it must never parse permissively."""
        body = {"post": {"id": "x", "verification": {"verification_code": "only-this"}}}
        with pytest.raises(ValueError, match="does not match"):
            parse_verification_block(body)

    def test_non_iso_expires_at_raises_loudly(self):
        body = {"post": {"verification": {
            "verification_code": "c", "challenge_text": "t", "expires_at": "five minutes from now",
        }}}
        with pytest.raises(ValueError, match="not ISO-8601"):
            parse_verification_block(body)


class TestNoteECaptchaFlow:
    def test_passed_verification_publishes_with_one_write_and_one_verify(self):
        write_calls, verify_calls = [], []
        def _request(method, path, body, headers):
            write_calls.append(path)
            return HTTPResponse(200, _challenge_write_body())
        def _submit(code, answer):
            verify_calls.append((code, answer))
            return CaptchaOutcome.CONFIRMED_SUCCESS, copy.deepcopy(CAPTCHA_FIXTURE["verify_response_success"])
        transport = _captcha_transport(_submit, request_fn=_request)
        result = transport.send(_envelope())
        assert result.outcome is TransportOutcome.SUCCESS
        assert result.publication_status is PublicationStatus.PUBLISHED
        assert result.verification_status is VerificationStatus.PASSED
        assert len(write_calls) == 1 and len(verify_calls) == 1
        # The solver solved the fixture's synthetic obfuscated prompt (12 plus 3).
        assert verify_calls[0][1] == "15.00"

    def test_confirmed_failure_classifies_not_published_and_counts(self):
        """Note E: the write already happened — a failed verification is a classified
        fact (NOT_PUBLISHED/FAILED) on the result, not an exception."""
        transport = _captcha_transport(_confirmed_failure)
        result = transport.send(_envelope())
        assert result.outcome is TransportOutcome.SUCCESS  # transmission DID succeed
        assert result.publication_status is PublicationStatus.NOT_PUBLISHED
        assert result.verification_status is VerificationStatus.FAILED
        assert transport.captcha_verifier.consecutive_confirmed_failures == 1

    def test_third_consecutive_failure_fires_trigger_and_blocks_next_send(self):
        kill_switch = KillSwitch()
        transport = _captcha_transport(_confirmed_failure, kill_switch=kill_switch)
        for _ in range(CAPTCHA_LOCAL_FAILURE_THRESHOLD):
            result = transport.send(_envelope())
            assert result.verification_status is VerificationStatus.FAILED
        entry = kill_switch.activation_log[-1]
        assert entry.trigger == "captcha_suspension_risk"
        assert entry.extra["verification_code"] == "moltbook_verify_SYNTHETIC0000000000000000"
        # A wholly separate write attempt is now blocked at the kill-switch boundary.
        with pytest.raises(KillSwitchEngaged):
            transport.send(_envelope())

    def test_ambiguous_verification_stays_pending_uncounted_unretried(self):
        verify_calls = []
        def _submit(code, answer):
            verify_calls.append(code)
            return CaptchaOutcome.AMBIGUOUS, None
        transport = _captcha_transport(_submit)
        result = transport.send(_envelope())
        assert result.publication_status is PublicationStatus.PENDING_VERIFICATION
        assert result.verification_status is VerificationStatus.REQUIRED
        assert transport.captcha_verifier.consecutive_confirmed_failures == 0
        assert len(verify_calls) == 1  # exactly one attempt — never retried

    def test_trusted_agent_path_is_first_class(self):
        """No verification block → NOT_REQUIRED + PUBLISHED directly off the write,
        with ZERO verify calls (Note E: a first-class case, not a degenerate one)."""
        verify_calls = []
        def _submit(code, answer):
            verify_calls.append(code)
            return CaptchaOutcome.CONFIRMED_SUCCESS, {}
        transport = _captcha_transport(
            _submit,
            request_fn=lambda m, p, b, h: HTTPResponse(
                200, copy.deepcopy(CAPTCHA_FIXTURE["write_response_trusted_no_challenge"])),
        )
        result = transport.send(_envelope())
        assert result.publication_status is PublicationStatus.PUBLISHED
        assert result.verification_status is VerificationStatus.NOT_REQUIRED
        assert verify_calls == []

    def test_unconfigured_captcha_leaves_content_pending_reported_exactly(self):
        """Note E point 7: unconfigured is legal — a pending write is reported as
        exactly that, never guessed at, never silently dropped."""
        transport = MoltbookHTTPTransport(
            "key", live_config_version=CONFIG_V1,
            request_fn=lambda m, p, b, h: HTTPResponse(200, _challenge_write_body()),
        )
        result = transport.send(_envelope())
        assert result.outcome is TransportOutcome.SUCCESS
        assert result.publication_status is PublicationStatus.PENDING_VERIFICATION
        assert result.verification_status is VerificationStatus.REQUIRED

    def test_expired_challenge_honors_platform_expires_at_only(self):
        """The fixture's captured expires_at (2026-07-21T12:05Z) is in the past —
        EXPIRED/NOT_PUBLISHED with NO submit call and NO counter movement. Proves
        expiry comes from the platform value, not any constant."""
        verify_calls = []
        def _submit(code, answer):
            verify_calls.append(code)
            return CaptchaOutcome.CONFIRMED_SUCCESS, {}
        transport = _captcha_transport(
            _submit,
            request_fn=lambda m, p, b, h: HTTPResponse(
                200, copy.deepcopy(CAPTCHA_FIXTURE["write_response_with_challenge"])),
        )
        result = transport.send(_envelope())
        assert result.publication_status is PublicationStatus.NOT_PUBLISHED
        assert result.verification_status is VerificationStatus.EXPIRED
        assert verify_calls == []  # documented-to-fail call never made
        assert transport.captcha_verifier.consecutive_confirmed_failures == 0

    def test_non_default_expiry_window_flows_with_no_constant_interfering(self):
        """A submolt-style short window (well under 5 minutes) still verifies fine —
        nothing in the flow encodes either documented window."""
        transport = _captcha_transport(
            _confirmed_success,
            request_fn=lambda m, p, b, h: HTTPResponse(
                200, _challenge_write_body(expires_in_seconds=20)),
        )
        result = transport.send(_envelope())
        assert result.verification_status is VerificationStatus.PASSED

    def test_each_write_binds_its_own_verification_code_never_reused(self):
        """Two writes, two distinct platform-issued codes — each attempt record and
        submit call carries the code from ITS OWN write response (Note E binding)."""
        codes = iter(["moltbook_verify_AAA", "moltbook_verify_BBB"])
        submitted = []
        def _request(method, path, body, headers):
            return HTTPResponse(200, _challenge_write_body(verification_code=next(codes)))
        def _submit(code, answer):
            submitted.append(code)
            return CaptchaOutcome.CONFIRMED_SUCCESS, {}
        transport = _captcha_transport(_submit, request_fn=_request)
        transport.send(_envelope())
        transport.send(_envelope())
        assert submitted == ["moltbook_verify_AAA", "moltbook_verify_BBB"]
        recorded = [r.verification_code for r in transport.captcha_verifier.log]
        assert recorded == ["moltbook_verify_AAA", "moltbook_verify_BBB"]

    def test_statuses_are_none_where_no_content_was_created(self):
        """Publication/verification are questions only a created-content response
        raises — a failed transmission has neither (None, not fabricated)."""
        transport = MoltbookHTTPTransport(
            "key", request_fn=_fake_request(429), live_config_version=CONFIG_V1,
        )
        result = transport.send(_envelope())
        assert result.publication_status is None
        assert result.verification_status is None
        # And the Note E alias answers the transmission question by its note name.
        assert result.transmission_status is result.outcome

    def test_client_adapter_surfaces_statuses_additively(self):
        transport = MoltbookHTTPTransport(
            "key", live_config_version=CONFIG_V1,
            request_fn=lambda m, p, b, h: HTTPResponse(200, _challenge_write_body()),
        )
        client_transport = as_client_transport(transport, governance_config_version=CONFIG_V1)
        result = client_transport(action="post", content="hello", headers={})
        assert result["outcome"] == "success"
        assert result["publication_status"] == "pending_verification"
        assert result["verification_status"] == "required"

    def test_dry_run_simulated_statuses_are_labeled_simulated(self):
        """Note E mechanical decision: no network call → no platform to issue a
        challenge → the simulation mirrors the no-verification-block path, on the
        deliberately separate DryRunOutcome type."""
        dry = DryRunTransport(live_config_version=CONFIG_V1)
        outcome = dry.send(_envelope(action_id=make_dry_run_action_id()))
        assert outcome.simulated_publication_status is PublicationStatus.PUBLISHED
        assert outcome.simulated_verification_status is VerificationStatus.NOT_REQUIRED
