"""
resolver.py — Constraint evaluator for Pi Script v0.1

Invocation:
    python -m pi_script.resolver ir.json state.json

Inputs:
    ir.json     — Validated IR produced by the M2 validator. Fully trusted.
    state.json  — Entity state snapshot. Schema locked in Draft 3:
                  {
                      "trigger_type":   "event" | "heartbeat",
                      "entity":         str,
                      "entity_state":   { field: value, ... },
                      "response_history": [
                          { "text": str, "state_ref": str, "timestamp": str }
                      ]
                  }

Outputs:
    RESOLUTION TRACE printed to stdout (human-readable terminal format)
    Exit code 0 — all constraints satisfied
    Exit code 1 — one or more violations
    Exit code 2 — input error (bad trigger_type, unknown entity, etc.)

Architecture (Section 10.3, Draft 3):
    1. Validate trigger_type
    2. Look up enforce block for named entity
    3. For each constraint: check state availability → evaluate rule → record result
    4. Collect violations, apply priority resolution (Q1)
    5. Determine final_action and system_state
    6. Call build_trace() → render_trace() → emit

Single responsibility: The resolver is an evaluator, not a compiler.
Parse and validate errors are M1/M2 concerns. Resolver errors are
always runtime evaluation errors.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any

from pi_script.trace import build_trace, render_trace


# ── Violation action restrictiveness order (Q1 resolution) ──────────────────
_ACTION_RANK: dict[str, int] = {
    "warn":              0,
    "flag":              1,
    "escalate":          2,
    "flag + escalate":   3,
    "rollback":          4,
    "freeze":            5,
    "freeze + rollback": 6,
}

_VALID_TRIGGER_TYPES = {"event", "heartbeat"}


# ── Public entry point ───────────────────────────────────────────────────────

def resolve(ir: dict[str, Any], state: dict[str, Any]) -> tuple[dict, str, int]:
    """
    Evaluate all enforced constraints for the named entity against the
    provided state snapshot.

    Returns:
        (trace_dict, rendered_str, exit_code)
        exit_code: 0 = all satisfied, 1 = violations, 2 = input error
    """
    # ── Step 1: Validate trigger_type ────────────────────────────────────────
    trigger_type = state.get("trigger_type", "")
    if trigger_type not in _VALID_TRIGGER_TYPES:
        _fatal(
            f"Invalid trigger_type '{trigger_type}'. "
            f"Must be one of: {sorted(_VALID_TRIGGER_TYPES)}"
        )

    entity_name = state.get("entity", "")
    entity_state = state.get("entity_state", {})
    response_history = state.get("response_history", [])
    session_id = entity_state.get("session_id")

    # ── Step 2: Look up enforce block ─────────────────────────────────────────
    enforce = ir.get("enforce", {})
    if entity_name not in enforce:
        _fatal(
            f"Entity '{entity_name}' not found in enforce block. "
            f"Known entities: {list(enforce.keys())}"
        )

    constraint_names = enforce[entity_name]
    constraints_ir = ir.get("constraints", {})
    maps_ir = ir.get("maps", {})

    # ── Step 3: Evaluate each constraint ─────────────────────────────────────
    evaluated: list[dict[str, Any]] = []

    for cname in constraint_names:
        if cname not in constraints_ir:
            evaluated.append(_suspended(cname, "constraint definition not found in IR"))
            continue

        c_ir = constraints_ir[cname]
        rule = c_ir.get("rule", {})
        rule_kind = rule.get("kind", "unknown")
        priority = c_ir.get("priority", "medium")
        on_violation = c_ir.get("on_violation", [])
        action_str = _action_list_to_str(on_violation)

        state_ref = rule.get("ref", "")
        field_name = _field_from_ref(state_ref)

        if rule_kind == "contradiction_rule":
            result = _eval_contradiction(
                cname, rule, priority, action_str,
                response_history, maps_ir
            )
        elif rule_kind == "membership_rule":
            if field_name and field_name not in entity_state:
                evaluated.append(_suspended(cname, f"state field '{field_name}' not in snapshot"))
                continue
            result = _eval_membership(
                cname, rule, priority, action_str,
                entity_state, maps_ir
            )
        else:
            if field_name and field_name not in entity_state:
                evaluated.append(_suspended(cname, f"state field '{field_name}' not in snapshot"))
                continue
            result = _eval_rule(
                cname, rule, rule_kind, priority, action_str, entity_state
            )

        evaluated.append(result)

    # ── Step 4: Collect violations, apply priority resolution (Q1) ───────────
    violations = [e for e in evaluated if e["status"] == "violated"]
    conflict_resolution = None
    final_action = None
    system_state = "running"

    if violations:
        final_action, conflict_resolution = _resolve_violations(violations)
        system_state = _action_to_system_state(final_action)

    # ── Step 5: Build triggered_by description ────────────────────────────────
    triggered_by = _triggered_by(trigger_type, entity_state, entity_name)

    # ── Step 6: Build and render trace ────────────────────────────────────────
    trace_data = {
        "domain":              ir.get("domain", "unknown"),
        "entity":              entity_name,
        "session_id":          session_id,
        "trigger_type":        trigger_type,
        "triggered_by":        triggered_by,
        "timestamp":           _now_iso(),
        "constraints":         evaluated,
        "conflict_resolution": conflict_resolution,
        "final_action":        final_action,
        "system_state":        system_state,
    }

    trace = build_trace(trace_data)
    rendered = render_trace(trace)

    exit_code = 1 if violations else 0
    return trace, rendered, exit_code


# ── Rule evaluators ──────────────────────────────────────────────────────────

def _eval_rule(
    name: str,
    rule: dict,
    rule_kind: str,
    priority: str,
    action: str,
    entity_state: dict,
) -> dict[str, Any]:
    dispatch = {
        "range_rule":       _eval_range,
        "threshold_rule":   _eval_threshold,
        "equality_rule":    _eval_equality,
        "conditional_rule": _eval_conditional,
    }
    fn = dispatch.get(rule_kind)
    if fn is None:
        return _constraint_result(
            name, priority, "violated", rule_kind,
            f"Unknown rule kind '{rule_kind}' — cannot evaluate",
            action=action,
        )
    return fn(name, rule, priority, action, entity_state)


def _eval_range(name, rule, priority, action, entity_state) -> dict:
    """Form 1: state must remain within range(lo .. hi)"""
    field = _field_from_ref(rule.get("ref", ""))
    lo = rule.get("lo")
    hi = rule.get("hi")
    value = entity_state.get(field)

    if value is None:
        return _suspended(name, f"field '{field}' not in snapshot")
    try:
        v = float(value)
    except (TypeError, ValueError):
        return _suspended(name, f"field '{field}' value '{value}' is not numeric")

    if lo is not None and v < lo:
        return _constraint_result(
            name, priority, "violated", "range_rule",
            f"{field} {v} is below minimum {lo} (range floor)", action=action,
        )
    if hi is not None and v > hi:
        return _constraint_result(
            name, priority, "violated", "range_rule",
            f"{field} {v} exceeds maximum {hi} (range ceiling)", action=action,
        )
    return _constraint_result(
        name, priority, "satisfied", "range_rule",
        f"{field} = {v}, within range({lo} .. {hi})",
    )


def _eval_threshold(name, rule, priority, action, entity_state) -> dict:
    """Form 3: state must remain below N within window"""
    field = _field_from_ref(rule.get("ref", ""))
    below = rule.get("below")
    value = entity_state.get(field)

    if value is None:
        return _suspended(name, f"field '{field}' not in snapshot")
    try:
        v = float(value)
    except (TypeError, ValueError):
        return _suspended(name, f"field '{field}' value '{value}' is not numeric")

    if below is not None and v >= below:
        return _constraint_result(
            name, priority, "violated", "threshold_rule",
            f"{field} {v} >= threshold {below}", action=action,
        )
    return _constraint_result(
        name, priority, "satisfied", "threshold_rule",
        f"{field} = {v}, below threshold {below}",
    )


def _eval_equality(name, rule, priority, action, entity_state) -> dict:
    """Form 2: state must equal reference_value"""
    field = _field_from_ref(rule.get("ref", ""))
    expected = rule.get("value")
    value = entity_state.get(field)

    if value is None:
        return _suspended(name, f"field '{field}' not in snapshot")

    actual = _coerce_bool(value) if isinstance(expected, bool) else value

    if actual != expected:
        return _constraint_result(
            name, priority, "violated", "equality_rule",
            f"{field} is {value!r}, expected {expected!r}", action=action,
        )
    return _constraint_result(
        name, priority, "satisfied", "equality_rule",
        f"{field} = {value!r}, equals expected {expected!r}",
    )


def _eval_conditional(name, rule, priority, action, entity_state) -> dict:
    """Form 4: if state op value then require action before outcome"""
    field = _field_from_ref(rule.get("ref", ""))
    op = rule.get("op", "")
    threshold = rule.get("value")
    value = entity_state.get(field)

    if value is None:
        return _suspended(name, f"field '{field}' not in snapshot")
    try:
        v = float(value)
        t = float(threshold)
    except (TypeError, ValueError):
        return _suspended(name, f"cannot compare '{field}' value '{value}' with '{threshold}'")

    if _apply_op(v, op, t):
        return _constraint_result(
            name, priority, "violated", "conditional_rule",
            f"condition met: {field} {v} {op} {t}", action=action,
        )
    return _constraint_result(
        name, priority, "satisfied", "conditional_rule",
        f"condition not met: {field} {v} {op} {t}",
    )


def _eval_membership(name, rule, priority, action, entity_state, maps_ir) -> dict:
    """Form 6: state must match mapped_values (implicit map join by state_ref)"""
    ref = rule.get("ref", "")
    field = _field_from_ref(ref)
    value = entity_state.get(field)

    valid_values: set[str] = set()
    for map_entry in maps_ir.get(ref, []):
        maps_to = map_entry.get("maps_to")
        if maps_to:
            valid_values.add(str(maps_to))

    if value is None:
        return _suspended(name, f"field '{field}' not in snapshot")

    if str(value) not in valid_values:
        return _constraint_result(
            name, priority, "violated", "membership_rule",
            f"{field} value {value!r} not in valid set {sorted(valid_values)}",
            action=action,
        )
    return _constraint_result(
        name, priority, "satisfied", "membership_rule",
        f"{field} = {value!r}, matched in valid set {sorted(valid_values)}",
    )


def _eval_contradiction(
    name, rule, priority, action, response_history, maps_ir
) -> dict:
    """
    Form 5: if new_response contradicts prior_response(same_topic)
    topic key = state_ref (Q2 resolution)
    contradiction detection = map trigger match on new response text
    """
    if not response_history:
        return _constraint_result(
            name, priority, "satisfied", "contradiction_rule",
            "no response history to evaluate",
        )

    contradiction_triggers: list[str] = []
    for map_entries in maps_ir.values():
        for entry in map_entries:
            for t in entry.get("triggers", []):
                if not t.startswith("regex:"):
                    contradiction_triggers.append(t.lower())

    new_entry = response_history[-1]
    new_text = new_entry.get("text", "").lower()
    new_ref = new_entry.get("state_ref", "")

    prior_on_topic = [
        e for e in response_history[:-1]
        if e.get("state_ref", "") == new_ref
    ]

    if not prior_on_topic:
        return _constraint_result(
            name, priority, "satisfied", "contradiction_rule",
            f"no prior responses on topic '{new_ref}' within window",
        )

    matched_trigger = next(
        (t for t in contradiction_triggers if t and t in new_text), None
    )

    if matched_trigger:
        prior_text = prior_on_topic[-1].get("text", "")
        return _constraint_result(
            name, priority, "violated", "contradiction_rule",
            f"new response matches contradiction trigger '{matched_trigger}' "
            f"against prior response on topic '{new_ref}'",
            action=action,
            map_match=f"'{matched_trigger}' -> contradiction signal",
            prior_response=prior_text,
        )

    return _constraint_result(
        name, priority, "satisfied", "contradiction_rule",
        f"no contradiction signals detected in new response on topic '{new_ref}'",
    )


# ── Violation resolution (Q1) ────────────────────────────────────────────────

def _resolve_violations(violations: list[dict]) -> tuple[str, str | None]:
    """Most restrictive action wins. All violations logged as co-active (Q1)."""
    if len(violations) == 1:
        return violations[0].get("action", "flag"), None

    ranked = sorted(
        violations,
        key=lambda v: _ACTION_RANK.get(v.get("action", "flag"), 0),
        reverse=True,
    )
    final_action = ranked[0].get("action", "flag")

    critical = [v for v in violations if v.get("priority") == "critical"]
    names = [v["name"] for v in violations]

    if len(critical) >= 2:
        note = (
            f"{len(critical)} simultaneous critical violations: "
            f"{', '.join(v['name'] for v in critical)}. "
            f"Most restrictive action '{final_action}' selected (Q1 resolution). "
            "All violations logged as co-active."
        )
    else:
        note = (
            f"{len(violations)} violations across mixed priorities: "
            f"{', '.join(names)}. "
            f"Highest priority action '{final_action}' applied. "
            "All violations logged."
        )

    return final_action, note


# ── Helpers ──────────────────────────────────────────────────────────────────

def _constraint_result(
    name: str,
    priority: str,
    status: str,
    rule_kind: str,
    evaluation: str,
    action: str | None = None,
    map_match: str | None = None,
    prior_response: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name":       name,
        "priority":   priority,
        "status":     status,
        "rule_kind":  rule_kind,
        "evaluation": evaluation,
        "map_match":  map_match,
        "action":     action if status == "violated" else None,
    }
    if prior_response is not None:
        result["prior_response"] = prior_response
    return result


def _suspended(name: str, reason: str) -> dict[str, Any]:
    return {
        "name":       name,
        "priority":   "unknown",
        "status":     "suspended",
        "rule_kind":  "unknown",
        "evaluation": f"suspended: {reason}",
        "map_match":  None,
        "action":     None,
    }


def _action_list_to_str(on_violation: list[str]) -> str:
    return " + ".join(on_violation) if on_violation else "flag"


def _action_to_system_state(action: str | None) -> str:
    if not action:
        return "running"
    a = action.lower()
    if "freeze" in a:
        return "frozen"
    if "escalate" in a:
        return "escalated"
    return "running"


def _field_from_ref(ref: str) -> str:
    return ref.split(".", 1)[1] if "." in ref else ref


def _apply_op(value: float, op: str, threshold: float) -> bool:
    return {
        ">=": value >= threshold,
        ">":  value > threshold,
        "<=": value <= threshold,
        "<":  value < threshold,
        "==": value == threshold,
        "!=": value != threshold,
    }.get(op, False)


def _coerce_bool(value: Any) -> Any:
    if isinstance(value, str):
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
    return value


def _triggered_by(trigger_type: str, entity_state: dict, entity_name: str) -> str:
    if trigger_type == "heartbeat":
        return "decay_check interval elapsed — no new state arrived"
    return f"state snapshot received for {entity_name}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _load_json(path: str) -> dict:
    """Load a JSON file, tolerating UTF-8, UTF-8-with-BOM, and UTF-16 (PowerShell redirect)."""
    for encoding in ("utf-8-sig", "utf-16", "utf-8"):
        try:
            with open(path, encoding=encoding) as f:
                return json.load(f)
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}") from e
    raise ValueError(f"Cannot decode '{path}' — not valid UTF-8 or UTF-16 JSON")


def _fatal(msg: str) -> None:
    print(f"RESOLVER ERROR  {msg}", file=sys.stderr)
    sys.exit(2)


# ── CLI entry point ──────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) != 3:
        print(
            "Usage: python -m pi_script.resolver ir.json state.json",
            file=sys.stderr,
        )
        sys.exit(2)

    ir_path, state_path = sys.argv[1], sys.argv[2]

    try:
        ir = _load_json(ir_path)
    except (FileNotFoundError, ValueError) as e:
        _fatal(f"Cannot read IR file '{ir_path}': {e}")

    try:
        state = _load_json(state_path)
    except (FileNotFoundError, ValueError) as e:
        _fatal(f"Cannot read state file '{state_path}': {e}")

    trace, rendered, exit_code = resolve(ir, state)
    print(rendered)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
