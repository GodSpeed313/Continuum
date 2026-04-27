"""
trace.py — RESOLUTION TRACE builder and renderer for Pi Script v0.1

Public API:
    build_trace(data: dict) -> dict
        Takes evaluation results. Returns a structured, JSON-serializable trace dict.

    render_trace(trace: dict) -> str
        Takes a trace dict. Returns a terminal pretty-print string.

    human_text(data: dict) -> str
        Takes evaluation results. Returns a plain-English explanation.
        This is the gate condition field. Must be readable by a non-expert.

Gate condition (Section 3.1):
    A non-expert must be able to read a RESOLUTION TRACE and understand
    why the system acted. If they cannot, the trace format is broken, not the person.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# ── Violation action restrictiveness order (Q1 resolution) ──────────────────
# Higher index = more restrictive. Used for simultaneous critical conflict resolution.
_ACTION_RANK: dict[str, int] = {
    "warn":              0,
    "flag":              1,
    "escalate":          2,
    "flag + escalate":   3,
    "rollback":          4,
    "freeze":            5,
    "freeze + rollback": 6,
}


# ── Public API ───────────────────────────────────────────────────────────────

def build_trace(data: dict[str, Any]) -> dict[str, Any]:
    """
    Build a structured RESOLUTION TRACE dict from evaluation results.

    Input shape (from resolver):
        domain:              str
        entity:              str
        session_id:          str | None
        trigger_type:        "event" | "heartbeat"
        triggered_by:        str        e.g. "tone_score changed to 0.31"
        timestamp:           str        ISO 8601 — if absent, generated now
        constraints:         list[dict] one entry per evaluated constraint
            name:            str
            status:          "satisfied" | "violated"
            rule_kind:       str
            evaluation:      str        e.g. "tone_score 0.31 < range floor 0.4"
            map_match:       str | None
            action:          str | None
        conflict_resolution: str | None  None if 0 or 1 violations
        final_action:        str | None
        system_state:        "running" | "frozen" | "escalated"

    Returns a JSON-serializable dict with all Section 3.1 required fields,
    plus a human_text field (the gate condition field).
    """
    timestamp = data.get("timestamp") or _now_iso()

    trace = {
        "timestamp":           timestamp,
        "domain":              data["domain"],
        "entity":              _entity_label(data),
        "trigger_type":        data["trigger_type"],
        "triggered_by":        data["triggered_by"],
        "constraints":         [_build_constraint_block(c) for c in data.get("constraints", [])],
        "conflict_resolution": data.get("conflict_resolution"),
        "final_action":        data.get("final_action"),
        "system_state":        data["system_state"],
        "human_text":          human_text(data),
    }
    return trace


def render_trace(trace: dict[str, Any]) -> str:
    """
    Render a RESOLUTION TRACE dict as a terminal pretty-print string.

    The rendered format mirrors Section 3.1 of the Pi Script v0.1 spec.
    """
    lines: list[str] = []
    sep = "═" * 56

    lines.append("")
    lines.append("RESOLUTION TRACE")
    lines.append(sep)
    lines.append(f"Timestamp    : {trace['timestamp']}")
    lines.append(f"Domain       : {trace['domain']}")
    lines.append(f"Entity       : {trace['entity']}")
    lines.append(f"Trigger      : {trace['trigger_type']} — {trace['triggered_by']}")
    lines.append(sep)

    constraints = trace.get("constraints", [])
    for i, c in enumerate(constraints):
        prefix = "├──" if i < len(constraints) - 1 else "└──"
        lines.append(f"{prefix} CONSTRAINT: {c['name']} [priority: {c.get('priority', 'unknown')}]")
        lines.append(f"│   ├── Rule kind  : {c['rule_kind']}")
        lines.append(f"│   ├── Evaluation : {c['evaluation']}")
        if c.get("map_match"):
            lines.append(f"│   ├── Map match  : {c['map_match']}")
        status = c["status"]
        if status == "satisfied":
            lines.append(f"│   └── ✓ SATISFIED — no action")
        else:
            lines.append(f"│   ├── ✗ VIOLATION DETECTED")
            lines.append(f"│   └── Action     : {c.get('action', 'none')}")
        lines.append("│")

    if trace.get("conflict_resolution"):
        lines.append("├── CONFLICT RESOLUTION")
        lines.append(f"│   └── {trace['conflict_resolution']}")
        lines.append("│")

    lines.append("└── RESOLUTION")
    if trace.get("final_action"):
        lines.append(f"    ├── Action       : {trace['final_action']}")
    lines.append(f"    ├── System state : {trace['system_state']}")
    lines.append(f"    └── {trace['human_text']}")
    lines.append("")

    return "\n".join(lines)


def human_text(data: dict[str, Any]) -> str:
    """
    Generate the gate condition field: a plain-English explanation of what
    happened and why the system acted.

    Rules:
    - No jargon. No log-speak. No system error language.
    - Must be readable by someone who has never seen Pi Script.
    - Must explain both WHAT happened and WHY the system responded that way.
    - Simultaneous violations must be listed, not collapsed.
    """
    constraints = data.get("constraints", [])
    violations = [c for c in constraints if c["status"] == "violated"]
    suspended = [c for c in constraints if c["status"] == "suspended"]
    system_state = data["system_state"]
    final_action = data.get("final_action")

    # ── Suspension note — built upfront, appended to all cases ───────────────
    suspension_note = ""
    if suspended:
        sus_names = _natural_list([c["name"] for c in suspended])
        suspension_note = (
            f" Note: {sus_names} could not be checked because the required "
            "state information was not available — those rules have been paused."
        )

    # ── All satisfied ────────────────────────────────────────────────────────
    if not violations:
        names = [c["name"] for c in constraints if c["status"] == "satisfied"]
        if len(names) == 0:
            return "No constraints were evaluated. No action was taken." + suspension_note
        if len(names) == 1:
            return (
                f"The rule '{names[0]}' was checked and passed. "
                "Everything is within acceptable bounds. No action was taken."
                + suspension_note
            )
        rule_list = _natural_list(names)
        return (
            f"All rules were checked and passed: {rule_list}. "
            "Everything is within acceptable bounds. No action was taken."
            + suspension_note
        )

    # ── Single violation ─────────────────────────────────────────────────────
    if len(violations) == 1:
        v = violations[0]
        return _single_violation_text(v, system_state, final_action) + suspension_note

    # ── Multiple violations ──────────────────────────────────────────────────
    critical_violations = [v for v in violations if v.get("priority") == "critical"]

    if len(critical_violations) >= 2:
        names = _natural_list([v["name"] for v in critical_violations])
        action_text = _action_to_plain(final_action)
        state_text = _state_to_plain(system_state)
        return (
            f"Two critical rules were broken at the same time: {names}. "
            f"The strictest response has been applied — {action_text}. "
            f"{state_text} "
            f"Both issues are recorded here and require human review before the system can continue."
            + suspension_note
        )

    # Mixed priority violations
    v_names = _natural_list([v["name"] for v in violations])
    action_text = _action_to_plain(final_action)
    state_text = _state_to_plain(system_state)
    return (
        f"Multiple rules were broken: {v_names}. "
        f"The most serious issue has been handled first — {action_text}. "
        f"{state_text}"
        + suspension_note
    )


# ── Internal helpers ─────────────────────────────────────────────────────────

def _build_constraint_block(c: dict[str, Any]) -> dict[str, Any]:
    """Normalise a constraint evaluation entry for the trace dict."""
    return {
        "name":       c["name"],
        "priority":   c.get("priority", "unknown"),
        "status":     c["status"],
        "rule_kind":  c["rule_kind"],
        "evaluation": c["evaluation"],
        "map_match":  c.get("map_match"),
        "action":     c.get("action"),
    }


def _single_violation_text(
    v: dict[str, Any],
    system_state: str,
    final_action: str | None,
) -> str:
    """Generate human_text for a single constraint violation."""
    name = v["name"]
    rule_kind = v.get("rule_kind", "unknown")
    evaluation = v.get("evaluation", "")
    priority = v.get("priority", "unknown")
    action_text = _action_to_plain(final_action)
    state_text = _state_to_plain(system_state)

    if rule_kind == "range_rule":
        return (
            f"The rule '{name}' was broken: {evaluation}. "
            f"{action_text.capitalize()}. {state_text}"
        )

    if rule_kind == "threshold_rule":
        return (
            f"The rule '{name}' was broken: {evaluation}. "
            f"{action_text.capitalize()}. {state_text}"
        )

    if rule_kind == "equality_rule":
        return (
            f"The rule '{name}' was broken: {evaluation}. "
            f"{action_text.capitalize()}. {state_text}"
        )

    if rule_kind == "contradiction_rule":
        if priority == "critical":
            return (
                f"This response contradicts earlier advice on the same topic — "
                f"'{name}' is a critical rule. "
                f"The system has been frozen and the issue escalated for human review "
                f"before any further responses are sent."
            )
        return (
            f"This response may contradict earlier advice on the same topic. "
            f"The rule '{name}' has flagged it for review. "
            f"{action_text.capitalize()}. {state_text}"
        )

    if rule_kind == "membership_rule":
        return (
            f"The value provided does not match any of the expected options — "
            f"the rule '{name}' requires a value from a defined set. "
            f"{action_text.capitalize()}. {state_text}"
        )

    if rule_kind == "conditional_rule":
        return (
            f"A condition was met that triggered the rule '{name}': {evaluation}. "
            f"{action_text.capitalize()}. {state_text}"
        )

    return (
        f"The rule '{name}' was broken: {evaluation}. "
        f"{action_text.capitalize()}. {state_text}"
    )


def _action_to_plain(action: str | None) -> str:
    """Translate a violation action code into plain English."""
    if not action:
        return "no action was taken"
    mapping = {
        "flag":              "this has been logged for review",
        "warn":              "a warning has been issued to the operator",
        "escalate":          "this has been sent to a human reviewer",
        "flag + escalate":   "this has been logged and sent to a human reviewer",
        "freeze":            "the system has been paused until a human clears it",
        "rollback":          "the system has been rolled back to its last verified state",
        "freeze + rollback": (
            "the system has been paused and rolled back to its last verified state"
        ),
    }
    return mapping.get(action.lower(), f"the following action was taken: {action}")


def _state_to_plain(system_state: str) -> str:
    """Translate a system state into a plain-English status sentence."""
    mapping = {
        "running":   "The system is still running.",
        "frozen":    "The system is currently paused and cannot send further responses until this is resolved.",
        "escalated": "The issue has been passed to a human reviewer.",
    }
    return mapping.get(system_state, f"System state: {system_state}.")


def _entity_label(data: dict[str, Any]) -> str:
    """Format the entity label, including session_id if present."""
    entity = data["entity"]
    session_id = data.get("session_id")
    if session_id:
        return f"{entity} [session_id: {session_id}]"
    return entity


def _natural_list(items: list[str]) -> str:
    """Format a list of strings as natural English: 'a, b, and c'."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string with millisecond precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
