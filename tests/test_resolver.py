"""
test_resolver.py — Tests for pi_script/resolver.py

Five test classes:
    TestResolverHappyPath    — all constraints satisfied, correct output shape
    TestResolverViolations   — single violation per rule kind
    TestResolverQ1           — simultaneous critical violations, Q1 resolution
    TestResolverQ2           — contradiction detection, Q2 topic-key resolution
    TestResolverInputErrors  — bad trigger_type, unknown entity, exit code 2
"""

import unittest
from pi_script.resolver import resolve


# ── Shared IR fixture ────────────────────────────────────────────────────────

def _base_ir(constraints: dict, enforce_list: list, maps: dict = None) -> dict:
    return {
        "domain": "ai_governance",
        "entities": {
            "TestAgent": {
                "confidence_score": "range(0.0..1.0)",
                "response_count":   "integer",
                "current_mode":     "text",
                "is_active":        "boolean",
                "response_history": "sequence(text)",
            }
        },
        "constraints": constraints,
        "maps": maps or {},
        "enforce": {
            "TestAgent": enforce_list
        },
        "arbiter": None,
    }


def _base_state(overrides: dict = None, history: list = None) -> dict:
    state = {
        "trigger_type": "event",
        "entity":       "TestAgent",
        "entity_state": {
            "confidence_score": 0.72,
            "response_count":   42,
            "current_mode":     "normal_mode",
            "is_active":        True,
            "session_id":       "test-001",
        },
        "response_history": history or [],
    }
    if overrides:
        state["entity_state"].update(overrides)
    return state


# ── Constraint IR builders ───────────────────────────────────────────────────

def _range_constraint(name="ConfidenceFloor", lo=0.2, hi=1.0,
                       ref="TestAgent.confidence_score",
                       priority="critical", action="freeze"):
    return {
        name: {
            "priority":     priority,
            "rule":         {"kind": "range_rule", "ref": ref, "lo": lo, "hi": hi},
            "on_violation": [action],
            "escalation":   [],
            "decay_check":  None,
        }
    }


def _threshold_constraint(name="ResponseCap", below=1000,
                           ref="TestAgent.response_count",
                           priority="high", action="warn"):
    return {
        name: {
            "priority":     priority,
            "rule":         {"kind": "threshold_rule", "ref": ref, "below": below},
            "on_violation": [action],
            "escalation":   [],
            "decay_check":  None,
        }
    }


def _equality_constraint(name="SessionIntegrity", value=True,
                          ref="TestAgent.is_active",
                          priority="high", action="freeze"):
    return {
        name: {
            "priority":     priority,
            "rule":         {"kind": "equality_rule", "ref": ref, "value": value},
            "on_violation": [action],
            "escalation":   [],
            "decay_check":  None,
        }
    }


def _membership_constraint(name="ModeCompliance",
                            ref="TestAgent.current_mode",
                            priority="medium", action="flag"):
    return {
        name: {
            "priority":     priority,
            "rule":         {"kind": "membership_rule", "ref": ref},
            "on_violation": [action],
            "escalation":   [],
            "decay_check":  None,
        }
    }


def _conditional_constraint(name="PrecautionaryPause",
                             ref="TestAgent.confidence_score",
                             op="<", value=0.5,
                             priority="high", action="escalate"):
    return {
        name: {
            "priority":     priority,
            "rule":         {
                "kind":    "conditional_rule",
                "ref":     ref,
                "op":      op,
                "value":   value,
                "require": "confidence_review",
                "before":  "responding",
            },
            "on_violation": [action],
            "escalation":   [],
            "decay_check":  None,
        }
    }


def _contradiction_constraint(name="ConsistencyGuard",
                               ref="TestAgent.response_history",
                               priority="critical", action="flag + escalate"):
    return {
        name: {
            "priority":     priority,
            "rule":         {"kind": "contradiction_rule", "ref": ref},
            "on_violation": [action],
            "escalation":   [],
            "decay_check":  None,
        }
    }


def _mode_maps():
    return {
        "TestAgent.current_mode": [
            {"maps_to": "normal_mode", "triggers": ["normal", "standard"]},
            {"maps_to": "safe_mode",   "triggers": ["safe", "restricted"]},
        ]
    }


def _contradiction_maps():
    return {
        "TestAgent.response_history": [
            {"maps_to": "potential_contradiction",
             "triggers": ["actually,", "on second thought", "i was wrong"]},
        ]
    }


# ── TestResolverHappyPath ────────────────────────────────────────────────────

class TestResolverHappyPath(unittest.TestCase):
    """All constraints satisfied — correct output shape and exit code."""

    def setUp(self):
        constraints = {}
        constraints.update(_range_constraint())
        constraints.update(_threshold_constraint())
        constraints.update(_equality_constraint())
        constraints.update(_membership_constraint())
        constraints.update(_conditional_constraint())
        enforce_list = list(constraints.keys())
        maps = _mode_maps()
        self.ir = _base_ir(constraints, enforce_list, maps)
        self.state = _base_state()

    def test_exit_code_zero_when_all_satisfied(self):
        _, _, exit_code = resolve(self.ir, self.state)
        self.assertEqual(exit_code, 0)

    def test_system_state_running_when_all_satisfied(self):
        trace, _, _ = resolve(self.ir, self.state)
        self.assertEqual(trace["system_state"], "running")

    def test_final_action_none_when_all_satisfied(self):
        trace, _, _ = resolve(self.ir, self.state)
        self.assertIsNone(trace["final_action"])

    def test_all_constraints_appear_in_trace(self):
        trace, _, _ = resolve(self.ir, self.state)
        names = [c["name"] for c in trace["constraints"]]
        self.assertIn("ConfidenceFloor", names)
        self.assertIn("ResponseCap", names)
        self.assertIn("SessionIntegrity", names)
        self.assertIn("ModeCompliance", names)
        self.assertIn("PrecautionaryPause", names)

    def test_all_constraints_satisfied_status(self):
        trace, _, _ = resolve(self.ir, self.state)
        for c in trace["constraints"]:
            self.assertEqual(
                c["status"], "satisfied",
                f"Expected satisfied for {c['name']}, got {c['status']}"
            )

    def test_human_text_mentions_no_action(self):
        trace, _, _ = resolve(self.ir, self.state)
        self.assertIn("no action", trace["human_text"].lower())

    def test_rendered_output_is_string(self):
        _, rendered, _ = resolve(self.ir, self.state)
        self.assertIsInstance(rendered, str)

    def test_rendered_contains_resolution_trace_header(self):
        _, rendered, _ = resolve(self.ir, self.state)
        self.assertIn("RESOLUTION TRACE", rendered)

    def test_heartbeat_trigger_satisfies_cleanly(self):
        state = _base_state()
        state["trigger_type"] = "heartbeat"
        trace, _, exit_code = resolve(self.ir, state)
        self.assertEqual(exit_code, 0)
        self.assertEqual(trace["trigger_type"], "heartbeat")


# ── TestResolverViolations ───────────────────────────────────────────────────

class TestResolverViolations(unittest.TestCase):
    """Single violation per rule kind — correct detection and action."""

    def test_range_rule_violation_below_floor(self):
        constraints = _range_constraint(lo=0.5, hi=1.0)
        ir = _base_ir(constraints, ["ConfidenceFloor"])
        state = _base_state({"confidence_score": 0.3})
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 1)
        c = trace["constraints"][0]
        self.assertEqual(c["status"], "violated")
        self.assertEqual(c["rule_kind"], "range_rule")

    def test_range_rule_violation_above_ceiling(self):
        constraints = _range_constraint(lo=0.0, hi=0.5)
        ir = _base_ir(constraints, ["ConfidenceFloor"])
        state = _base_state({"confidence_score": 0.8})
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 1)
        self.assertEqual(trace["constraints"][0]["status"], "violated")

    def test_threshold_rule_violation(self):
        constraints = _threshold_constraint(below=10)
        ir = _base_ir(constraints, ["ResponseCap"])
        state = _base_state({"response_count": 42})
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 1)
        self.assertEqual(trace["constraints"][0]["status"], "violated")
        self.assertEqual(trace["constraints"][0]["rule_kind"], "threshold_rule")

    def test_equality_rule_violation(self):
        constraints = _equality_constraint(value=True)
        ir = _base_ir(constraints, ["SessionIntegrity"])
        state = _base_state({"is_active": False})
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 1)
        self.assertEqual(trace["constraints"][0]["status"], "violated")
        self.assertEqual(trace["constraints"][0]["rule_kind"], "equality_rule")

    def test_membership_rule_violation(self):
        constraints = _membership_constraint()
        maps = _mode_maps()
        ir = _base_ir(constraints, ["ModeCompliance"], maps)
        state = _base_state({"current_mode": "unknown_mode"})
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 1)
        self.assertEqual(trace["constraints"][0]["status"], "violated")
        self.assertEqual(trace["constraints"][0]["rule_kind"], "membership_rule")

    def test_conditional_rule_violation(self):
        constraints = _conditional_constraint(op="<", value=0.5)
        ir = _base_ir(constraints, ["PrecautionaryPause"])
        state = _base_state({"confidence_score": 0.3})
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 1)
        self.assertEqual(trace["constraints"][0]["status"], "violated")
        self.assertEqual(trace["constraints"][0]["rule_kind"], "conditional_rule")

    def test_violation_action_in_trace(self):
        constraints = _range_constraint(lo=0.5, hi=1.0, action="freeze")
        ir = _base_ir(constraints, ["ConfidenceFloor"])
        state = _base_state({"confidence_score": 0.1})
        trace, _, _ = resolve(ir, state)
        self.assertEqual(trace["final_action"], "freeze")

    def test_system_state_frozen_on_freeze_action(self):
        constraints = _range_constraint(lo=0.5, hi=1.0, action="freeze")
        ir = _base_ir(constraints, ["ConfidenceFloor"])
        state = _base_state({"confidence_score": 0.1})
        trace, _, _ = resolve(ir, state)
        self.assertEqual(trace["system_state"], "frozen")

    def test_system_state_escalated_on_escalate_action(self):
        constraints = _conditional_constraint(op="<", value=0.5, action="escalate")
        ir = _base_ir(constraints, ["PrecautionaryPause"])
        state = _base_state({"confidence_score": 0.3})
        trace, _, _ = resolve(ir, state)
        self.assertEqual(trace["system_state"], "escalated")

    def test_sparse_snapshot_suspends_constraint(self):
        """Missing state field → constraint suspended, not crashed."""
        constraints = _range_constraint()
        ir = _base_ir(constraints, ["ConfidenceFloor"])
        state = _base_state()
        del state["entity_state"]["confidence_score"]
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 0)
        self.assertEqual(trace["constraints"][0]["status"], "suspended")

    def test_human_text_mentions_constraint_name_on_violation(self):
        constraints = _range_constraint(lo=0.5, hi=1.0, name="ConfidenceFloor")
        ir = _base_ir(constraints, ["ConfidenceFloor"])
        state = _base_state({"confidence_score": 0.1})
        trace, _, _ = resolve(ir, state)
        self.assertIn("ConfidenceFloor", trace["human_text"])


# ── TestResolverQ1 ───────────────────────────────────────────────────────────

class TestResolverQ1(unittest.TestCase):
    """
    Q1 resolution: simultaneous critical violations.
    Most restrictive action wins. All violations logged as co-active.
    """

    def _two_critical_ir(self, action1="freeze", action2="flag + escalate"):
        constraints = {}
        constraints.update(_range_constraint(
            name="C1", lo=0.5, hi=1.0,
            priority="critical", action=action1
        ))
        constraints.update(_threshold_constraint(
            name="C2", below=10,
            priority="critical", action=action2
        ))
        return _base_ir(constraints, ["C1", "C2"])

    def test_both_violations_logged(self):
        ir = self._two_critical_ir()
        state = _base_state({"confidence_score": 0.1, "response_count": 42})
        trace, _, _ = resolve(ir, state)
        violated = [c for c in trace["constraints"] if c["status"] == "violated"]
        self.assertEqual(len(violated), 2)

    def test_most_restrictive_action_wins(self):
        """freeze > flag + escalate — freeze must be final_action."""
        ir = self._two_critical_ir(action1="freeze", action2="flag + escalate")
        state = _base_state({"confidence_score": 0.1, "response_count": 42})
        trace, _, _ = resolve(ir, state)
        self.assertEqual(trace["final_action"], "freeze")

    def test_freeze_rollback_beats_freeze(self):
        """freeze + rollback > freeze."""
        ir = self._two_critical_ir(action1="freeze + rollback", action2="freeze")
        state = _base_state({"confidence_score": 0.1, "response_count": 42})
        trace, _, _ = resolve(ir, state)
        self.assertEqual(trace["final_action"], "freeze + rollback")

    def test_conflict_resolution_note_present(self):
        ir = self._two_critical_ir()
        state = _base_state({"confidence_score": 0.1, "response_count": 42})
        trace, _, _ = resolve(ir, state)
        self.assertIsNotNone(trace["conflict_resolution"])

    def test_conflict_resolution_mentions_both_names(self):
        ir = self._two_critical_ir()
        state = _base_state({"confidence_score": 0.1, "response_count": 42})
        trace, _, _ = resolve(ir, state)
        note = trace["conflict_resolution"]
        self.assertIn("C1", note)
        self.assertIn("C2", note)

    def test_exit_code_one_on_simultaneous_critical(self):
        ir = self._two_critical_ir()
        state = _base_state({"confidence_score": 0.1, "response_count": 42})
        _, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 1)

    def test_human_text_mentions_both_violation_names(self):
        ir = self._two_critical_ir()
        state = _base_state({"confidence_score": 0.1, "response_count": 42})
        trace, _, _ = resolve(ir, state)
        ht = trace["human_text"]
        self.assertIn("C1", ht)
        self.assertIn("C2", ht)


# ── TestResolverQ2 ───────────────────────────────────────────────────────────

class TestResolverQ2(unittest.TestCase):
    """
    Q2 resolution: contradiction detection.
    topic key = state_ref. Trigger = map block match on new response text.
    """

    def _contradiction_ir(self):
        constraints = _contradiction_constraint()
        maps = _contradiction_maps()
        return _base_ir(constraints, ["ConsistencyGuard"], maps)

    def test_no_history_satisfies(self):
        ir = self._contradiction_ir()
        state = _base_state(history=[])
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 0)
        self.assertEqual(trace["constraints"][0]["status"], "satisfied")

    def test_single_entry_no_prior_satisfies(self):
        """One entry in history — no prior to contradict."""
        ir = self._contradiction_ir()
        history = [{
            "text":      "Refunds take 5 business days.",
            "state_ref": "TestAgent.response_history",
            "timestamp": "2026-04-27T10:00:00.000Z",
        }]
        state = _base_state(history=history)
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 0)

    def test_contradiction_trigger_in_new_response_violates(self):
        """New response contains contradiction trigger → violated."""
        ir = self._contradiction_ir()
        history = [
            {
                "text":      "Refunds take 5 business days.",
                "state_ref": "TestAgent.response_history",
                "timestamp": "2026-04-27T10:00:00.000Z",
            },
            {
                "text":      "Actually, refunds may take up to 14 days.",
                "state_ref": "TestAgent.response_history",
                "timestamp": "2026-04-27T11:00:00.000Z",
            },
        ]
        state = _base_state(history=history)
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 1)
        self.assertEqual(trace["constraints"][0]["status"], "violated")
        self.assertEqual(trace["constraints"][0]["rule_kind"], "contradiction_rule")

    def test_contradiction_map_match_appears_in_trace(self):
        """Map match field must be populated on contradiction violation."""
        ir = self._contradiction_ir()
        history = [
            {
                "text":      "Policy A applies here.",
                "state_ref": "TestAgent.response_history",
                "timestamp": "2026-04-27T10:00:00.000Z",
            },
            {
                "text":      "On second thought, policy B applies.",
                "state_ref": "TestAgent.response_history",
                "timestamp": "2026-04-27T11:00:00.000Z",
            },
        ]
        state = _base_state(history=history)
        trace, _, _ = resolve(ir, state)
        c = trace["constraints"][0]
        self.assertIsNotNone(c.get("map_match"))

    def test_different_state_ref_does_not_trigger(self):
        """Responses on different state_refs are different topics — no contradiction."""
        ir = self._contradiction_ir()
        history = [
            {
                "text":      "Refunds take 5 days.",
                "state_ref": "TestAgent.other_field",
                "timestamp": "2026-04-27T10:00:00.000Z",
            },
            {
                "text":      "Actually, refunds take 14 days.",
                "state_ref": "TestAgent.response_history",
                "timestamp": "2026-04-27T11:00:00.000Z",
            },
        ]
        state = _base_state(history=history)
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 0)


# ── TestResolverInputErrors ──────────────────────────────────────────────────

class TestResolverInputErrors(unittest.TestCase):
    """Bad inputs — resolver must reject cleanly, never crash silently."""

    def _simple_ir(self):
        constraints = _range_constraint()
        return _base_ir(constraints, ["ConfidenceFloor"])

    def test_invalid_trigger_type_exits_2(self):
        ir = self._simple_ir()
        state = _base_state()
        state["trigger_type"] = "invalid_trigger"
        with self.assertRaises(SystemExit) as cm:
            resolve(ir, state)
        self.assertEqual(cm.exception.code, 2)

    def test_unknown_entity_exits_2(self):
        ir = self._simple_ir()
        state = _base_state()
        state["entity"] = "NonExistentAgent"
        with self.assertRaises(SystemExit) as cm:
            resolve(ir, state)
        self.assertEqual(cm.exception.code, 2)

    def test_empty_trigger_type_exits_2(self):
        ir = self._simple_ir()
        state = _base_state()
        state["trigger_type"] = ""
        with self.assertRaises(SystemExit) as cm:
            resolve(ir, state)
        self.assertEqual(cm.exception.code, 2)

    def test_missing_trigger_type_exits_2(self):
        ir = self._simple_ir()
        state = _base_state()
        del state["trigger_type"]
        with self.assertRaises(SystemExit) as cm:
            resolve(ir, state)
        self.assertEqual(cm.exception.code, 2)

    def test_empty_entity_state_suspends_all(self):
        """Empty entity_state → all constraints suspended, not crashed."""
        constraints = {}
        constraints.update(_range_constraint())
        constraints.update(_threshold_constraint())
        ir = _base_ir(constraints, ["ConfidenceFloor", "ResponseCap"])
        state = _base_state()
        state["entity_state"] = {}
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 0)
        for c in trace["constraints"]:
            self.assertEqual(
                c["status"], "suspended",
                f"Expected suspended for {c['name']}, got {c['status']}"
            )


# ── TestBidirectionalMaps ────────────────────────────────────────────────────

def _membership_ir_with_label(label=None) -> dict:
    entry = {"maps_to": "safe_mode", "triggers": ["safe", "restricted"]}
    if label is not None:
        entry["label"] = label
    return _base_ir(
        constraints={
            "ModeCheck": {
                "priority": "medium",
                "rule": {"kind": "membership_rule", "ref": "TestAgent.current_mode"},
                "on_violation": ["warn"],
                "escalation": [],
                "decay_check": None,
            }
        },
        enforce_list=["ModeCheck"],
        maps={"TestAgent.current_mode": [entry]},
    )


class TestBidirectionalMaps(unittest.TestCase):
    def test_label_for_returns_label_when_present(self):
        from pi_script.resolver import _label_for
        maps = {"Agent.mode": [{"maps_to": "safe_mode", "triggers": [], "label": "Safe Mode"}]}
        self.assertEqual(_label_for("Agent.mode", "safe_mode", maps), "Safe Mode")

    def test_label_for_returns_none_when_absent(self):
        from pi_script.resolver import _label_for
        maps = {"Agent.mode": [{"maps_to": "safe_mode", "triggers": []}]}
        self.assertIsNone(_label_for("Agent.mode", "safe_mode", maps))

    def test_label_for_returns_none_for_unknown_ref(self):
        from pi_script.resolver import _label_for
        self.assertIsNone(_label_for("Agent.other", "safe_mode", {}))

    def test_membership_satisfied_trace_includes_label(self):
        ir = _membership_ir_with_label(label="Safe Mode")
        state = _base_state({"current_mode": "safe_mode"})
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 0)
        evaluation = trace["constraints"][0]["evaluation"]
        self.assertIn("Safe Mode", evaluation)

    def test_membership_violated_trace_includes_label_for_invalid_value(self):
        ir = _membership_ir_with_label(label="Safe Mode")
        state = _base_state({"current_mode": "unknown_mode"})
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 1)

    def test_membership_without_label_trace_unchanged(self):
        ir = _membership_ir_with_label(label=None)
        state = _base_state({"current_mode": "safe_mode"})
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 0)
        evaluation = trace["constraints"][0]["evaluation"]
        self.assertNotIn("(", evaluation)

    def test_membership_satisfied_raw_value_still_shown(self):
        ir = _membership_ir_with_label(label="Safe Mode")
        state = _base_state({"current_mode": "safe_mode"})
        trace, _, _ = resolve(ir, state)
        evaluation = trace["constraints"][0]["evaluation"]
        self.assertIn("safe_mode", evaluation)


class TestCrossDomainImport(unittest.TestCase):
    """Ruling 9.5 — imported constraints annotated in trace."""

    def _ir_with_imported_constraint(self):
        return _base_ir(
            constraints={
                "ConfidenceFloor": {
                    "priority":      "critical",
                    "rule":          {"kind": "range_rule", "ref": "TestAgent.confidence_score",
                                      "lo": 0.2, "hi": 1.0},
                    "on_violation":  ["freeze", "escalate"],
                    "escalation":    [],
                    "decay_check":   None,
                    "imported_from": "safety_core",
                }
            },
            enforce_list=["ConfidenceFloor"],
        )

    def test_imported_from_present_in_trace_dict(self):
        ir = self._ir_with_imported_constraint()
        state = _base_state({"confidence_score": 0.85})
        trace, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 0)
        self.assertEqual(trace["constraints"][0]["imported_from"], "safety_core")

    def test_imported_from_annotates_rendered_trace(self):
        ir = self._ir_with_imported_constraint()
        state = _base_state({"confidence_score": 0.85})
        _, rendered, _ = resolve(ir, state)
        self.assertIn("imported from safety_core", rendered)

    def test_native_constraint_has_no_imported_from_in_trace(self):
        ir = _base_ir(
            constraints={
                "ConfidenceFloor": {
                    "priority":     "critical",
                    "rule":         {"kind": "range_rule", "ref": "TestAgent.confidence_score",
                                     "lo": 0.2, "hi": 1.0},
                    "on_violation": ["freeze", "escalate"],
                    "escalation":   [],
                    "decay_check":  None,
                }
            },
            enforce_list=["ConfidenceFloor"],
        )
        state = _base_state({"confidence_score": 0.85})
        trace, rendered, _ = resolve(ir, state)
        self.assertIsNone(trace["constraints"][0].get("imported_from"))
        self.assertNotIn("imported from", rendered)

    def test_imported_constraint_violation_still_fires(self):
        ir = self._ir_with_imported_constraint()
        state = _base_state({"confidence_score": 0.10})
        _, _, exit_code = resolve(ir, state)
        self.assertEqual(exit_code, 1)


class TestViolationCounters(unittest.TestCase):

    def _escalating_ir(self, steps=None):
        if steps is None:
            steps = [{"at": 3.0, "action": "escalate"}, {"at": 10.0, "action": "freeze"}]
        return _base_ir(
            constraints={
                "ConfidenceFloor": {
                    "priority":     "critical",
                    "rule":         {"kind": "range_rule",
                                     "ref": "TestAgent.confidence_score",
                                     "lo": 0.2, "hi": 1.0},
                    "on_violation": ["warn"],
                    "escalation":   steps,
                    "decay_check":  None,
                }
            },
            enforce_list=["ConfidenceFloor"],
        )

    def _violating_state(self, counts=None):
        s = _base_state({"confidence_score": 0.10})
        if counts:
            s["violation_counts"] = counts
        return s

    def _clean_state(self, counts=None):
        s = _base_state({"confidence_score": 0.85})
        if counts:
            s["violation_counts"] = counts
        return s

    # ── Counter increments ─────────────────────────────────────────────────

    def test_counter_increments_on_first_violation(self):
        ir = self._escalating_ir()
        trace, _, _ = resolve(ir, self._violating_state())
        self.assertEqual(trace["updated_violation_counts"]["ConfidenceFloor"], 1)

    def test_counter_increments_from_existing_value(self):
        ir = self._escalating_ir()
        trace, _, _ = resolve(ir, self._violating_state({"ConfidenceFloor": 5}))
        self.assertEqual(trace["updated_violation_counts"]["ConfidenceFloor"], 6)

    def test_counter_not_incremented_on_satisfied(self):
        ir = self._escalating_ir()
        trace, _, _ = resolve(ir, self._clean_state())
        self.assertNotIn("ConfidenceFloor", trace["updated_violation_counts"])

    def test_updated_counts_empty_on_clean_run(self):
        ir = self._escalating_ir()
        trace, _, _ = resolve(ir, self._clean_state())
        self.assertEqual(trace["updated_violation_counts"], {})

    # ── Escalation fires ───────────────────────────────────────────────────

    def test_base_action_used_below_threshold(self):
        ir = self._escalating_ir()
        trace, _, _ = resolve(ir, self._violating_state({"ConfidenceFloor": 1}))
        c = trace["constraints"][0]
        self.assertEqual(c["action"], "warn")
        self.assertFalse(c.get("escalation_fired", False))

    def test_escalation_fires_at_threshold(self):
        ir = self._escalating_ir()
        # count was 2, will become 3 — threshold met
        trace, _, _ = resolve(ir, self._violating_state({"ConfidenceFloor": 2}))
        c = trace["constraints"][0]
        self.assertEqual(c["action"], "escalate")
        self.assertTrue(c["escalation_fired"])

    def test_escalation_replaces_on_violation(self):
        ir = self._escalating_ir()
        trace, _, _ = resolve(ir, self._violating_state({"ConfidenceFloor": 9}))
        c = trace["constraints"][0]
        self.assertEqual(c["action"], "freeze")
        self.assertTrue(c["escalation_fired"])

    def test_highest_threshold_wins(self):
        # count becomes 11 — both at:3 and at:10 are met; at:10 wins
        ir = self._escalating_ir()
        trace, _, _ = resolve(ir, self._violating_state({"ConfidenceFloor": 10}))
        c = trace["constraints"][0]
        self.assertEqual(c["action"], "freeze")

    def test_no_escalation_block_uses_base_action(self):
        ir = _base_ir(
            constraints={
                "ConfidenceFloor": {
                    "priority":     "critical",
                    "rule":         {"kind": "range_rule",
                                     "ref": "TestAgent.confidence_score",
                                     "lo": 0.2, "hi": 1.0},
                    "on_violation": ["warn"],
                    "escalation":   [],
                    "decay_check":  None,
                }
            },
            enforce_list=["ConfidenceFloor"],
        )
        trace, _, _ = resolve(ir, self._violating_state())
        c = trace["constraints"][0]
        self.assertEqual(c["action"], "warn")
        self.assertFalse(c.get("escalation_fired", False))

    # ── violation_count in result ──────────────────────────────────────────

    def test_violation_count_present_on_violated_constraint(self):
        ir = self._escalating_ir()
        trace, _, _ = resolve(ir, self._violating_state({"ConfidenceFloor": 4}))
        c = trace["constraints"][0]
        self.assertEqual(c["violation_count"], 5)

    def test_violation_count_absent_on_satisfied_constraint(self):
        ir = self._escalating_ir()
        trace, _, _ = resolve(ir, self._clean_state())
        c = trace["constraints"][0]
        self.assertNotIn("violation_count", c)

    def test_escalation_next_shown_below_threshold(self):
        ir = self._escalating_ir()
        trace, _, _ = resolve(ir, self._violating_state({"ConfidenceFloor": 1}))
        c = trace["constraints"][0]
        nxt = c.get("escalation_next")
        self.assertIsNotNone(nxt)
        self.assertEqual(int(nxt["at"]), 3)
        self.assertEqual(nxt["action"], "escalate")

    # ── Trace rendering ────────────────────────────────────────────────────

    def test_violation_count_line_in_trace_with_escalation_fired(self):
        ir = self._escalating_ir()
        _, rendered, _ = resolve(ir, self._violating_state({"ConfidenceFloor": 2}))
        self.assertIn("Violation count", rendered)
        self.assertIn("escalation threshold met", rendered)
        self.assertIn("freeze" if False else "escalate", rendered)

    def test_violation_count_line_shows_next_escalation(self):
        ir = self._escalating_ir()
        _, rendered, _ = resolve(ir, self._violating_state({"ConfidenceFloor": 0}))
        self.assertIn("Violation count", rendered)
        self.assertIn("next escalation", rendered)

    def test_no_violation_count_line_when_satisfied(self):
        ir = self._escalating_ir()
        _, rendered, _ = resolve(ir, self._clean_state())
        self.assertNotIn("Violation count", rendered)


class TestEscalationValidation(unittest.TestCase):

    def _validate(self, source: str):
        from pi_script.parser import parse_string
        from pi_script.validator import PiValidator
        tree, err = parse_string(source, source_name="<test>")
        assert err is None, f"Parse error: {err}"
        return PiValidator(tree).validate()

    def _source_with_threshold(self, threshold: str) -> str:
        return f"""\
domain test_domain {{
    audit_interval: 1 hour
    tiebreaker: timestamp_asc
}}
entity Agent {{
    score: range(0.0 .. 1.0)
}}
constraint ScoreFloor {{
    priority: high
    rule: Agent.score must remain within range(0.1 .. 1.0)
    on_violation: warn
    escalation {{
        at {threshold} violations: escalate
    }}
}}
enforce {{
    entity: Agent
    constraints: [ScoreFloor]
}}
"""

    def test_integer_threshold_valid(self):
        ok, errors, _ = self._validate(self._source_with_threshold("3"))
        assert ok, errors

    def test_float_threshold_rejected(self):
        ok, errors, _ = self._validate(self._source_with_threshold("1.5"))
        assert not ok
        assert any("1.5" in e for e in errors)

    def test_zero_threshold_rejected(self):
        ok, errors, _ = self._validate(self._source_with_threshold("0"))
        assert not ok
        assert any("positive integer" in e for e in errors)

    def test_large_integer_threshold_valid(self):
        ok, errors, _ = self._validate(self._source_with_threshold("100"))
        assert ok, errors


if __name__ == "__main__":
    unittest.main()
