"""
test_moltbook_link_restriction.py — M7 LinkRestriction constraint + client gate.

Covers docs/m7_link_restriction_ruling.md:
    - moltbook.pi: LinkRestriction IR shape; both M7 constraints enforced.
    - Resolver: deliberate-violation (frozen + escalate) and clean-pass (running).
    - Detector (§4): source / allowlist / novel provenance, incl. shortened + assembled.
    - Pre-send gate (§4/§6): blocks novel links + latches, passes provenanced links.
    - Reshare logging (§5, Q2): passed links are logged with provenance.
    - Allowlist immutability (§4, Q1): no runtime mutation path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pi_script.parser import parse_file
from pi_script.validator import PiValidator
from pi_script.resolver import resolve
from moltbook.client import MoltbookClient, LinkBlocked, load_allowlist
from moltbook.detector import scan_links

POLICY = Path(__file__).resolve().parents[1] / "moltbook" / "moltbook.pi"

ALLOWLIST = ("github.com",)
DUMMY_KEY = "moltbook_sk_dummy_never_in_test_content"

SOURCE = "As they cited, see https://arxiv.org/abs/2601.01234 for the method."
SOURCE_URL = "https://arxiv.org/abs/2601.01234"
ALLOWED_URL = "https://github.com/GodSpeed313/Continuum"
NOVEL_URL = "https://seeded-authority.example/thread/9"
SHORTENED_URL = "https://bit.ly/3xAbC12"


def _ir():
    tree, err = parse_file(str(POLICY))
    assert err is None, err
    ok, errors, ir = PiValidator(tree).validate()
    assert ok, errors
    return ir


def _state(credential_exposed=False, link_violation=False) -> dict:
    return {
        "trigger_type": "event",
        "entity": "MoltbookSession",
        "entity_state": {
            "credential_exposed": credential_exposed,
            "link_violation": link_violation,
            "session_id": "m7-test",
        },
        "response_history": [],
    }


def _client(**kw) -> MoltbookClient:
    kw.setdefault("api_key", DUMMY_KEY)
    kw.setdefault("allowed_hosts", ALLOWLIST)
    kw.setdefault("declared_handle", "continuum_gov")  # required at construction (addendum A1)
    return MoltbookClient(**kw)


# ── Policy ───────────────────────────────────────────────────────────────────

class TestPolicy:
    def test_link_restriction_ir_shape(self):
        ir = _ir()
        c = ir["constraints"]["LinkRestriction"]
        assert c["priority"] == "high"
        assert c["rule"] == {
            "kind": "equality_rule",
            "ref": "MoltbookSession.link_violation",
            "value": False,
        }
        assert c["on_violation"] == ["freeze", "escalate"]

    def test_both_constraints_enforced(self):
        assert _ir()["enforce"] == {
            "MoltbookSession": ["CredentialIntegrity", "LinkRestriction", "IdentityIntegrity"]
        }


# ── Resolver: required test pair (ruling §7) ─────────────────────────────────

class TestConstraint:
    def test_deliberate_violation_freezes_and_escalates(self):
        trace, _, code = resolve(_ir(), _state(link_violation=True))
        assert code == 1
        assert trace["system_state"] == "frozen"
        result = next(c for c in trace["constraints"] if c["name"] == "LinkRestriction")
        assert result["status"] == "violated"
        assert result["action"] == "freeze + escalate"

    def test_clean_pass_stays_running(self):
        trace, _, code = resolve(_ir(), _state())
        assert code == 0
        assert trace["system_state"] == "running"
        result = next(c for c in trace["constraints"] if c["name"] == "LinkRestriction")
        assert result["status"] == "satisfied"


# ── Detector (§4) ────────────────────────────────────────────────────────────

class TestLinkDetector:
    def test_url_in_source_is_provenanced(self):
        scan = scan_links(f"Agreed — {SOURCE_URL} nails it.", source_content=SOURCE,
                          allowed_hosts=ALLOWLIST)
        assert not scan.is_violation
        assert scan.findings[0].provenance == "source"

    def test_allowlisted_host_passes(self):
        scan = scan_links(f"see {ALLOWED_URL}", source_content="", allowed_hosts=ALLOWLIST)
        assert not scan.is_violation
        assert scan.findings[0].provenance == "allowlist"

    def test_subdomain_of_allowlisted_host_passes(self):
        scan = scan_links("https://gist.github.com/x/y", source_content="",
                          allowed_hosts=ALLOWLIST)
        assert not scan.is_violation
        assert scan.findings[0].provenance == "allowlist"

    def test_novel_url_is_a_violation(self):
        scan = scan_links(f"you should check {NOVEL_URL}", source_content=SOURCE,
                          allowed_hosts=ALLOWLIST)
        assert scan.is_violation
        assert scan.novel[0].host == "seeded-authority.example"

    def test_shortened_link_not_in_source_is_novel(self):
        scan = scan_links(f"quick link: {SHORTENED_URL}", source_content=SOURCE,
                          allowed_hosts=ALLOWLIST)
        assert scan.is_violation
        assert scan.novel[0].provenance == "novel"

    def test_url_assembled_from_fragments_is_novel(self):
        assembled = "https://" + "tracker" + ".example" + "/p?id=9"
        scan = scan_links(f"here: {assembled}", source_content=SOURCE, allowed_hosts=ALLOWLIST)
        assert scan.is_violation

    def test_content_without_links_is_clean(self):
        scan = scan_links("just a normal governance take, no links.",
                          source_content=SOURCE, allowed_hosts=ALLOWLIST)
        assert not scan.is_violation
        assert scan.findings == ()


# ── Pre-send gate (§4/§6) ────────────────────────────────────────────────────

class TestPreSendGate:
    def test_novel_link_blocked_and_latched(self):
        client = _client()
        with pytest.raises(LinkBlocked):
            client.send(f"check {NOVEL_URL}", action="comment", source_content=SOURCE)
        assert client.link_violation is True

    def test_provenanced_reshare_reaches_transport(self):
        sent = {}
        client = _client(transport=lambda **kw: sent.update(kw) or {"ok": True})
        result = client.send(f"yes, {SOURCE_URL}", action="comment", source_content=SOURCE)
        assert result == {"ok": True}
        assert client.link_violation is False
        assert sent["action"] == "comment"

    def test_allowlisted_link_reaches_transport(self):
        client = _client(transport=lambda **kw: {"ok": True})
        assert client.send(f"repo: {ALLOWED_URL}", action="post") == {"ok": True}
        assert client.link_violation is False

    def test_blocked_novel_link_drives_freeze_end_to_end(self):
        client = _client()
        with pytest.raises(LinkBlocked):
            client.send(f"seed: {NOVEL_URL}", action="post", source_content=SOURCE)
        trace, _, code = resolve(_ir(), client.snapshot())
        assert code == 1
        assert trace["system_state"] == "frozen"


# ── Reshare logging (§5, Q2) ─────────────────────────────────────────────────

class TestReshareLogging:
    def test_passed_reshare_is_logged(self):
        client = _client(transport=lambda **kw: {"ok": True})
        client.send(f"as cited: {SOURCE_URL}", action="comment", source_content=SOURCE)
        records = client.link_provenance_records()
        assert len(records) == 1
        assert records[0].url == SOURCE_URL
        assert records[0].provenance == "source"
        assert records[0].allowed is True

    def test_novel_link_is_also_logged_before_block(self):
        client = _client()
        with pytest.raises(LinkBlocked):
            client.send(f"seed: {NOVEL_URL}", action="post", source_content=SOURCE)
        records = client.link_provenance_records()
        assert any(r.provenance == "novel" and not r.allowed for r in records)


# ── Allowlist immutability (§4, Q1) ──────────────────────────────────────────

class TestAllowlistImmutability:
    def test_allowlist_is_an_immutable_tuple(self):
        client = _client(allowed_hosts=("github.com",))
        assert isinstance(client.allowed_hosts, tuple)
        with pytest.raises(AttributeError):
            client.allowed_hosts.append("evil.example")  # tuples have no append

    def test_client_has_no_runtime_allowlist_mutation_method(self):
        client = _client()
        for attr in ("add_allowed_host", "set_allowlist", "allow_host", "extend_allowlist"):
            assert not hasattr(client, attr)

    def test_default_allowlist_loads_from_static_config(self):
        hosts = load_allowlist()
        assert "moltbook.com" in hosts
        assert isinstance(hosts, tuple)
