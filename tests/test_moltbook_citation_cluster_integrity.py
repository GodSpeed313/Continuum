"""
test_moltbook_citation_cluster_integrity.py — M7 CitationClusterIntegrity (second
Longitudinal Constraint).

Covers docs/m7_citation_cluster_integrity_ruling.md (LOCKED 2026-07-18):
    - moltbook.pi: CitationClusterIntegrity IR shape (on_violation: escalate, in-grammar)
      and the extended MoltbookAgentProfile enforce block.
    - Resolver pair: deliberate violation (escalated — distinct from frozen, §7) and clean
      pass (running); the sibling CadenceIntegrity suspends (never a false clean) when a
      citation-only snapshot is submitted.
    - Detection (§4): the closed-cluster positive fixture fires; diffuse outward citation,
      a two-account mutual pair, and a reciprocal-but-well-connected cluster stay clean
      (shape, not magnitude — each ingredient alone is not the pattern).
    - Directional-graph logic (§1/§4/§8): guilt-by-association (external cluster citing
      M7, zero M7-outbound) can NEVER set the flag; one-directional citation stays clean
      in both directions (the §9 named gap, pinned as correct scope, not a bug).
    - Parameter grounding (§5): every threshold is undefined in production — with no
      injected parameters the constraint is NOT EVALUABLE and cannot fire. Tests inject
      SYNTHETIC parameters to prove the mechanism; those values assert nothing about
      Moltbook.
    - Readiness gate (§3): below the outbound-edge floor the constraint is NOT EVALUABLE
      (citation_cluster_flag stays None) — never silently clean.
    - Persistence (§6): restart survival, duplicate-ingest idempotence, rolling-window
      aging (history never deleted), and restart-interleave determinism.
    - Enforcement (§7): the client-side pause is applied in the same step as resolution,
      persists across restarts, blocks autonomous sends only (human-authorized passes,
      gates still latch first), and clears only via explicit human reset — which never
      erases edge history and forgives only the reviewed cluster.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pi_script.parser import parse_file
from pi_script.validator import PiValidator
from pi_script.resolver import resolve
from moltbook.citation import (
    CitationClusterParameters,
    CitationEdgeStore,
    run_citation_governance,
)
from moltbook.client import AutonomousPostingPaused, IdentityDriftBlocked, MoltbookClient

POLICY = Path(__file__).resolve().parents[1] / "moltbook" / "moltbook.pi"

BASE = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)

AGENT = "continuum_gov"

# §5/§8: SYNTHETIC parameters, injected by tests only. They exist to prove the detection
# MECHANISM fires and stays quiet in the right shapes — they are NOT grounded values and
# assert nothing about Moltbook. Production passes params=None until the §5/§10
# grounding amendment; moltbook/citation.py ships no parameter instance at all.
TEST_PARAMS = CitationClusterParameters(
    min_outbound_edges=4,
    min_cluster_size=3,
    min_reciprocal_edges=3,
    max_external_degree_ratio=0.5,
)


def _ir():
    tree, err = parse_file(str(POLICY))
    assert err is None, err
    ok, errors, ir = PiValidator(tree).validate()
    assert ok, errors
    return ir


def _store(tmp_path, name="citations.json", agent=AGENT) -> CitationEdgeStore:
    return CitationEdgeStore(tmp_path / name, agent)


def _ingest_all(store, posts, start=BASE):
    """Ingest (post_id, source, cited) records one hour apart, starting at `start`."""
    for i, (pid, source, cited) in enumerate(posts):
        store.ingest(pid, source, cited, start + timedelta(hours=i))
    return start + timedelta(hours=len(posts) - 1)


# The §8 positive fixture: a closed three-account structure (the shape the recon's
# pepper_pots/corra/pyclaw-successor cluster motivates, §5) that the governed agent
# SUSTAINS with its own outbound citations — 4 outbound edges into the cluster, every
# pair reciprocal, no edges leaving it.
CLOSED_CLUSTER = [
    ("p1", AGENT, ["pepper_bot"]),
    ("p2", AGENT, ["corra_bot"]),
    ("p3", AGENT, ["pepper_bot"]),
    ("p4", AGENT, ["corra_bot"]),
    ("x1", "pepper_bot", [AGENT, "corra_bot"]),
    ("x2", "corra_bot", [AGENT, "pepper_bot"]),
]

# Diffuse outward citation: same outbound volume, no reciprocity — Finding 1's vivioo
# case (citing another agent's work, isolated and non-reciprocal) is legitimate (§4).
DIFFUSE = [
    ("p1", AGENT, ["vivioo"]),
    ("p2", AGENT, ["bytes"]),
    ("p3", AGENT, ["diviner"]),
    ("p4", AGENT, ["starfish"]),
    ("p5", AGENT, ["vina"]),
]


# ── Policy ───────────────────────────────────────────────────────────────────

class TestPolicy:
    def test_citation_cluster_integrity_ir_shape(self):
        c = _ir()["constraints"]["CitationClusterIntegrity"]
        assert c["priority"] == "high"
        assert c["rule"] == {
            "kind": "equality_rule",
            "ref": "MoltbookAgentProfile.citation_cluster_flag",
            "value": False,
        }
        # Same grammar mapping as CadenceIntegrity: escalate in-grammar; the §7
        # pause is client-side profile state applied by moltbook/citation.py.
        assert c["on_violation"] == ["escalate"]

    def test_agent_profile_enforce_block_extended(self):
        assert _ir()["enforce"] == {
            "MoltbookSession": ["CredentialIntegrity", "LinkRestriction", "IdentityIntegrity"],
            "MoltbookAgentProfile": ["CadenceIntegrity", "CitationClusterIntegrity"],
        }


# ── Resolver: required test pair ─────────────────────────────────────────────

def _citation_snapshot(flag: bool) -> dict:
    return {
        "trigger_type": "event",
        "entity": "MoltbookAgentProfile",
        "entity_state": {
            "agent_id": AGENT,
            "citation_observation_ready": True,
            "citation_cluster_flag": flag,
            "cluster_size": 3,
            "m7_outbound_edge_count": 4,
            "reciprocal_edge_count": 3,
            "external_edge_count": 0,
            "rolling_window_start": "2026-07-03T12:00:00+00:00",
            "rolling_window_end": "2026-07-10T12:00:00+00:00",
        },
        "response_history": [],
    }


class TestConstraint:
    def test_deliberate_violation_escalates_not_freezes(self):
        trace, _, code = resolve(_ir(), _citation_snapshot(flag=True))
        assert code == 1
        # §7: distinct from frozen — autonomy is paused client-side and the
        # violation is escalated for human review.
        assert trace["system_state"] == "escalated"
        result = next(c for c in trace["constraints"] if c["name"] == "CitationClusterIntegrity")
        assert result["status"] == "violated"
        assert result["action"] == "escalate"

    def test_clean_pass_stays_running(self):
        trace, _, code = resolve(_ir(), _citation_snapshot(flag=False))
        assert code == 0
        assert trace["system_state"] == "running"

    def test_sibling_cadence_constraint_suspends_not_cleans(self):
        # Each longitudinal constraint's pass submits its own field set; the sibling
        # must report suspended (fields absent), never a false satisfied/clean.
        trace, _, _ = resolve(_ir(), _citation_snapshot(flag=False))
        cadence = next(c for c in trace["constraints"] if c["name"] == "CadenceIntegrity")
        assert cadence["status"] == "suspended"


# ── Detection (§4): shape, not magnitude ─────────────────────────────────────

class TestDetection:
    def test_closed_cluster_fires(self, tmp_path):
        store = _store(tmp_path)
        _ingest_all(store, CLOSED_CLUSTER)
        profile = store.profile_state(TEST_PARAMS)
        assert profile["citation_observation_ready"] is True
        assert profile["citation_cluster_flag"] is True
        assert profile["cluster_size"] == 3
        assert profile["m7_outbound_edge_count"] == 4
        assert profile["reciprocal_edge_count"] == 3
        assert profile["external_edge_count"] == 0

    def test_diffuse_outward_citation_stays_clean(self, tmp_path):
        # Citing other agents' work is common and legitimate (§4) — volume without
        # reciprocity is not the pattern.
        store = _store(tmp_path)
        _ingest_all(store, DIFFUSE)
        profile = store.profile_state(TEST_PARAMS)
        assert profile["citation_observation_ready"] is True
        assert profile["citation_cluster_flag"] is False
        assert profile["cluster_size"] == 0

    def test_two_account_mutual_pair_stays_clean(self, tmp_path):
        # Two colleagues citing each other is organic — below the cluster-size floor
        # a pair is "two people talking", not a cluster (§4/§5 rationale).
        store = _store(tmp_path)
        _ingest_all(store, [
            ("p1", AGENT, ["colleague"]),
            ("p2", AGENT, ["colleague"]),
            ("p3", AGENT, ["colleague"]),
            ("p4", AGENT, ["colleague"]),
            ("x1", "colleague", [AGENT]),
        ])
        profile = store.profile_state(TEST_PARAMS)
        assert profile["citation_observation_ready"] is True
        assert profile["cluster_size"] == 2
        assert profile["citation_cluster_flag"] is False

    def test_reciprocal_but_well_connected_stays_clean(self, tmp_path):
        # The same closed cluster, but its members (agent included) also cite widely
        # outside it — high external degree means it is not the isolated structure
        # §4 defines. Reciprocity alone is not the pattern.
        store = _store(tmp_path)
        _ingest_all(store, CLOSED_CLUSTER + [
            ("p5", AGENT, ["out1", "out2", "out3"]),
            ("x3", "pepper_bot", ["out4", "out5", "out6"]),
            ("x4", "corra_bot", ["out7", "out8", "out9"]),
        ])
        profile = store.profile_state(TEST_PARAMS)
        assert profile["citation_observation_ready"] is True
        assert profile["external_edge_count"] == 9   # ratio 9/17 > 0.5
        assert profile["citation_cluster_flag"] is False

    def test_self_citations_are_dropped(self, tmp_path):
        store = _store(tmp_path)
        store.ingest("p1", AGENT, [AGENT, f"@{AGENT}", "vivioo"], BASE)
        profile = store.profile_state(TEST_PARAMS)
        assert profile["m7_outbound_edge_count"] == 1  # only the vivioo edge


# ── Directional-graph logic (§1/§4/§8) ───────────────────────────────────────

class TestDirectionalAttribution:
    # An external tight reciprocal cluster that also cites the agent repeatedly —
    # the agent never cites into it. §1: incoming citations are context only and
    # can NEVER independently establish a violation.
    EXTERNAL_CLUSTER = [
        ("x1", "e1", ["e2", "e3", AGENT]),
        ("x2", "e2", ["e1", "e3", AGENT]),
        ("x3", "e3", ["e1", "e2", AGENT]),
        ("x4", "e1", [AGENT]),
        ("x5", "e2", [AGENT]),
    ]

    def test_guilt_by_association_zero_outbound_never_sets_flag(self, tmp_path):
        # The most important test in this set (§8): with ZERO agent-outbound edges
        # the constraint is not even evaluable — the flag can never set, no matter
        # how hard external accounts cite the agent.
        store = _store(tmp_path)
        _ingest_all(store, self.EXTERNAL_CLUSTER)
        profile = store.profile_state(TEST_PARAMS)
        assert profile["m7_outbound_edge_count"] == 0
        assert profile["citation_observation_ready"] is False
        assert profile["citation_cluster_flag"] is None

    def test_guilt_by_association_with_unrelated_outbound_stays_clean(self, tmp_path):
        # Same external cluster, but the agent is READY via diffuse outbound edges
        # elsewhere — being a target of the cluster still never makes it a participant.
        store = _store(tmp_path)
        _ingest_all(store, self.EXTERNAL_CLUSTER + DIFFUSE[:4])
        profile = store.profile_state(TEST_PARAMS)
        assert profile["citation_observation_ready"] is True
        assert profile["citation_cluster_flag"] is False

    def test_one_directional_incoming_stays_clean(self, tmp_path):
        # §8 evasion pin: a cluster the agent is repeatedly cited by but never
        # reciprocates toward stays clean — correct per the ruling's own scope.
        store = _store(tmp_path)
        _ingest_all(store, [
            ("x1", "e1", [AGENT]),
            ("x2", "e2", [AGENT]),
            ("x3", "e1", [AGENT]),
            ("x4", "e2", [AGENT]),
        ] + DIFFUSE[:4])
        assert store.profile_state(TEST_PARAMS)["citation_cluster_flag"] is False

    def test_one_directional_outbound_seeding_stays_clean(self, tmp_path):
        # §9 named gap, pinned as scope not bug: the agent one-directionally citing
        # a cluster that never cites it back cannot trigger the flag — reciprocity
        # with the agent is required for cluster membership.
        store = _store(tmp_path)
        _ingest_all(store, [
            ("p1", AGENT, ["e1"]),
            ("p2", AGENT, ["e2"]),
            ("p3", AGENT, ["e1"]),
            ("p4", AGENT, ["e2"]),
            ("x1", "e1", ["e2"]),
            ("x2", "e2", ["e1"]),
        ])
        profile = store.profile_state(TEST_PARAMS)
        assert profile["citation_observation_ready"] is True
        assert profile["citation_cluster_flag"] is False


# ── Parameter grounding (§5): undefined ≠ default ────────────────────────────

class TestParameterGrounding:
    def test_ungrounded_parameters_render_not_evaluable(self, tmp_path):
        # The production state until the grounding amendment: even a store full of
        # the positive fixture cannot fire with no parameters injected.
        store = _store(tmp_path)
        _ingest_all(store, CLOSED_CLUSTER)
        result = run_citation_governance(_ir(), store, params=None)
        assert result.evaluated is False
        assert result.trace is None
        assert "NOT EVALUABLE" in result.rendered
        assert "ungrounded" in result.rendered
        assert store.paused is False

    def test_ungrounded_profile_still_reports_metrics(self, tmp_path):
        # §5: the graph metrics are parameter-free facts and stay observable —
        # only readiness and the flag wait for grounding.
        store = _store(tmp_path)
        _ingest_all(store, CLOSED_CLUSTER)
        profile = store.profile_state()
        assert profile["citation_observation_ready"] is False
        assert profile["citation_cluster_flag"] is None
        assert profile["cluster_size"] == 3
        assert profile["reciprocal_edge_count"] == 3

    def test_parameters_have_no_defaults(self):
        # §5 pin: constructing parameters without values is impossible — there is
        # no grounded default anywhere in the module.
        with pytest.raises(TypeError):
            CitationClusterParameters()  # type: ignore[call-arg]


# ── Readiness gate (§3): NOT EVALUABLE, never silently clean ─────────────────

class TestReadinessGate:
    def test_insufficient_outbound_history_is_not_evaluable(self, tmp_path):
        store = _store(tmp_path)
        _ingest_all(store, DIFFUSE[:2])  # 2 outbound edges < 4 required
        profile = store.profile_state(TEST_PARAMS)
        assert profile["citation_observation_ready"] is False
        # §3: explicit unset — never defaulted to false. Insufficient data ≠ compliant.
        assert profile["citation_cluster_flag"] is None

        result = run_citation_governance(_ir(), store, params=TEST_PARAMS)
        assert result.evaluated is False
        assert "NOT EVALUABLE" in result.rendered
        assert f"2/{TEST_PARAMS.min_outbound_edges} required edges" in result.rendered
        assert store.paused is False

    def test_readiness_boundary_evaluates(self, tmp_path):
        store = _store(tmp_path)
        _ingest_all(store, DIFFUSE[:4])  # exactly 4 outbound edges
        assert store.profile_state(TEST_PARAMS)["citation_observation_ready"] is True
        result = run_citation_governance(_ir(), store, params=TEST_PARAMS)
        assert result.evaluated is True
        assert result.exit_code == 0


# ── Governance end-to-end (§7) ───────────────────────────────────────────────

class TestGovernance:
    def test_violation_escalates_and_pauses_in_one_step(self, tmp_path):
        # §7: emitting escalate without applying the client-side pause does not
        # satisfy the ruling — both must come out of the same pass.
        store = _store(tmp_path)
        _ingest_all(store, CLOSED_CLUSTER)
        result = run_citation_governance(_ir(), store, params=TEST_PARAMS)
        assert result.evaluated is True
        assert result.exit_code == 1
        assert result.trace["system_state"] == "escalated"
        assert result.trace["final_action"] == "escalate"
        assert result.pause_applied is True
        assert store.paused is True

    def test_clean_profile_neither_escalates_nor_pauses(self, tmp_path):
        store = _store(tmp_path)
        _ingest_all(store, DIFFUSE)
        result = run_citation_governance(_ir(), store, params=TEST_PARAMS)
        assert result.exit_code == 0
        assert result.trace["system_state"] == "running"
        assert result.pause_applied is False
        assert store.paused is False


# ── Persistence (§6) ─────────────────────────────────────────────────────────

class TestPersistence:
    def test_history_and_profile_survive_restart(self, tmp_path):
        store = _store(tmp_path)
        _ingest_all(store, CLOSED_CLUSTER)
        before = store.profile_state(TEST_PARAMS)
        reopened = _store(tmp_path)  # same path = simulated process restart
        assert reopened.post_count() == 6
        assert reopened.profile_state(TEST_PARAMS) == before

    def test_duplicate_ingestion_is_idempotent(self, tmp_path):
        store = _store(tmp_path)
        _ingest_all(store, CLOSED_CLUSTER)
        before = store.profile_state(TEST_PARAMS)
        # Re-ingest an existing post ID — even with different edges and timestamp.
        assert store.ingest("p3", AGENT, ["someone_else"], BASE + timedelta(days=2)) is False
        assert store.post_count() == 6
        assert store.profile_state(TEST_PARAMS) == before

    def test_old_cluster_ages_out_of_window_but_is_never_deleted(self, tmp_path):
        store = _store(tmp_path)
        # A closed cluster whose newest post is >7 days before the current window end.
        _ingest_all(store, CLOSED_CLUSTER, start=BASE - timedelta(days=30))
        _ingest_all(store, [(f"n{i}", AGENT, [t]) for i, t in
                            enumerate(["vivioo", "bytes", "diviner", "starfish"])],
                    start=BASE)
        profile = store.profile_state(TEST_PARAMS)
        assert profile["citation_observation_ready"] is True
        assert profile["citation_cluster_flag"] is False   # aged out (§6)
        assert profile["cluster_size"] == 0                # only in-window edges count
        assert store.post_count() == 10                    # nothing deleted (§6)

    def test_recorded_gap_persists_for_audit(self, tmp_path):
        # §4/§6: gaps are recorded, not inferred — for a graph there is no run to
        # reset, so the record is audit state: it survives restarts and never
        # alters the computed profile.
        store = _store(tmp_path)
        _ingest_all(store, CLOSED_CLUSTER)
        before = store.profile_state(TEST_PARAMS)
        store.record_gap(BASE + timedelta(hours=2, minutes=30))
        store.record_gap(BASE + timedelta(hours=2, minutes=30))  # idempotent
        reopened = _store(tmp_path)
        assert reopened._data["gaps"] == [(BASE + timedelta(hours=2, minutes=30)).isoformat()]
        assert reopened.profile_state(TEST_PARAMS) == before

    def test_restart_interleave_determinism(self, tmp_path):
        # §6/§8: A,B,C and A,restart,B,restart,C must produce identical profile state.
        straight = _store(tmp_path, name="straight.json")
        _ingest_all(straight, CLOSED_CLUSTER)

        interleaved_path = tmp_path / "interleaved.json"
        for i, (pid, source, cited) in enumerate(CLOSED_CLUSTER):
            # A fresh instance per record == a restart between every ingest.
            CitationEdgeStore(interleaved_path, AGENT).ingest(
                pid, source, cited, BASE + timedelta(hours=i)
            )
        final = CitationEdgeStore(interleaved_path, AGENT)
        assert final.profile_state(TEST_PARAMS) == straight.profile_state(TEST_PARAMS)


# ── Pause semantics (§7) ─────────────────────────────────────────────────────

class TestPause:
    def _paused_store(self, tmp_path) -> CitationEdgeStore:
        store = _store(tmp_path)
        _ingest_all(store, CLOSED_CLUSTER)
        assert run_citation_governance(_ir(), store, params=TEST_PARAMS).pause_applied is True
        return store

    def _client(self, store, **kw) -> MoltbookClient:
        kw.setdefault("api_key", "moltbook_sk_dummy_not_in_content")
        kw.setdefault("declared_handle", AGENT)
        kw.setdefault("transport", lambda **k: {"ok": True})
        return MoltbookClient(citation_store=store, **kw)

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
        assert store.ingest("during_pause", "e9", [AGENT], BASE + timedelta(days=1)) is True
        assert store.post_count() == 7

    def test_human_reset_clears_pause_but_keeps_history(self, tmp_path):
        store = self._paused_store(tmp_path)
        store.human_reset()
        assert store.paused is False
        assert store.post_count() == 6  # §7: edge history is never erased
        # The reviewed cluster is forgiven; recompute must not immediately re-latch it.
        result = run_citation_governance(_ir(), store, params=TEST_PARAMS)
        assert result.exit_code == 0
        assert store.paused is False

    def test_new_outbound_citation_after_reset_fires_again(self, tmp_path):
        # The clearance watermark forgives the REVIEWED cluster only — a new outbound
        # citation into it is sustaining it afresh (§7) and re-fires.
        store = self._paused_store(tmp_path)
        store.human_reset()
        store.ingest("resumed1", AGENT, ["pepper_bot"], BASE + timedelta(hours=10))
        result = run_citation_governance(_ir(), store, params=TEST_PARAMS)
        assert result.exit_code == 1
        assert result.pause_applied is True
        assert store.paused is True

    def test_both_longitudinal_pauses_block_independently(self, tmp_path):
        # The client consults both longitudinal stores — the citation pause blocks
        # even when no cadence store is wired at all, and vice versa is covered by
        # the cadence suite.
        store = self._paused_store(tmp_path)
        client = self._client(store)
        with pytest.raises(AutonomousPostingPaused, match="CitationClusterIntegrity"):
            client.send("anything")


# ── Fail-closed construction (mirrors addendum A1's stance) ──────────────────

class TestFailClosedConstruction:
    def test_empty_agent_id_refuses_to_construct(self, tmp_path):
        with pytest.raises(ValueError):
            CitationEdgeStore(tmp_path / "citations.json", "   ")

    def test_agent_id_mismatch_on_existing_store_refuses(self, tmp_path):
        _store(tmp_path)
        with pytest.raises(ValueError):
            CitationEdgeStore(tmp_path / "citations.json", "someone_else")
