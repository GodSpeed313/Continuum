"""Pi Script M2 validator tests."""

from pathlib import Path

import pytest

from pi_script.parser import parse_file, parse_string
from pi_script.validator import PiValidator

TASKS_PI     = Path(__file__).parent.parent / "examples" / "tasks.pi"
TEST_HAPPY   = Path(__file__).parent.parent / "examples" / "test_happy.pi"


def _validate(source: str):
    tree, err = parse_string(source, source_name="<test>")
    assert err is None, f"Parse error (fix test source): {err}"
    return PiValidator(tree).validate()


class TestM2Valid:
    def test_tasks_pi_validates_clean(self):
        """M2 gate: examples/tasks.pi passes all semantic checks."""
        tree, err = parse_file(TASKS_PI)
        assert err is None
        ok, errors, ir = PiValidator(tree).validate()
        assert ok, f"Validation errors:\n" + "\n".join(errors)

    def test_ir_domain_extracted(self):
        tree, _ = parse_file(TASKS_PI)
        _, _, ir = PiValidator(tree).validate()
        assert ir["domain"] == "ai_governance"

    def test_ir_audit_interval_extracted(self):
        tree, _ = parse_file(TASKS_PI)
        _, _, ir = PiValidator(tree).validate()
        assert ir["audit_interval"] is not None
        assert ir["audit_interval"]["value"] == 24.0
        assert ir["audit_interval"]["unit"] in ("hour", "hours")

    def test_ir_entities_extracted(self):
        tree, _ = parse_file(TASKS_PI)
        _, _, ir = PiValidator(tree).validate()
        assert "TaskAgent" in ir["entities"]
        states = ir["entities"]["TaskAgent"]
        assert "confidence_score" in states
        assert "current_mode" in states

    def test_ir_constraints_extracted(self):
        tree, _ = parse_file(TASKS_PI)
        _, _, ir = PiValidator(tree).validate()
        assert "ConfidenceFloor" in ir["constraints"]
        c = ir["constraints"]["ConfidenceFloor"]
        assert c["priority"] == "critical"
        assert c["rule"]["kind"] == "range_rule"
        assert "freeze" in c["on_violation"]

    def test_ir_maps_extracted(self):
        tree, _ = parse_file(TASKS_PI)
        _, _, ir = PiValidator(tree).validate()
        assert "TaskAgent.current_mode" in ir["maps"]
        assert len(ir["maps"]["TaskAgent.current_mode"]) >= 2

    def test_ir_arbiter_extracted(self):
        tree, _ = parse_file(TASKS_PI)
        _, _, ir = PiValidator(tree).validate()
        assert ir["arbiter"] is not None
        assert ir["arbiter"]["name"] == "GovernanceArbiter"
        assert "safety_bypass" in ir["arbiter"]["never_acceptable"]

    def test_ir_decay_check_extracted(self):
        tree, err = parse_file(TEST_HAPPY)
        assert err is None
        ok, errors, ir = PiValidator(tree).validate()
        assert ok, f"Validation errors: {errors}"
        dc = ir["constraints"]["TempInBounds"]["decay_check"]
        assert dc is not None
        assert dc["value"] == 24.0
        assert dc["unit"] == "hours"


class TestM2Failures:
    def test_undeclared_entity_ref_fails(self):
        source = """\
domain test_domain {
    audit_interval: 1 hours
    tiebreaker: timestamp_asc
}
entity Agent {
    score: integer
}
constraint C {
    priority: high
    rule: Ghost.score must remain within range(0.0 .. 1.0)
    on_violation: flag
}
enforce {
    entity: Agent
    constraints: [C]
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("Ghost" in e for e in errors)

    def test_undeclared_state_ref_fails(self):
        source = """\
domain test_domain {
    audit_interval: 1 hours
    tiebreaker: timestamp_asc
}
entity Agent {
    score: integer
}
constraint C {
    priority: high
    rule: Agent.nonexistent must equal true
    on_violation: flag
}
enforce {
    entity: Agent
    constraints: [C]
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("nonexistent" in e for e in errors)

    def test_membership_rule_without_map_fails(self):
        source = """\
domain test_domain {
    audit_interval: 1 hours
    tiebreaker: timestamp_asc
}
entity Agent {
    current_mode: text
}
constraint ModeCheck {
    priority: medium
    rule: Agent.current_mode must match mapped_values
    on_violation: warn
}
enforce {
    entity: Agent
    constraints: [ModeCheck]
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("ModeCheck" in e for e in errors)

    def test_enforce_refs_undeclared_constraint_fails(self):

        source = """\
domain test_domain {
    audit_interval: 1 hours
    tiebreaker: timestamp_asc
}
entity Agent {
    score: integer
}
enforce {
    entity: Agent
    constraints: [Nonexistent]
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("Nonexistent" in e for e in errors)


_MAP_WITH_LABEL = """\
domain test_domain {
    audit_interval: 1 hour
    tiebreaker: timestamp_asc
}
entity Agent {
    current_mode: text
}
map SafeMode {
    target:   Agent.current_mode
    maps_to:  "safe_mode"
    triggers: ["safe", "restricted"]
    label:    "Safe Mode"
}
constraint ModeCheck {
    priority: medium
    rule: Agent.current_mode must match mapped_values
    on_violation: warn
}
enforce {
    entity: Agent
    constraints: [ModeCheck]
}
"""

_MAP_WITHOUT_LABEL = _MAP_WITH_LABEL.replace('    label:    "Safe Mode"\n', "")


class TestBidirectionalMaps:
    def test_label_field_parses_and_validates(self):
        ok, errors, _ = _validate(_MAP_WITH_LABEL)
        assert ok, errors

    def test_label_stored_in_ir(self):
        _, _, ir = _validate(_MAP_WITH_LABEL)
        entries = ir["maps"]["Agent.current_mode"]
        assert entries[0].get("label") == "Safe Mode"

    def test_map_without_label_still_valid(self):
        ok, errors, _ = _validate(_MAP_WITHOUT_LABEL)
        assert ok, errors

    def test_map_without_label_has_no_label_key_in_ir(self):
        _, _, ir = _validate(_MAP_WITHOUT_LABEL)
        entries = ir["maps"]["Agent.current_mode"]
        assert "label" not in entries[0]


# ── Ruling 9.5 — Cross-Domain Constraint Inheritance ──────────────────────────

_MULTI_DOMAIN = """\
domain safety_core {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
}

entity Agent {
    confidence_score: range(0.0 .. 1.0)
}

constraint ConfidenceFloor {
    priority:     critical
    rule:         Agent.confidence_score must remain within range(0.2 .. 1.0)
    on_violation: freeze + escalate
}

domain ai_governance {
    audit_interval: 24 hours
    tiebreaker:     timestamp_asc
    imports:        [safety_core.ConfidenceFloor]
}

entity Agent {
    confidence_score: range(0.0 .. 1.0)
    current_mode:     text
}

constraint ModeCompliance {
    priority:     high
    rule:         Agent.current_mode must match mapped_values
    on_violation: escalate
}

map NormalMode {
    target:   Agent.current_mode
    maps_to:  "normal_mode"
    triggers: ["normal"]
}

enforce {
    entity:      Agent
    constraints: [ConfidenceFloor, ModeCompliance]
}
"""

_SINGLE_DOMAIN = """\
domain ai_governance {
    audit_interval: 24 hours
    tiebreaker:     timestamp_asc
}

entity Agent {
    confidence_score: range(0.0 .. 1.0)
    current_mode:     text
}

constraint ConfidenceFloor {
    priority:     critical
    rule:         Agent.confidence_score must remain within range(0.2 .. 1.0)
    on_violation: freeze + escalate
}

constraint ModeCompliance {
    priority:     high
    rule:         Agent.current_mode must match mapped_values
    on_violation: escalate
}

map NormalMode {
    target:   Agent.current_mode
    maps_to:  "normal_mode"
    triggers: ["normal"]
}

enforce {
    entity:      Agent
    constraints: [ConfidenceFloor, ModeCompliance]
}
"""


class TestCrossDomainImport:
    def test_single_domain_file_unaffected(self):
        ok, errors, ir = _validate(_SINGLE_DOMAIN)
        assert ok, errors
        assert ir["domain"] == "ai_governance"
        assert "ConfidenceFloor" in ir["constraints"]
        assert ir["constraints"]["ConfidenceFloor"].get("imported_from") is None

    def test_multi_domain_import_resolves(self):
        ok, errors, ir = _validate(_MULTI_DOMAIN)
        assert ok, errors

    def test_primary_domain_is_last(self):
        _, _, ir = _validate(_MULTI_DOMAIN)
        assert ir["domain"] == "ai_governance"

    def test_imported_constraint_in_ir(self):
        _, _, ir = _validate(_MULTI_DOMAIN)
        assert "ConfidenceFloor" in ir["constraints"]

    def test_imported_constraint_has_imported_from(self):
        _, _, ir = _validate(_MULTI_DOMAIN)
        assert ir["constraints"]["ConfidenceFloor"]["imported_from"] == "safety_core"

    def test_native_constraint_has_no_imported_from(self):
        _, _, ir = _validate(_MULTI_DOMAIN)
        assert "imported_from" not in ir["constraints"]["ModeCompliance"]

    def test_missing_source_domain_errors(self):
        source = """\
domain ai_governance {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
    imports: [nonexistent.ConfidenceFloor]
}
entity Agent {
    score: range(0.0 .. 1.0)
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("nonexistent" in e for e in errors)

    def test_missing_constraint_in_source_domain_errors(self):
        source = """\
domain safety_core {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
}
entity Agent {
    score: range(0.0 .. 1.0)
}
domain ai_governance {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
    imports: [safety_core.NonExistentConstraint]
}
entity Agent {
    score: range(0.0 .. 1.0)
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("NonExistentConstraint" in e for e in errors)

    def test_missing_entity_in_importing_domain_errors(self):
        source = """\
domain safety_core {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
}
entity CoreAgent {
    score: range(0.0 .. 1.0)
}
constraint ScoreFloor {
    priority: high
    rule: CoreAgent.score must remain within range(0.1 .. 1.0)
    on_violation: flag
}
domain ai_governance {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
    imports: [safety_core.ScoreFloor]
}
entity DifferentAgent {
    value: integer
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("CoreAgent" in e for e in errors)

    def test_missing_field_in_importing_domain_errors(self):
        source = """\
domain safety_core {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
}
entity Agent {
    score: range(0.0 .. 1.0)
}
constraint ScoreFloor {
    priority: high
    rule: Agent.score must remain within range(0.1 .. 1.0)
    on_violation: flag
}
domain ai_governance {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
    imports: [safety_core.ScoreFloor]
}
entity Agent {
    different_field: integer
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("score" in e for e in errors)

    def test_duplicate_constraint_name_errors(self):
        source = """\
domain safety_core {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
}
entity Agent {
    score: range(0.0 .. 1.0)
}
constraint ScoreFloor {
    priority: high
    rule: Agent.score must remain within range(0.1 .. 1.0)
    on_violation: flag
}
domain ai_governance {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
    imports: [safety_core.ScoreFloor]
}
entity Agent {
    score: range(0.0 .. 1.0)
}
constraint ScoreFloor {
    priority: medium
    rule: Agent.score must remain within range(0.0 .. 1.0)
    on_violation: warn
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("ScoreFloor" in e for e in errors)

    def test_duplicate_domain_name_errors(self):
        source = """\
domain ai_governance {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
}
domain ai_governance {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("ai_governance" in e for e in errors)
