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
arbiter GovernancePolicy {
    acceptable_evolution:  []
    never_acceptable:      []
    requires_human_review: []
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
arbiter GovernancePolicy {
    acceptable_evolution:  []
    never_acceptable:      []
    requires_human_review: []
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
arbiter GovernancePolicy {
    acceptable_evolution:  []
    never_acceptable:      []
    requires_human_review: []
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


# ── Ruling 9.7 — Arbiter Mandatory ────────────────────────────────────────────

_MINIMAL_WITH_ARBITER = """\
domain ai_governance {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
}
entity Agent {
    score: range(0.0 .. 1.0)
}
constraint ScoreFloor {
    priority: high
    rule: Agent.score must remain within range(0.1 .. 1.0)
    on_violation: warn
}
enforce {
    entity: Agent
    constraints: [ScoreFloor]
}
arbiter GovernancePolicy {
    acceptable_evolution:  []
    never_acceptable:      []
    requires_human_review: []
}
"""

_MINIMAL_WITHOUT_ARBITER = """\
domain ai_governance {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
}
entity Agent {
    score: range(0.0 .. 1.0)
}
constraint ScoreFloor {
    priority: high
    rule: Agent.score must remain within range(0.1 .. 1.0)
    on_violation: warn
}
enforce {
    entity: Agent
    constraints: [ScoreFloor]
}
"""

_MULTI_WITH_ARBITER_IN_PRIMARY = """\
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
    on_violation: warn
}
domain ai_governance {
    audit_interval: 24 hours
    tiebreaker:     timestamp_asc
    imports:        [safety_core.ScoreFloor]
}
entity Agent {
    score: range(0.0 .. 1.0)
}
enforce {
    entity: Agent
    constraints: [ScoreFloor]
}
arbiter GovernancePolicy {
    acceptable_evolution:  []
    never_acceptable:      []
    requires_human_review: []
}
"""

_MULTI_WITH_ARBITER_IN_LIBRARY_ONLY = """\
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
    on_violation: warn
}
arbiter GovernancePolicy {
    acceptable_evolution:  []
    never_acceptable:      []
    requires_human_review: []
}
domain ai_governance {
    audit_interval: 24 hours
    tiebreaker:     timestamp_asc
    imports:        [safety_core.ScoreFloor]
}
entity Agent {
    score: range(0.0 .. 1.0)
}
enforce {
    entity: Agent
    constraints: [ScoreFloor]
}
"""


# ── Ruling 9.8 fixtures ───────────────────────────────────────────────────────

_SEMANTIC_MAP_VALID = """\
domain primary {
    audit_interval: 1 hour
    tiebreaker: timestamp_asc
}
entity Session {
    topic: text
}
map TopicMap {
    target:               Session.topic
    maps_to:              "active"
    triggers:             ["running", "started"]
    match_mode:           semantic
    similarity_threshold: 0.85
}
constraint TopicCompliance {
    priority:     medium
    rule:         Session.topic must match mapped_values
    on_violation: flag
}
enforce {
    entity:      Session
    constraints: [TopicCompliance]
}
arbiter Gov {
    acceptable_evolution:  []
    never_acceptable:      []
    requires_human_review: []
}
"""

_SEMANTIC_MAP_NO_THRESHOLD = """\
domain primary {
    audit_interval: 1 hour
    tiebreaker: timestamp_asc
}
entity Session {
    topic: text
}
map TopicMap {
    target:     Session.topic
    maps_to:    "active"
    triggers:   ["running"]
    match_mode: semantic
}
constraint TopicCompliance {
    priority:     medium
    rule:         Session.topic must match mapped_values
    on_violation: flag
}
enforce {
    entity:      Session
    constraints: [TopicCompliance]
}
arbiter Gov {
    acceptable_evolution:  []
    never_acceptable:      []
    requires_human_review: []
}
"""

_THRESHOLD_WITHOUT_SEMANTIC = """\
domain primary {
    audit_interval: 1 hour
    tiebreaker: timestamp_asc
}
entity Session {
    topic: text
}
map TopicMap {
    target:               Session.topic
    maps_to:              "active"
    triggers:             ["running"]
    similarity_threshold: 0.85
}
constraint TopicCompliance {
    priority:     medium
    rule:         Session.topic must match mapped_values
    on_violation: flag
}
enforce {
    entity:      Session
    constraints: [TopicCompliance]
}
arbiter Gov {
    acceptable_evolution:  []
    never_acceptable:      []
    requires_human_review: []
}
"""


class TestSemanticMapValidation:

    def test_valid_semantic_map_ir(self):
        ok, errors, ir = _validate(_SEMANTIC_MAP_VALID)
        assert ok, errors
        entries = ir["maps"]["Session.topic"]
        assert len(entries) == 1
        assert entries[0]["match_mode"] == "semantic"
        assert entries[0]["similarity_threshold"] == 0.85

    def test_semantic_requires_threshold(self):
        ok, errors, _ = _validate(_SEMANTIC_MAP_NO_THRESHOLD)
        assert not ok
        assert any("requires similarity_threshold" in e for e in errors)

    def test_threshold_without_semantic(self):
        ok, errors, _ = _validate(_THRESHOLD_WITHOUT_SEMANTIC)
        assert not ok
        assert any("only valid with match_mode: semantic" in e for e in errors)

    def test_threshold_zero_rejected(self):
        source = _SEMANTIC_MAP_VALID.replace("0.85", "0.0")
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("(0.0, 1.0]" in e for e in errors)

    def test_threshold_one_accepted(self):
        source = _SEMANTIC_MAP_VALID.replace("0.85", "1.0")
        ok, errors, _ = _validate(source)
        assert ok, errors

    def test_threshold_above_one_rejected(self):
        source = _SEMANTIC_MAP_VALID.replace("0.85", "1.1")
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("(0.0, 1.0]" in e for e in errors)

    def test_existing_map_unaffected(self):
        # A plain substring map (no match_mode / similarity_threshold) still validates.
        ok, errors, ir = _validate(_MINIMAL_WITH_ARBITER)
        assert ok, errors
        for ref_entries in ir["maps"].values():
            for entry in ref_entries:
                assert "match_mode" not in entry
                assert "similarity_threshold" not in entry


# ── Ruling 9.9 fixtures ───────────────────────────────────────────────────────

_BOUND_RULE_VALID = """\
domain primary {
    audit_interval: 1 hour
    tiebreaker: timestamp_asc
}
entity Model {
    mse: range(0.0 .. 1.0)
}
constraint MseFloor {
    priority:     high
    rule:         Model.mse must remain < 0.8
    on_violation: flag
}
enforce {
    entity:      Model
    constraints: [MseFloor]
}
arbiter Gov {
    acceptable_evolution:  []
    never_acceptable:      []
    requires_human_review: []
}
"""


class TestBoundRuleValidation:

    def test_valid_bound_rule_ir(self):
        ok, errors, ir = _validate(_BOUND_RULE_VALID)
        assert ok, errors
        rule = ir["constraints"]["MseFloor"]["rule"]
        assert rule["kind"] == "bound_rule"
        assert rule["ref"] == "Model.mse"
        assert rule["op"] == "<"
        assert rule["value"] == 0.8

    def test_bound_rule_ge_valid(self):
        source = _BOUND_RULE_VALID.replace("must remain < 0.8", "must remain >= 0.2")
        ok, errors, _ = _validate(source)
        assert ok, errors

    def test_bound_rule_le_valid(self):
        source = _BOUND_RULE_VALID.replace("must remain < 0.8", "must remain <= 0.8")
        ok, errors, _ = _validate(source)
        assert ok, errors

    def test_bound_rule_gt_valid(self):
        source = _BOUND_RULE_VALID.replace("must remain < 0.8", "must remain > 0.2")
        ok, errors, _ = _validate(source)
        assert ok, errors

    def test_bound_op_eq_rejected(self):
        source = _BOUND_RULE_VALID.replace("must remain < 0.8", "must remain == 0.5")
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("==" in e for e in errors)

    def test_bound_op_neq_rejected(self):
        source = _BOUND_RULE_VALID.replace("must remain < 0.8", "must remain != 0.5")
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("!=" in e for e in errors)


class TestArbiterRequired:

    def test_arbiter_present_passes(self):
        ok, errors, _ = _validate(_MINIMAL_WITH_ARBITER)
        assert ok, errors

    def test_arbiter_missing_fails_validation(self):
        ok, errors, _ = _validate(_MINIMAL_WITHOUT_ARBITER)
        assert not ok
        assert any("Arbiter block is required" in e for e in errors)

    def test_arbiter_library_domain_no_arbiter_ok(self):
        # Primary has arbiter; library domain does not — should pass
        ok, errors, _ = _validate(_MULTI_WITH_ARBITER_IN_PRIMARY)
        assert ok, errors

    def test_arbiter_library_domain_only_fails(self):
        # Library has arbiter, primary does not — should fail
        ok, errors, _ = _validate(_MULTI_WITH_ARBITER_IN_LIBRARY_ONLY)
        assert not ok
        assert any("Arbiter block is required" in e for e in errors)
