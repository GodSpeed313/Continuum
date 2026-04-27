"""
test_trace.py — Tests for pi_script/trace.py

Three test classes:
    TestBuildTrace   — structural correctness of build_trace output
    TestRenderTrace  — format correctness of render_trace output
    TestHumanText    — gate condition field verification

Gate condition (Section 3.1):
    A non-expert must be able to read a RESOLUTION TRACE and understand
    why the system acted. If they cannot, the trace format is broken, not the person.
"""

import unittest
from pi_script.trace import build_trace, render_trace, human_text


# ── Shared fixtures ──────────────────────────────────────────────────────────

def _satisfied_constraint(name="TempInBounds", rule_kind="range_rule"):
    return {
        "name":       name,
        "priority":   "critical",
        "status":     "satisfied",
        "rule_kind":  rule_kind,
        "evaluation": "tone_score 0.72 within range(0.4 .. 1.0)",
        "map_match":  None,
        "action":     None,
    }


def _violated_constraint(
    name="MaintainTone",
    rule_kind="range_rule",
    priority="high",
    action="warn",
    evaluation="tone_score 0.31 < range floor 0.4",
):
    return {
        "name":       name,
        "priority":   priority,
        "status":     "violated",
        "rule_kind":  rule_kind,
        "evaluation": evaluation,
        "map_match":  None,
        "action":     action,
    }


def _suspended_constraint(name="PolicyVersionCurrent"):
    return {
        "name":       name,
        "priority":   "critical",
        "status":     "suspended",
        "rule_kind":  "equality_rule",
        "evaluation": "state field unavailable",
        "map_match":  None,
        "action":     None,
    }


def _base_data(constraints, final_action=None, system_state="running",
               conflict_resolution=None):
    return {
        "domain":              "ai_governance",
        "entity":              "CustomerServiceAgent",
        "session_id":          "abc-4421",
        "trigger_type":        "event",
        "triggered_by":        "tone_score changed to 0.31",
        "timestamp":           "2026-04-21T14:32:07.000Z",
        "constraints":         constraints,
        "conflict_resolution": conflict_resolution,
        "final_action":        final_action,
        "system_state":        system_state,
    }


# ── TestBuildTrace ───────────────────────────────────────────────────────────

class TestBuildTrace(unittest.TestCase):
    """Structural correctness of build_trace output."""

    def setUp(self):
        self.data = _base_data(
            constraints=[_satisfied_constraint()],
            system_state="running",
        )
        self.trace = build_trace(self.data)

    def test_all_required_fields_present(self):
        """All Section 3.1 required fields must appear in the trace dict."""
        required = [
            "timestamp", "domain", "entity", "trigger_type",
            "triggered_by", "constraints", "final_action",
            "system_state", "human_text",
        ]
        for field in required:
            self.assertIn(field, self.trace, f"Missing required field: {field}")

    def test_human_text_is_non_empty_string(self):
        """human_text must always be a non-empty string."""
        ht = self.trace["human_text"]
        self.assertIsInstance(ht, str)
        self.assertGreater(len(ht.strip()), 0)

    def test_timestamp_generated_if_absent(self):
        """If timestamp not provided, build_trace generates one."""
        data = _base_data(constraints=[_satisfied_constraint()])
        data.pop("timestamp", None)
        trace = build_trace(data)
        self.assertIn("timestamp", trace)
        self.assertIsInstance(trace["timestamp"], str)
        self.assertGreater(len(trace["timestamp"]), 0)

    def test_session_id_in_entity_label(self):
        """session_id must appear in the entity label when present."""
        self.assertIn("abc-4421", self.trace["entity"])
        self.assertIn("CustomerServiceAgent", self.trace["entity"])

    def test_no_session_id_entity_label_clean(self):
        """Entity label without session_id should just be the entity name."""
        data = _base_data(constraints=[_satisfied_constraint()])
        data["session_id"] = None
        trace = build_trace(data)
        self.assertEqual(trace["entity"], "CustomerServiceAgent")

    def test_constraint_blocks_all_present(self):
        """One constraint block per evaluated constraint."""
        constraints = [
            _satisfied_constraint("C1"),
            _violated_constraint("C2"),
        ]
        data = _base_data(constraints=constraints, final_action="warn")
        trace = build_trace(data)
        self.assertEqual(len(trace["constraints"]), 2)
        names = [c["name"] for c in trace["constraints"]]
        self.assertIn("C1", names)
        self.assertIn("C2", names)

    def test_suspended_constraint_does_not_crash(self):
        """Suspended constraints must be handled without raising an exception."""
        data = _base_data(
            constraints=[
                _satisfied_constraint(),
                _suspended_constraint(),
            ]
        )
        try:
            trace = build_trace(data)
            self.assertIn("human_text", trace)
        except Exception as e:
            self.fail(f"build_trace raised an exception on suspended constraint: {e}")

    def test_conflict_resolution_field_present(self):
        """conflict_resolution field must appear in trace dict."""
        self.assertIn("conflict_resolution", self.trace)

    def test_json_serializable(self):
        """Trace dict must be JSON-serializable."""
        import json
        try:
            json.dumps(self.trace)
        except TypeError as e:
            self.fail(f"Trace dict is not JSON-serializable: {e}")


# ── TestRenderTrace ──────────────────────────────────────────────────────────

class TestRenderTrace(unittest.TestCase):
    """Format correctness of render_trace output."""

    def setUp(self):
        satisfied = _satisfied_constraint()
        violated = _violated_constraint()
        data = _base_data(
            constraints=[satisfied, violated],
            final_action="warn",
            system_state="running",
        )
        self.trace = build_trace(data)
        self.rendered = render_trace(self.trace)

    def test_returns_string(self):
        self.assertIsInstance(self.rendered, str)

    def test_contains_resolution_trace_header(self):
        self.assertIn("RESOLUTION TRACE", self.rendered)

    def test_contains_resolution_footer(self):
        self.assertIn("RESOLUTION", self.rendered)

    def test_contains_satisfied_for_passing_constraint(self):
        self.assertIn("SATISFIED", self.rendered)

    def test_contains_violation_for_failing_constraint(self):
        self.assertIn("VIOLATION", self.rendered)

    def test_contains_entity_name(self):
        self.assertIn("CustomerServiceAgent", self.rendered)

    def test_contains_domain(self):
        self.assertIn("ai_governance", self.rendered)

    def test_contains_human_text(self):
        """The human_text field must appear somewhere in the rendered output."""
        ht = self.trace["human_text"]
        self.assertIn(ht[:40], self.rendered)

    def test_contains_conflict_resolution_when_present(self):
        """CONFLICT RESOLUTION section appears when conflict_resolution is set."""
        constraints = [
            _violated_constraint("C1", priority="critical", action="freeze"),
            _violated_constraint("C2", priority="critical", action="flag + escalate"),
        ]
        data = _base_data(
            constraints=constraints,
            final_action="freeze",
            system_state="frozen",
            conflict_resolution="Two critical violations. freeze selected as most restrictive action.",
        )
        trace = build_trace(data)
        rendered = render_trace(trace)
        self.assertIn("CONFLICT RESOLUTION", rendered)


# ── TestHumanText ────────────────────────────────────────────────────────────

class TestHumanText(unittest.TestCase):
    """
    Gate condition verification.

    Each test checks that human_text produces language that is:
    - Free of jargon
    - Explains what happened
    - Explains what the system did in response
    - Understandable without knowledge of Pi Script
    """

    def test_all_satisfied_no_action_mentioned(self):
        """All satisfied → human text must say no action was taken."""
        data = _base_data(constraints=[
            _satisfied_constraint("C1"),
            _satisfied_constraint("C2"),
        ])
        ht = human_text(data)
        self.assertIn("no action", ht.lower())

    def test_all_satisfied_mentions_passed(self):
        """All satisfied → human text must indicate rules passed."""
        data = _base_data(constraints=[_satisfied_constraint()])
        ht = human_text(data)
        self.assertTrue(
            "passed" in ht.lower() or "acceptable" in ht.lower() or "within" in ht.lower(),
            f"Expected 'passed' or 'acceptable' in human_text, got: {ht}"
        )

    def test_single_range_violation_mentions_constraint_name(self):
        """Single range violation → constraint name must appear in human text."""
        data = _base_data(
            constraints=[_violated_constraint("MaintainTone", rule_kind="range_rule")],
            final_action="warn",
            system_state="running",
        )
        ht = human_text(data)
        self.assertIn("MaintainTone", ht)

    def test_single_range_violation_mentions_action(self):
        """Single range violation → action must be explained in plain English."""
        data = _base_data(
            constraints=[_violated_constraint(action="warn")],
            final_action="warn",
            system_state="running",
        )
        ht = human_text(data)
        self.assertTrue(
            "warning" in ht.lower() or "operator" in ht.lower(),
            f"Expected action explanation in human_text, got: {ht}"
        )

    def test_critical_contradiction_mentions_frozen(self):
        """Critical contradiction → human text must mention frozen/paused."""
        v = _violated_constraint(
            name="NeverContradictPolicy",
            rule_kind="contradiction_rule",
            priority="critical",
            action="freeze + rollback",
        )
        data = _base_data(
            constraints=[v],
            final_action="freeze + rollback",
            system_state="frozen",
        )
        ht = human_text(data)
        self.assertTrue(
            "frozen" in ht.lower() or "paused" in ht.lower(),
            f"Expected 'frozen' or 'paused' in human_text, got: {ht}"
        )

    def test_critical_contradiction_mentions_human_review(self):
        """Critical contradiction → human text must mention human review."""
        v = _violated_constraint(
            name="NeverContradictPolicy",
            rule_kind="contradiction_rule",
            priority="critical",
            action="flag + escalate",
        )
        data = _base_data(
            constraints=[v],
            final_action="flag + escalate",
            system_state="escalated",
        )
        ht = human_text(data)
        self.assertTrue(
            "human" in ht.lower() or "review" in ht.lower() or "reviewer" in ht.lower(),
            f"Expected human review mention in human_text, got: {ht}"
        )

    def test_two_simultaneous_critical_violations_mentions_both(self):
        """Two critical violations → both constraint names must appear in human text."""
        constraints = [
            _violated_constraint("NeverContradictPolicy", priority="critical",
                                 rule_kind="contradiction_rule", action="freeze"),
            _violated_constraint("PolicyVersionCurrent", priority="critical",
                                 rule_kind="equality_rule", action="freeze + rollback"),
        ]
        data = _base_data(
            constraints=constraints,
            final_action="freeze + rollback",
            system_state="frozen",
            conflict_resolution="Two critical violations. freeze + rollback selected.",
        )
        ht = human_text(data)
        self.assertIn("NeverContradictPolicy", ht)
        self.assertIn("PolicyVersionCurrent", ht)

    def test_two_simultaneous_critical_violations_mentions_strictest(self):
        """Two critical violations → human text must explain strictest action applied."""
        constraints = [
            _violated_constraint("C1", priority="critical", action="freeze"),
            _violated_constraint("C2", priority="critical", action="flag + escalate"),
        ]
        data = _base_data(
            constraints=constraints,
            final_action="freeze",
            system_state="frozen",
        )
        ht = human_text(data)
        self.assertTrue(
            "strict" in ht.lower() or "serious" in ht.lower() or "critical" in ht.lower(),
            f"Expected strictness language in human_text, got: {ht}"
        )

    def test_suspended_constraint_note_appears(self):
        """Suspended constraint → suspension note must appear in human text."""
        data = _base_data(
            constraints=[
                _satisfied_constraint(),
                _suspended_constraint("PolicyVersionCurrent"),
            ]
        )
        ht = human_text(data)
        self.assertTrue(
            "not available" in ht.lower() or "paused" in ht.lower() or "could not" in ht.lower(),
            f"Expected suspension note in human_text, got: {ht}"
        )

    def test_no_jargon_in_satisfied_case(self):
        """Satisfied case must not contain Pi Script-specific jargon."""
        data = _base_data(constraints=[_satisfied_constraint()])
        ht = human_text(data)
        jargon = ["constraint_decl", "rule_expr", "c_priority", "lark", "ir", "decay_check"]
        for term in jargon:
            self.assertNotIn(term, ht.lower(), f"Jargon term '{term}' found in human_text: {ht}")

    def test_no_jargon_in_violation_case(self):
        """Violation case must not contain Pi Script-specific jargon."""
        data = _base_data(
            constraints=[_violated_constraint()],
            final_action="warn",
            system_state="running",
        )
        ht = human_text(data)
        jargon = ["constraint_decl", "rule_expr", "c_priority", "lark", "ir", "decay_check"]
        for term in jargon:
            self.assertNotIn(term, ht.lower(), f"Jargon term '{term}' found in human_text: {ht}")

    def test_empty_constraints_list(self):
        """Empty constraints list must not crash and must return a sensible message."""
        data = _base_data(constraints=[])
        try:
            ht = human_text(data)
            self.assertIsInstance(ht, str)
            self.assertGreater(len(ht.strip()), 0)
        except Exception as e:
            self.fail(f"human_text raised on empty constraints: {e}")

    def test_heartbeat_trigger_handled(self):
        """Heartbeat trigger type must not crash trace generation."""
        data = _base_data(constraints=[_satisfied_constraint()])
        data["trigger_type"] = "heartbeat"
        data["triggered_by"] = "decay_check interval elapsed — no new state arrived"
        try:
            trace = build_trace(data)
            self.assertIn("human_text", trace)
        except Exception as e:
            self.fail(f"build_trace raised on heartbeat trigger: {e}")


if __name__ == "__main__":
    unittest.main()
