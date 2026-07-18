"""
test_moltbook_cadence_integrity.py — M7 CadenceIntegrity (first Longitudinal Constraint).

Covers docs/m7_cadence_integrity_ruling.md (LOCKED 2026-07-17, incl. the post-lock
grammar correction):
    - moltbook.pi: CadenceIntegrity IR shape (on_violation: escalate, in-grammar) and the
      MoltbookAgentProfile enforce block alongside the session constraints.
    - Resolver pair: deliberate violation (escalated — distinct from frozen, §7) and clean
      pass (running).
    - Detection (§4/§5): near-periodic positive fixture fires; irregular and
      frequent-but-irregular stay clean (frequency ≠ regularity); a recorded gap resets
      the consecutive run instead of being bridged.
    - Readiness gate (§2/§3): below 4 in-window intervals the constraint is NOT EVALUABLE
      (application-level gate, cadence_anomaly stays None) — never silently clean.
    - Persistence (§6): restart survival, duplicate-ingest idempotence, rolling-window
      aging (history never deleted), and restart-interleave determinism.
    - Enforcement (§7): the client-side pause (autonomous_posting_paused, distinct from
      frozen) is applied in the same step as resolution, persists across restarts, blocks
      autonomous sends only (human-authorized passes, gates still latch first), and clears
      only via explicit human reset — which never erases observation history.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pi_script.parser import parse_file
from pi_script.validator import PiValidator
from pi_script.resolver import resolve
from moltbook.cadence import (
    CadenceObservationStore,
    run_cadence_governance,
    MIN_READY_INTERVALS,
)
from moltbook.client import AutonomousPostingPaused, IdentityDriftBlocked, MoltbookClient

POLICY = Path(__file__).resolve().parents[1] / "moltbook" / "moltbook.pi"

BASE = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)

# §8 fixtures: five intervals each (six posts). Spread ≤ 2J = 6s fires; anything wider is clean.
PERIODIC = [180, 181, 179, 180, 182]           # the observed near-periodic pattern
IRREGULAR = [180, 500, 90, 260, 400]           # organic spacing
FREQUENT_IRREGULAR = [30, 90, 45, 120, 60]     # high frequency, no regularity


def _ir():
    tree, err = parse_file(str(POLICY))
    assert err is None, err
    ok, errors, ir = PiValidator(tree).validate()
    assert ok, errors
    return ir


def _store(tmp_path, name="cadence.json", agent="continuum_gov") -> CadenceObservationStore:
    return CadenceObservationStore(tmp_path / name, agent)


def _ingest_seq(store, intervals, start=BASE, prefix="p"):
    """Ingest a post at `start`, then one after each interval in `intervals`."""
    ts = start
    store.ingest(f"{prefix}0", ts)
    for i, delta in enumerate(intervals, start=1):
        ts = ts + timedelta(seconds=delta)
        store.ingest(f"{prefix}{i}", ts)
    return ts


def _profile_snapshot(anomaly: bool) -> dict:
    return {
        "trigger_type": "event",
        "entity": "MoltbookAgentProfile",
        "entity_state": {
            "agent_id": "continuum_gov",
            "cadence_observation_ready": True,
            "cadence_anomaly": anomaly,
            "observed_interval_count": 5,
            "common_period_seconds": 180,
            "max_jitter_seconds": 2,
            "rolling_window_start": "2026-07-03T12:00:00+00:00",
            "rolling_window_end": "2026-07-10T12:00:00+00:00",
        },
        "response_history": [],
    }


# ── Policy ───────────────────────────────────────────────────────────────────

class TestPolicy:
    def test_cadence_integrity_ir_shape(self):
        c = _ir()["constraints"]["CadenceIntegrity"]
        assert c["priority"] == "high"
        assert c["rule"] == {
            "kind": "equality_rule",
            "ref": "MoltbookAgentProfile.cadence_anomaly",
            "value": False,
        }
        # Post-lock grammar correction: escalate in-grammar; the §7 pause is
        # client-side profile state applied by moltbook/cadence.py.
        assert c["on_violation"] == ["escalate"]

    def test_agent_profile_enforce_block(self):
        assert _ir()["enforce"] == {
            "MoltbookSession": ["CredentialIntegrity", "LinkRestriction", "IdentityIntegrity"],
            "MoltbookAgentProfile": ["CadenceIntegrity", "CitationClusterIntegrity"],
        }


# ── Resolver: required test pair ─────────────────────────────────────────────

class TestConstraint:
    def test_deliberate_violation_escalates_not_freezes(self):
        trace, _, code = resolve(_ir(), _profile_snapshot(anomaly=True))
        assert code == 1
        # §7: distinct from frozen — the session is not frozen, autonomy is paused
        # client-side and the violation is escalated for human review.
        assert trace["system_state"] == "escalated"
        result = next(c for c in trace["constraints"] if c["name"] == "CadenceIntegrity")
        assert result["status"] == "violated"
        assert result["action"] == "escalate"

    def test_clean_pass_stays_running(self):
        trace, _, code = resolve(_ir(), _profile_snapshot(anomaly=False))
        assert code == 0
        assert trace["system_state"] == "running"


# ── Detection (§4/§5) ────────────────────────────────────────────────────────

class TestDetection:
    def test_near_periodic_pattern_fires(self, tmp_path):
        store = _store(tmp_path)
        _ingest_seq(store, PERIODIC)
        profile = store.profile_state()
        assert profile["cadence_observation_ready"] is True
        assert profile["cadence_anomaly"] is True
        assert profile["common_period_seconds"] == 180
        assert 0 <= profile["max_jitter_seconds"] <= 3

    def test_irregular_spacing_stays_clean(self, tmp_path):
        store = _store(tmp_path)
        _ingest_seq(store, IRREGULAR)
        profile = store.profile_state()
        assert profile["cadence_observation_ready"] is True
        assert profile["cadence_anomaly"] is False

    def test_frequent_but_irregular_stays_clean(self, tmp_path):
        # §8: frequency and regularity are decoupled — posting often is not the pattern.
        store = _store(tmp_path)
        _ingest_seq(store, FREQUENT_IRREGULAR)
        assert store.profile_state()["cadence_anomaly"] is False

    def test_recorded_gap_resets_the_run(self, tmp_path):
        # §4: a detector-recorded gap is never bridged — it breaks the consecutive run,
        # so five periodic intervals with a gap in the middle cannot form the N=5 run.
        store = _store(tmp_path)
        end = _ingest_seq(store, PERIODIC)
        store.record_gap(BASE + timedelta(seconds=180 + 181 + 90))  # inside interval 3
        profile = store.profile_state()
        assert profile["observed_interval_count"] == 4  # the gap-spanning interval is out
        assert profile["cadence_anomaly"] is False
        assert end > BASE  # fixture sanity


# ── Readiness gate (§2/§3): NOT EVALUABLE, never silently clean ───────────────

class TestReadinessGate:
    def test_insufficient_history_is_not_evaluable(self, tmp_path):
        store = _store(tmp_path)
        _ingest_seq(store, [180, 181])  # 3 posts = 2 intervals < 4 required
        profile = store.profile_state()
        assert profile["cadence_observation_ready"] is False
        # §3: explicit unset — never defaulted to false. Insufficient data ≠ compliant.
        assert profile["cadence_anomaly"] is None

        result = run_cadence_governance(_ir(), store)
        assert result.evaluated is False
        assert result.trace is None
        assert "NOT EVALUABLE" in result.rendered
        assert f"2/{MIN_READY_INTERVALS} required intervals" in result.rendered
        assert store.paused is False

    def test_readiness_boundary_four_intervals_evaluates(self, tmp_path):
        store = _store(tmp_path)
        _ingest_seq(store, [180, 500, 90, 260])  # exactly 5 posts / 4 intervals
        assert store.profile_state()["cadence_observation_ready"] is True
        result = run_cadence_governance(_ir(), store)
        assert result.evaluated is True
        assert result.exit_code == 0


# ── Governance end-to-end (§7) ───────────────────────────────────────────────

class TestGovernance:
    def test_violation_escalates_and_pauses_in_one_step(self, tmp_path):
        # §7 (post-lock correction): emitting escalate without applying the client-side
        # pause does not satisfy the ruling — both must come out of the same pass.
        store = _store(tmp_path)
        _ingest_seq(store, PERIODIC)
        result = run_cadence_governance(_ir(), store)
        assert result.evaluated is True
        assert result.exit_code == 1
        assert result.trace["system_state"] == "escalated"
        assert result.trace["final_action"] == "escalate"
        assert result.pause_applied is True
        assert store.paused is True

    def test_clean_profile_neither_escalates_nor_pauses(self, tmp_path):
        store = _store(tmp_path)
        _ingest_seq(store, IRREGULAR)
        result = run_cadence_governance(_ir(), store)
        assert result.exit_code == 0
        assert result.trace["system_state"] == "running"
        assert result.pause_applied is False
        assert store.paused is False


# ── Persistence (§6) ─────────────────────────────────────────────────────────

class TestPersistence:
    def test_history_and_profile_survive_restart(self, tmp_path):
        store = _store(tmp_path)
        _ingest_seq(store, PERIODIC)
        before = store.profile_state()
        reopened = _store(tmp_path)  # same path = simulated process restart
        assert reopened.observation_count() == 6
        assert reopened.profile_state() == before

    def test_duplicate_ingestion_is_idempotent(self, tmp_path):
        store = _store(tmp_path)
        _ingest_seq(store, PERIODIC)
        before = store.profile_state()
        assert store.ingest("p3", BASE + timedelta(days=2)) is False  # even a new ts
        assert store.observation_count() == 6
        assert store.profile_state() == before

    def test_old_pattern_ages_out_of_window_but_is_never_deleted(self, tmp_path):
        store = _store(tmp_path)
        # A near-periodic run whose newest post is >7 days before the current window end.
        _ingest_seq(store, PERIODIC, start=BASE - timedelta(days=30), prefix="old")
        _ingest_seq(store, IRREGULAR, start=BASE, prefix="new")
        profile = store.profile_state()
        assert profile["cadence_observation_ready"] is True
        assert profile["cadence_anomaly"] is False       # aged out (§6)
        assert profile["observed_interval_count"] == 5   # only the in-window intervals
        assert store.observation_count() == 12           # nothing deleted (§6)

    def test_restart_interleave_determinism(self, tmp_path):
        # §6/§8: A,B,C and A,restart,B,restart,C must produce identical profile state.
        straight = _store(tmp_path, name="straight.json")
        _ingest_seq(straight, PERIODIC)

        interleaved_path = tmp_path / "interleaved.json"
        ts = BASE
        CadenceObservationStore(interleaved_path, "continuum_gov").ingest("p0", ts)
        for i, delta in enumerate(PERIODIC, start=1):
            ts = ts + timedelta(seconds=delta)
            # A fresh instance per observation == a restart between every ingest.
            CadenceObservationStore(interleaved_path, "continuum_gov").ingest(f"p{i}", ts)

        final = CadenceObservationStore(interleaved_path, "continuum_gov")
        assert final.profile_state() == straight.profile_state()


# ── Pause semantics (§7) ─────────────────────────────────────────────────────

class TestPause:
    def _paused_store(self, tmp_path) -> CadenceObservationStore:
        store = _store(tmp_path)
        _ingest_seq(store, PERIODIC)
        assert run_cadence_governance(_ir(), store).pause_applied is True
        return store

    def _client(self, store, **kw) -> MoltbookClient:
        kw.setdefault("api_key", "moltbook_sk_dummy_not_in_content")
        kw.setdefault("declared_handle", "continuum_gov")
        kw.setdefault("transport", lambda **k: {"ok": True})
        return MoltbookClient(cadence_store=store, **kw)

    def test_pause_survives_restart(self, tmp_path):
        self._paused_store(tmp_path)
        assert _store(tmp_path).paused is True

    def test_autonomous_send_blocked_while_paused(self, tmp_path):
        client = self._client(self._paused_store(tmp_path))
        for action in ("post", "comment", "dm"):
            with pytest.raises(AutonomousPostingPaused):
                client.send("clean scheduled content", action=action)

    def test_human_authorized_send_passes_while_paused(self, tmp_path):
        client = self._client(self._paused_store(tmp_path))
        assert client.send("human-approved notice", human_authorized=True) == {"ok": True}

    def test_gates_still_latch_before_the_pause_check(self, tmp_path):
        # A5 inheritance check: the pause is not a scan — a tainted attempt made while
        # paused still runs every gate and latches, nothing is silently dropped.
        client = self._client(self._paused_store(tmp_path))
        with pytest.raises(IdentityDriftBlocked):
            client.send("call me nightshade")
        assert client.identity_drift is True

    def test_read_only_observation_continues_while_paused(self, tmp_path):
        store = self._paused_store(tmp_path)
        assert store.ingest("during_pause", BASE + timedelta(days=1)) is True
        assert store.profile_state()["cadence_observation_ready"] is True

    def test_human_reset_clears_pause_but_keeps_history(self, tmp_path):
        store = self._paused_store(tmp_path)
        store.human_reset()
        assert store.paused is False
        assert store.observation_count() == 6  # §7: history is never erased
        # The reviewed run is cleared; recompute must not immediately re-latch it.
        result = run_cadence_governance(_ir(), store)
        assert result.exit_code == 0
        assert store.paused is False

    def test_new_pattern_after_reset_fires_again(self, tmp_path):
        # The clearance watermark forgives the REVIEWED run only — resuming the
        # metronome after reset is a fresh violation.
        store = self._paused_store(tmp_path)
        store.human_reset()
        resume = BASE + timedelta(seconds=sum(PERIODIC))
        ts = resume
        for i, delta in enumerate([180, 180, 181, 179, 180], start=1):
            ts = ts + timedelta(seconds=delta)
            store.ingest(f"resumed{i}", ts)
        result = run_cadence_governance(_ir(), store)
        assert result.exit_code == 1
        assert result.pause_applied is True
        assert store.paused is True


# ── Fail-closed construction (mirrors addendum A1's stance) ──────────────────

class TestFailClosedConstruction:
    def test_empty_agent_id_refuses_to_construct(self, tmp_path):
        with pytest.raises(ValueError):
            CadenceObservationStore(tmp_path / "cadence.json", "   ")

    def test_agent_id_mismatch_on_existing_store_refuses(self, tmp_path):
        _store(tmp_path)
        with pytest.raises(ValueError):
            CadenceObservationStore(tmp_path / "cadence.json", "someone_else")
