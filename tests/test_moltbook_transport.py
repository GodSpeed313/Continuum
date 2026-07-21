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

from datetime import datetime, timedelta, timezone

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
    KillSwitch,
    KillSwitchEngaged,
    MoltbookHTTPTransport,
    OperationalFreeze,
    ReconciliationOutcome,
    RetryCategory,
    TransportOutcome,
    TransportResult,
    as_client_transport,
    canonical_payload_hash,
    describe_retry_category,
    make_dry_run_action_id,
    reconcile,
    resolve_ambiguous_write,
    solve_captcha_deterministic,
    validate_envelope,
)

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


def _fake_request(status: int, body: dict | None = None):
    """A canned request_fn: ignores its args, always returns (status, body)."""
    def _fn(method, path, json_body, headers):
        return status, (body if body is not None else {})
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
            return 200, {"id": "post123"}
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
            return 200, {}
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
            return 200, {}
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
            return 200, {}
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
            return 503, {}
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
            return 429, {"error": "rate_limited"}
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
            return 200, {"id": "p1"}
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
            return 200, {"id": "c1"}
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
            return 200, {"id": "c1"}
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


# ───────────────── Implementation Note B: captcha verification ─────────────────

CAPTCHA_PROMPT = "What is 12 plus 3.00?"


def _challenge(challenge_id: str = "chal-1") -> CaptchaChallenge:
    return CaptchaChallenge(
        challenge_id=challenge_id, prompt=CAPTCHA_PROMPT,
        expires_at=BASE + timedelta(minutes=5),
    )


def _confirmed_success(_challenge_id, _answer):
    return CaptchaOutcome.CONFIRMED_SUCCESS, {"success": True}


def _confirmed_failure(_challenge_id, _answer):
    return CaptchaOutcome.CONFIRMED_FAILURE, {"success": False, "error": "wrong answer"}


def _ambiguous(_challenge_id, _answer):
    return CaptchaOutcome.AMBIGUOUS, None


class TestCaptchaSolver:
    def test_deterministic_solve(self):
        assert solve_captcha_deterministic("What is 12 plus 3.00?") == "15.00"
        assert solve_captcha_deterministic("12 plus 3.00") == solve_captcha_deterministic("12 plus 3.00")

    def test_thresholds_are_distinct_and_documented(self):
        """Continuum's margin must stay strictly under Moltbook's documented limit —
        the whole point of Implementation Note B is that 3 is conservative relative
        to a platform-grounded 10, not an independently invented number."""
        assert CAPTCHA_LOCAL_FAILURE_THRESHOLD == 3
        assert PLATFORM_CAPTCHA_SUSPENSION_LIMIT == 10
        assert CAPTCHA_LOCAL_FAILURE_THRESHOLD < PLATFORM_CAPTCHA_SUSPENSION_LIMIT


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
        assert entry.extra["challenge_id"] == "c2"

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

    def test_attempt_binds_action_and_challenge_identifiers(self):
        kill_switch = KillSwitch()
        verifier = CaptchaVerifier(kill_switch)
        env = _envelope()
        verifier.verify(env, _challenge("c1"), submit_fn=_confirmed_success)
        record = verifier.log[-1]
        assert record.action_id == env.action_id
        assert record.approval_trace_id == env.approval_trace_id
        assert record.challenge_id == "c1"


class TestCaptchaTransportIntegration:
    def test_send_blocked_on_confirmed_captcha_failure(self):
        from moltbook.transport import CaptchaVerificationFailed
        kill_switch = KillSwitch()
        transport = MoltbookHTTPTransport(
            "key", request_fn=_fake_request(200), live_config_version=CONFIG_V1,
            kill_switch=kill_switch,
            captcha_verifier=CaptchaVerifier(kill_switch),
            fetch_captcha_challenge=lambda: _challenge(),
            submit_captcha_fn=_confirmed_failure,
        )
        with pytest.raises(CaptchaVerificationFailed):
            transport.send(_envelope())

    def test_send_blocked_on_ambiguous_captcha_response(self):
        from moltbook.transport import CaptchaVerificationAmbiguous
        kill_switch = KillSwitch()
        transport = MoltbookHTTPTransport(
            "key", request_fn=_fake_request(200), live_config_version=CONFIG_V1,
            kill_switch=kill_switch,
            captcha_verifier=CaptchaVerifier(kill_switch),
            fetch_captcha_challenge=lambda: _challenge(),
            submit_captcha_fn=_ambiguous,
        )
        with pytest.raises(CaptchaVerificationAmbiguous):
            transport.send(_envelope())
        assert not kill_switch.engaged

    def test_send_proceeds_on_confirmed_captcha_success(self):
        captured = {}
        def _capture(method, path, body, headers):
            captured["called"] = True
            return 200, {"id": "p1"}
        kill_switch = KillSwitch()
        transport = MoltbookHTTPTransport(
            "key", request_fn=_capture, live_config_version=CONFIG_V1,
            kill_switch=kill_switch,
            captcha_verifier=CaptchaVerifier(kill_switch),
            fetch_captcha_challenge=lambda: _challenge(),
            submit_captcha_fn=_confirmed_success,
        )
        result = transport.send(_envelope())
        assert result.outcome is TransportOutcome.SUCCESS
        assert captured.get("called") is True

    def test_third_consecutive_failure_blocks_subsequent_sends_via_kill_switch(self):
        from moltbook.transport import CaptchaVerificationFailed
        kill_switch = KillSwitch()
        captcha_verifier = CaptchaVerifier(kill_switch)
        transport = MoltbookHTTPTransport(
            "key", request_fn=_fake_request(200), live_config_version=CONFIG_V1,
            kill_switch=kill_switch,
            captcha_verifier=captcha_verifier,
            fetch_captcha_challenge=lambda: _challenge(),
            submit_captcha_fn=_confirmed_failure,
        )
        for _ in range(CAPTCHA_LOCAL_FAILURE_THRESHOLD):
            with pytest.raises(CaptchaVerificationFailed):
                transport.send(_envelope())
        # The kill switch is now engaged (3rd confirmed failure) — a wholly separate
        # write attempt is blocked at the kill-switch boundary, not just captcha.
        with pytest.raises(KillSwitchEngaged):
            transport.send(_envelope())
