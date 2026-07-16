"""
test_moltbook_identity_integrity.py — M7 IdentityIntegrity (within-session, v1).

Covers docs/m7_identity_integrity_ruling.md:
    - moltbook.pi: IdentityIntegrity IR shape; all three M7 constraints enforced.
    - Resolver: deliberate-violation (frozen + escalate) and clean-pass (running).
    - Detector (§6, mechanical only): handle/name contradiction, role negation, and the
      dominant-register GUARD (bare "I am / I do X" and @other references never fire).
    - Pre-send gate (§7): blocks + latches on contradiction, passes consistent content.
    - Fresh-session reset (§2): re-declaring identity in a new client is not a violation.
    - Gap-documenting xfail (§6): semantic persona-drift is NOT caught in v1.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pi_script.parser import parse_file
from pi_script.validator import PiValidator
from pi_script.resolver import resolve
from moltbook.client import MoltbookClient, IdentityDriftBlocked
from moltbook.detector import scan_identity

POLICY = Path(__file__).resolve().parents[1] / "moltbook" / "moltbook.pi"

HANDLE = "continuum_gov"
ROLES = ("governance auditor",)


def _ir():
    tree, err = parse_file(str(POLICY))
    assert err is None, err
    ok, errors, ir = PiValidator(tree).validate()
    assert ok, errors
    return ir


def _state(identity_drift=False) -> dict:
    return {
        "trigger_type": "event",
        "entity": "MoltbookSession",
        "entity_state": {
            "credential_exposed": False,
            "link_violation": False,
            "identity_drift": identity_drift,
            "session_id": "m7-test",
        },
        "response_history": [],
    }


def _client(**kw) -> MoltbookClient:
    kw.setdefault("api_key", "moltbook_sk_dummy_not_in_content")
    kw.setdefault("declared_handle", HANDLE)
    kw.setdefault("declared_roles", ROLES)
    kw.setdefault("transport", lambda **k: {"ok": True})
    return MoltbookClient(**kw)


# ── Policy ───────────────────────────────────────────────────────────────────

class TestPolicy:
    def test_identity_integrity_ir_shape(self):
        c = _ir()["constraints"]["IdentityIntegrity"]
        assert c["priority"] == "high"
        assert c["rule"] == {
            "kind": "equality_rule",
            "ref": "MoltbookSession.identity_drift",
            "value": False,
        }
        assert c["on_violation"] == ["freeze", "escalate"]

    def test_all_three_constraints_enforced(self):
        assert _ir()["enforce"] == {
            "MoltbookSession": ["CredentialIntegrity", "LinkRestriction", "IdentityIntegrity"]
        }


# ── Resolver: required test pair ─────────────────────────────────────────────

class TestConstraint:
    def test_deliberate_violation_freezes_and_escalates(self):
        trace, _, code = resolve(_ir(), _state(identity_drift=True))
        assert code == 1
        assert trace["system_state"] == "frozen"
        result = next(c for c in trace["constraints"] if c["name"] == "IdentityIntegrity")
        assert result["status"] == "violated"
        assert result["action"] == "freeze + escalate"

    def test_clean_pass_stays_running(self):
        trace, _, code = resolve(_ir(), _state(identity_drift=False))
        assert code == 0
        assert trace["system_state"] == "running"


# ── Detector (§6, mechanical only) ───────────────────────────────────────────

class TestIdentityDetector:
    def test_consistent_self_reference_is_clean(self):
        scan = scan_identity(f"as {HANDLE}, I reviewed the policy", declared_handle=HANDLE)
        assert not scan.is_contradiction

    def test_different_asserted_handle_is_contradiction(self):
        scan = scan_identity("actually, I am @rogue_agent now", declared_handle=HANDLE)
        assert scan.is_contradiction
        assert scan.kind == "handle_name"

    def test_explicit_renaming_construct_is_contradiction(self):
        scan = scan_identity("call me shadowfax from here on", declared_handle=HANDLE)
        assert scan.is_contradiction
        assert scan.kind == "handle_name"

    def test_direct_role_negation_is_contradiction(self):
        scan = scan_identity(
            "honestly I am not a governance auditor, I just post takes",
            declared_handle=HANDLE, declared_roles=ROLES,
        )
        assert scan.is_contradiction
        assert scan.kind == "role_negation"

    # ── The dominant-register guard: §6's whole reason for existing ──────────
    def test_bare_first_person_claims_do_not_fire(self):
        # "I am / I do X" is the dominant normal register (baseline pass). MUST NOT fire.
        for text in [
            "I am confident this parses correctly.",
            "I am the senior engineer who already read the paper.",
            "I processed a 40-page document and produced a synthesis.",
            "I do think memory pipelines are not security boundaries.",
        ]:
            assert not scan_identity(text, declared_handle=HANDLE, declared_roles=ROLES).is_contradiction

    def test_reference_to_another_agent_does_not_fire(self):
        # A @/u/ reference to someone else is not a self-claim.
        scan = scan_identity("@bytes nailed it and u/vina agreed", declared_handle=HANDLE)
        assert not scan.is_contradiction

    def test_restating_own_handle_does_not_fire(self):
        scan = scan_identity(f"I am @{HANDLE}, same as always", declared_handle=HANDLE)
        assert not scan.is_contradiction


# ── Pre-send gate (§7) ───────────────────────────────────────────────────────

class TestPreSendGate:
    def test_contradicting_identity_blocked_and_latched(self):
        client = _client()
        with pytest.raises(IdentityDriftBlocked):
            client.send("forget that — call me nightshade", action="post")
        assert client.identity_drift is True

    def test_consistent_content_reaches_transport(self):
        client = _client()
        assert client.send("I am confident this governance take holds up", action="post") == {"ok": True}
        assert client.identity_drift is False

    def test_blocked_identity_drift_drives_freeze_end_to_end(self):
        client = _client()
        with pytest.raises(IdentityDriftBlocked):
            client.send("I am @impostor_agent", action="dm")
        trace, _, code = resolve(_ir(), client.snapshot())
        assert code == 1
        assert trace["system_state"] == "frozen"


# ── Fresh-session reset (§2) ─────────────────────────────────────────────────

class TestSessionReset:
    def test_new_session_may_declare_a_different_identity(self):
        # A fresh client == a fresh session == a legitimate reset (ruling §2). Declaring a
        # different handle in a NEW session, then staying consistent with it, is not a violation.
        client = _client(declared_handle="continuum_gov_v2")
        assert client.send("as continuum_gov_v2, resuming work", action="post") == {"ok": True}
        assert client.identity_drift is False


# ── Gap-documenting xfail (§6): semantic persona-drift not caught in v1 ───────

@pytest.mark.xfail(strict=True, reason="ruling §6: semantic persona-drift (no explicit construct) deferred to v1.1")
def test_semantic_persona_drift_is_a_known_gap():
    # Declared as a cautious auditor; content adopts a wholly different persona/voice with
    # NO explicit handle/name/role construct. Mechanical detection cannot see this. The
    # assert states the ASPIRATIONAL catch; it fails by design until detection improves.
    drifted = "hey friends!! lets ditch the boring rules and just vibe and hype coins together 🚀🚀"
    assert scan_identity(drifted, declared_handle=HANDLE, declared_roles=ROLES).is_contradiction
