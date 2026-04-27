"""Pi Script M1 parser tests."""

import os
import tempfile
from pathlib import Path

import pytest

from pi_script.parser import parse_file, parse_string

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
TASKS_PI = EXAMPLES_DIR / "tasks.pi"


class TestM1Gate:
    def test_tasks_pi_parses_without_error(self):
        """M1 gate: examples/tasks.pi produces a clean parse tree."""
        tree, error = parse_file(TASKS_PI)
        assert error is None, f"Parse failed:\n{error}"
        assert tree is not None

    def test_parse_tree_contains_domain_decl(self):
        """Parse tree root has exactly one domain_decl child."""
        tree, _ = parse_file(TASKS_PI)
        domain_nodes = [c for c in tree.children if hasattr(c, "data") and c.data == "domain_decl"]
        assert len(domain_nodes) == 1

    def test_invalid_syntax_returns_error_not_exception(self):
        """Malformed Pi Script surfaces a human-readable error instead of raising."""
        bad_source = "domain {}"  # missing domain name — parse error
        tree, error = parse_string(bad_source, source_name="<test>")
        assert tree is None, "Expected parse to fail on malformed input"
        assert error is not None, "Expected an error message"
        assert isinstance(error, str) and len(error) > 0
