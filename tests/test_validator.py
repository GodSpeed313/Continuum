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
