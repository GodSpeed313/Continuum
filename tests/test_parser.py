"""Pi Script M1 + M3 parser tests."""

import os
import tempfile
from pathlib import Path

import pytest

from pi_script.parser import parse_file, parse_string
from pi_script.validator import PiValidator

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
TASKS_PI     = EXAMPLES_DIR / "tasks.pi"
HAPPY_PI     = EXAMPLES_DIR / "test_happy.pi"


class TestM1Gate:
    def test_tasks_pi_parses_without_error(self):
        """M1 gate: examples/tasks.pi produces a clean parse tree."""
        tree, error = parse_file(TASKS_PI)
        assert error is None, f"Parse failed:\n{error}"
        assert tree is not None

    def test_parse_tree_contains_domain_decl(self):
        """Parse tree root has one domain_section whose first child is a domain_decl."""
        tree, _ = parse_file(TASKS_PI)
        section_nodes = [c for c in tree.children if hasattr(c, "data") and c.data == "domain_section"]
        assert len(section_nodes) >= 1
        first_section = section_nodes[0]
        assert first_section.children[0].data == "domain_decl"

    def test_invalid_syntax_returns_error_not_exception(self):
        """Malformed Pi Script surfaces a human-readable error instead of raising."""
        bad_source = "domain {}"  # missing domain name — parse error
        tree, error = parse_string(bad_source, source_name="<test>")
        assert tree is None, "Expected parse to fail on malformed input"
        assert error is not None, "Expected an error message"
        assert isinstance(error, str) and len(error) > 0


class TestM3Valid:
    def test_happy_pi_parses(self):
        tree, error = parse_file(HAPPY_PI)
        assert error is None, f"Parse failed:\n{error}"
        assert tree is not None

    def test_tasks_pi_parses(self):
        tree, error = parse_file(TASKS_PI)
        assert error is None, f"Parse failed:\n{error}"
        assert tree is not None


class TestM3Failures:
    def test_missing_domain_fails(self):
        source = """\
entity Agent {
    score: integer
}
"""
        tree, error = parse_string(source, source_name="<test>")
        assert tree is None, "Expected parse to fail with no domain declaration"
        assert error is not None
        assert isinstance(error, str) and len(error) > 0

    def test_duplicate_domain_fails(self):
        # Ruling 9.5: multiple domain sections are valid syntax; the validator
        # rejects same-name duplicates. Different names parse cleanly.
        source = """\
domain first_domain {
    audit_interval: 1 hours
    tiebreaker: timestamp_asc
}
domain first_domain {
    audit_interval: 1 hours
    tiebreaker: timestamp_asc
}
"""
        tree, error = parse_string(source, source_name="<test>")
        assert tree is not None, "Multi-domain is valid syntax"
        assert error is None
        ok, errors, _ = PiValidator(tree).validate()
        assert not ok
        assert any("first_domain" in e for e in errors)

    def test_undeclared_entity_in_constraint_fails(self):
        # Syntactically valid — parser accepts it. Semantically invalid — validator
        # rejects it. Tests the full pipeline. Already covered in TestM2Failures
        # but included here to confirm end-to-end rejection with a human-readable error.
        source = """\
domain test_domain {
    audit_interval: 1 hours
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
        tree, parse_error = parse_string(source, source_name="<test>")
        assert tree is not None, "Parser should accept syntactically valid source"
        assert parse_error is None
        ok, errors, _ = PiValidator(tree).validate()
        assert not ok
        assert any("Ghost" in e for e in errors)

    def test_enforce_shape_a_rejected(self):
        source = """\
domain test_domain {
    audit_interval: 1 hours
}
entity Agent {
    score: integer
}
enforce {
    on: Agent
    constraints: [SomeConstraint]
}
"""
        tree, error = parse_string(source, source_name="<test>")
        assert tree is None, "Shape A enforce syntax must be rejected by parser"
        assert error is not None
