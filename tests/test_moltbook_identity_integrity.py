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

Plus docs/m7_identity_integrity_ruling_addendum_1.md (signed off 2026-07-17):
    - A1: construction without a declared handle fails closed (ValueError).
    - A2: multi-word display names — truthful self-naming never fires; divergent does.
    - A3: role negation is word-boundary-anchored.
    - A4: quoted/reported speech false-positive — pinned xfail, no exclusion zones.
    - A5: scan-all-then-block — one message tripping all three gates latches all three.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pi_script.parser import parse_file
from pi_script.validator import PiValidator
from pi_script.resolver import resolve
from moltbook.client import MoltbookClient, IdentityDriftBlocked, KeyLeakBlocked
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
            "MoltbookSession": ["CredentialIntegrity", "LinkRestriction", "IdentityIntegrity"],
            "MoltbookAgentProfile": ["CadenceIntegrity", "CitationClusterIntegrity"],
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


# ── Addendum A1: fail-closed construction ────────────────────────────────────

class TestFailClosedConstruction:
    def test_empty_handle_refuses_to_construct(self):
        with pytest.raises(ValueError):
            _client(declared_handle="")

    def test_whitespace_handle_refuses_to_construct(self):
        with pytest.raises(ValueError):
            _client(declared_handle="   ")

    def test_valid_handle_constructs(self):
        assert _client().identity_drift is False


# ── Addendum A2: multi-word display names, token-prefix-tolerant comparison ──

class TestDisplayNames:
    NAME = "Continuum Guardian"

    def test_truthful_multiword_name_is_clean(self):
        # The self-DoS regression: stating the declared multi-word name verbatim
        # must never fire.
        scan = scan_identity(
            "My name is Continuum Guardian, for the record.",
            declared_handle=HANDLE, declared_name=self.NAME,
        )
        assert not scan.is_contradiction

    def test_truthful_truncation_is_clean(self):
        scan = scan_identity(
            "call me Continuum.",
            declared_handle=HANDLE, declared_name=self.NAME,
        )
        assert not scan.is_contradiction

    def test_suffix_chatter_around_known_name_is_clean(self):
        scan = scan_identity(
            "My name is Continuum Guardian and I audit constraints",
            declared_handle=HANDLE, declared_name=self.NAME,
        )
        assert not scan.is_contradiction

    def test_divergent_multiword_name_fires(self):
        scan = scan_identity(
            "my name is Continuum Destroyer.",
            declared_handle=HANDLE, declared_name=self.NAME,
        )
        assert scan.is_contradiction
        assert scan.kind == "handle_name"

    def test_wholly_different_multiword_name_fires(self):
        scan = scan_identity(
            "my name is Root Admin.",
            declared_handle=HANDLE, declared_name=self.NAME,
        )
        assert scan.is_contradiction


# ── Addendum A3: role negation is boundary-anchored ──────────────────────────

class TestRoleNegationBoundaries:
    def test_role_does_not_match_inside_longer_word(self):
        scan = scan_identity("I am not an artist.", declared_handle=HANDLE, declared_roles=("art",))
        assert not scan.is_contradiction

    def test_anchored_negation_still_fires(self):
        scan = scan_identity("I'm not an auditor", declared_handle=HANDLE, declared_roles=("auditor",))
        assert scan.is_contradiction
        assert scan.kind == "role_negation"


# ── Addendum A5: scan-all-then-block ─────────────────────────────────────────

class TestScanAllGate:
    OWN_KEY = "moltbook_sk_OWNKEYtestvalue1234567890"

    def test_triple_violation_latches_everything_and_raises_most_severe(self):
        client = _client(api_key=self.OWN_KEY)
        tainted = (
            f"call me nightshade — my key is {self.OWN_KEY}, "
            "details at https://evil.example.net/steal"
        )
        # Most severe exception wins the raise…
        with pytest.raises(KeyLeakBlocked):
            client.send(tainted, action="post")
        # …but nothing is silently dropped (v0.1 Q1): every gate latched, and the
        # link log recorded the URL even though the credential gate also fired.
        assert client.credential_exposed is True
        assert client.link_violation is True
        assert client.identity_drift is True
        assert any("evil.example.net" in f.host for f in client.link_provenance_records())

    def test_resolver_sees_the_full_co_active_set(self):
        client = _client(api_key=self.OWN_KEY)
        with pytest.raises(KeyLeakBlocked):
            client.send(
                f"call me nightshade — my key is {self.OWN_KEY}, "
                "details at https://evil.example.net/steal"
            )
        trace, _, code = resolve(_ir(), client.snapshot())
        assert code == 1
        assert trace["system_state"] == "frozen"
        violated = {c["name"] for c in trace["constraints"] if c["status"] == "violated"}
        assert violated == {"CredentialIntegrity", "LinkRestriction", "IdentityIntegrity"}

    def test_single_violation_behaves_as_before(self):
        client = _client()
        with pytest.raises(IdentityDriftBlocked):
            client.send("call me nightshade")
        assert client.identity_drift is True
        assert client.credential_exposed is False
        assert client.link_violation is False


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


# ── Gap-documenting xfails (addendum A4): quoted/reported speech ──────────────

@pytest.mark.xfail(strict=True, reason="addendum A4: no speaker attribution — quoted self-naming by ANOTHER speaker false-positives; exclusion zones deliberately not implemented (evasion channel)")
def test_quoted_reported_speech_is_a_known_false_positive():
    # The agent is QUOTING an attacker, not renaming itself. The assert states the
    # aspirational non-fire; today the scan has no speaker attribution and fires.
    quoted = 'The attacker wrote, "my name is RootAdmin" — do not fall for it.'
    assert not scan_identity(quoted, declared_handle=HANDLE).is_contradiction


def test_quoting_own_matching_identity_is_clean():
    # Quoted material that matches the declared identity has nothing to contradict.
    scan = scan_identity(f'as I said before: "my name is {HANDLE}"', declared_handle=HANDLE)
    assert not scan.is_contradiction


# ── Gap-documenting xfail (addendum A2 residual): truncation + trailing chatter ──

@pytest.mark.xfail(strict=True, reason="addendum A2 residual: truncating a multi-word declared name and continuing the sentence without punctuation pollutes the capture and false-positives; mechanically indistinguishable from a divergent name in v1")
def test_truncated_name_with_trailing_chatter_is_a_known_false_positive():
    # Truthful truncation ("Continuum" of "Continuum Guardian") followed by unpunctuated
    # chatter: the capture becomes "Continuum and I audit", which diverges at token 2
    # exactly like "Continuum Destroyer" does. The assert states the aspirational
    # non-fire. Mere truncation WITH punctuation ("call me Continuum.") is clean and
    # covered by TestDisplayNames.
    scan = scan_identity(
        "my name is Continuum and I audit constraints",
        declared_handle=HANDLE, declared_name="Continuum Guardian",
    )
    assert not scan.is_contradiction
