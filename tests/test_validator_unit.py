"""Pi Script validator unit tests — hand-built Lark Tree harness.

Constructs AST nodes directly and feeds them to PiValidator — no parser
involved. Tests validator internals in isolation (faster feedback loop and
better isolation for debugging than the end-to-end tests in
test_validator.py, which go through the parser).

Recreation of the M4-era file lost before it was ever committed (see
TODO.md). Node shapes mirror the trees pi_script/pi_script.lark actually
produces; terminals are real Token instances because the validator's
isinstance(Token) checks (_process_enforce, _str_list, _extract_state_type)
would silently mis-handle plain strings.
"""

from lark import Token, Tree

from pi_script.validator import PiValidator


# ── AST builders (shapes verified against parser output) ──────────────────────

def _state_ref(entity: str, field: str) -> Tree:
    return Tree("state_ref", [Token("PASCAL_ID", entity), Token("SNAKE_ID", field)])


def _duration(value: str, unit: str) -> Tree:
    return Tree("duration", [
        Token("PI_NUMBER", value),
        Tree("time_unit", [Token("TIME_UNIT_KW", unit)]),
    ])


def _audit_item(value: str = "24", unit: str = "hours") -> Tree:
    return Tree("domain_item", [_duration(value, unit)])


def _tiebreaker_item(mode: str = "timestamp_asc") -> Tree:
    return Tree("domain_item", [Tree("tiebreaker_mode", [Token("TIEBREAKER_KW", mode)])])


def _domain_decl(name: str, items: list[Tree]) -> Tree:
    return Tree("domain_decl", [Token("SNAKE_ID", name), *items])


def _stmt(decl: Tree) -> Tree:
    return Tree("top_level_stmt", [decl])


def _domain_section(domain: Tree, *decls: Tree) -> Tree:
    return Tree("domain_section", [domain, *[_stmt(d) for d in decls]])


def _start(*sections: Tree) -> Tree:
    return Tree("start", list(sections))


# ── Entity builders ───────────────────────────────────────────────────────────

def _st_kw(keyword: str) -> Tree:
    return Tree("state_type", [Token("STATE_TYPE_KW", keyword)])


def _st_range(lo: str, hi: str) -> Tree:
    return Tree("state_type", [Token("PI_NUMBER", lo), Token("PI_NUMBER", hi)])


def _st_sequence(inner: Tree) -> Tree:
    return Tree("state_type", [inner])


def _entity_decl(name: str, fields: list[tuple[str, Tree]]) -> Tree:
    return Tree("entity_decl", [
        Token("PASCAL_ID", name),
        *[Tree("state_field", [Token("SNAKE_ID", f), st]) for f, st in fields],
    ])


# ── Value builders ────────────────────────────────────────────────────────────

def _pv_number(raw: str) -> Tree:
    return Tree("pv_number", [Token("PI_NUMBER", raw)])


def _pv_true() -> Tree:
    return Tree("pv_true", [])


def _pv_false() -> Tree:
    return Tree("pv_false", [])


def _pv_string(value: str) -> Tree:
    return Tree("pv_string", [Token("ESCAPED_STRING", f'"{value}"')])


# ── Rule builders ─────────────────────────────────────────────────────────────

def _range_rule(ref: Tree, lo: str, hi: str) -> Tree:
    return Tree("range_rule", [ref, Token("PI_NUMBER", lo), Token("PI_NUMBER", hi)])


def _threshold_rule(ref: Tree, below: str, within: Tree) -> Tree:
    return Tree("threshold_rule", [ref, Token("PI_NUMBER", below), within])


def _equality_rule(ref: Tree, value: Tree) -> Tree:
    return Tree("equality_rule", [ref, value])


def _membership_rule(ref: Tree) -> Tree:
    return Tree("membership_rule", [ref])


def _bound_rule(ref: Tree, op: str, value: str) -> Tree:
    return Tree("bound_rule", [ref, Token("COMP_OP", op), Token("PI_NUMBER", value)])


def _if_rule(ref: Tree, cond: Tree,
             require: str = "review", before: str = "publish") -> Tree:
    return Tree("if_rule", [
        ref, cond, Token("SNAKE_ID", require), Token("SNAKE_ID", before),
    ])


def _cond_compare(op: str, value: Tree) -> Tree:
    return Tree("cond_compare", [Token("COMP_OP", op), value])


# ── Constraint builders ───────────────────────────────────────────────────────

def _priority(level: str) -> Tree:
    return Tree("c_priority", [Tree("priority_level", [Token("PRIORITY_KW", level)])])


def _rule(inner: Tree) -> Tree:
    return Tree("c_rule", [Tree("rule_expr", [inner])])


def _on_violation(*actions: str) -> Tree:
    return Tree("c_on_violation", [Tree("violation_action", [
        Tree("simple_action", [Token("ACTION_KW", a)]) for a in actions
    ])])


def _decay_check(value: str, unit: str) -> Tree:
    return Tree("c_decay_check", [_duration(value, unit)])


def _escalation(steps: list[tuple[str, str]]) -> Tree:
    return Tree("c_escalation", [Tree("escalation_block", [
        Tree("escalation_step", [
            Token("PI_NUMBER", at),
            Tree("escalation_action", [Token("ACTION_KW", action)]),
        ])
        for at, action in steps
    ])])


def _constraint_decl(name: str, *items: Tree) -> Tree:
    return Tree("constraint_decl", [Token("PASCAL_ID", name), *items])


# ── Map / enforce / arbiter builders ──────────────────────────────────────────

def _trigger(text: str) -> Tree:
    return Tree("trigger_entry", [Token("ESCAPED_STRING", f'"{text}"')])


def _regex_trigger(pattern: str) -> Tree:
    return Tree("regex_trigger", [Token("ESCAPED_STRING", f'"{pattern}"')])


def _map_decl(name: str, target: Tree, maps_to: Tree, triggers: list[Tree]) -> Tree:
    return Tree("map_decl", [
        Token("PASCAL_ID", name),
        Tree("mi_target", [target]),
        Tree("mi_maps_to", [maps_to]),
        Tree("mi_triggers", [Tree("trigger_list", triggers)]),
    ])


def _enforce_decl(entity: str, constraint_names: list[str]) -> Tree:
    return Tree("enforce_decl", [
        Tree("ei_entity", [Token("PASCAL_ID", entity)]),
        Tree("ei_constraints", [Tree("enforce_ref_list", [
            Token("PASCAL_ID", n) for n in constraint_names
        ])]),
    ])


def _str_list(values: list[str]) -> Tree:
    return Tree("str_list", [Token("ESCAPED_STRING", f'"{v}"') for v in values])


def _arbiter_decl(name: str,
                  acceptable: list[str] | None = None,
                  never: list[str] | None = None,
                  review: list[str] | None = None,
                  monitor: tuple[str, Tree] | None = None) -> Tree:
    children: list = [
        Token("PASCAL_ID", name),
        Tree("ai_acceptable", [_str_list(acceptable or [])]),
        Tree("ai_never", [_str_list(never or [])]),
        Tree("ai_human_review", [_str_list(review or [])]),
    ]
    if monitor is not None:
        threshold, window = monitor
        children.append(Tree("ai_monitor", [
            Tree("mi_threshold", [Token("PI_NUMBER", threshold)]),
            Tree("mi_window", [window]),
        ]))
    return Tree("arbiter_decl", children)


# ── Standard happy-path fixture ───────────────────────────────────────────────

_ALL_CONSTRAINTS = [
    "ScoreFloor", "ScoreThreshold", "FlagEquality", "ModeCheck", "ScoreBound",
]


def _standard_tree() -> Tree:
    """Full valid single-domain program covering every extraction path."""
    agent = _entity_decl("Agent", [
        ("score",        _st_range("0.0", "1.0")),
        ("current_mode", _st_kw("text")),
        ("flagged",      _st_kw("boolean")),
        ("tags",         _st_sequence(_st_kw("text"))),
    ])
    score_floor = _constraint_decl(
        "ScoreFloor",
        _priority("critical"),
        _rule(_range_rule(_state_ref("Agent", "score"), "0.2", "1.0")),
        _on_violation("freeze", "escalate"),
        _decay_check("24", "hours"),
        _escalation([("1", "warn"), ("3", "freeze")]),
    )
    score_threshold = _constraint_decl(
        "ScoreThreshold",
        _priority("high"),
        _rule(_threshold_rule(_state_ref("Agent", "score"), "0.3",
                              _duration("2", "hours"))),
        _on_violation("escalate"),
    )
    flag_equality = _constraint_decl(
        "FlagEquality",
        _priority("high"),
        _rule(_equality_rule(_state_ref("Agent", "flagged"), _pv_false())),
        _on_violation("flag"),
    )
    mode_check = _constraint_decl(
        "ModeCheck",
        _priority("medium"),
        _rule(_membership_rule(_state_ref("Agent", "current_mode"))),
        _on_violation("warn"),
    )
    score_bound = _constraint_decl(
        "ScoreBound",
        _priority("high"),
        _rule(_bound_rule(_state_ref("Agent", "score"), "<", "0.8")),
        _on_violation("flag"),
    )
    safe_mode_map = _map_decl(
        "SafeMode",
        _state_ref("Agent", "current_mode"),
        _pv_string("safe_mode"),
        [_trigger("safe"), _trigger("restricted"), _regex_trigger("^r.*d$")],
    )
    enforce = _enforce_decl("Agent", _ALL_CONSTRAINTS)
    arbiter = _arbiter_decl(
        "Gov",
        acceptable=["tuning"],
        never=["safety_bypass"],
        review=["scope_change"],
        monitor=("0.75", _duration("7", "days")),
    )
    return _start(_domain_section(
        _domain_decl("unit_domain", [_audit_item("24", "hours"),
                                     _tiebreaker_item("timestamp_desc")]),
        agent, score_floor, score_threshold, flag_equality, mode_check,
        score_bound, safe_mode_map, enforce, arbiter,
    ))


def _validate(tree: Tree):
    return PiValidator(tree).validate()


# ── Group 1: happy-path IR extraction (11) ────────────────────────────────────

class TestPiValidatorHappyPath:
    def test_domain_and_audit_interval_extracted(self):
        ok, errors, ir = _validate(_standard_tree())
        assert ok, "Validation errors:\n" + "\n".join(errors)
        assert ir["domain"] == "unit_domain"
        assert ir["audit_interval"] == {"value": 24.0, "unit": "hours"}
        assert ir["tiebreaker"] == "timestamp_desc"

    def test_entities_extracted(self):
        _, _, ir = _validate(_standard_tree())
        assert ir["entities"] == {"Agent": {
            "score":        "range(0.0..1.0)",
            "current_mode": "text",
            "flagged":      "boolean",
            "tags":         "sequence(text)",
        }}

    def test_range_rule_extracted(self):
        _, _, ir = _validate(_standard_tree())
        c = ir["constraints"]["ScoreFloor"]
        assert c["priority"] == "critical"
        assert c["rule"] == {
            "kind": "range_rule", "ref": "Agent.score", "lo": 0.2, "hi": 1.0,
        }
        assert c["on_violation"] == ["freeze", "escalate"]

    def test_threshold_rule_extracted(self):
        _, _, ir = _validate(_standard_tree())
        rule = ir["constraints"]["ScoreThreshold"]["rule"]
        assert rule == {
            "kind":   "threshold_rule",
            "ref":    "Agent.score",
            "below":  0.3,
            "within": {"value": 2.0, "unit": "hours"},
        }

    def test_equality_rule_extracted(self):
        _, _, ir = _validate(_standard_tree())
        rule = ir["constraints"]["FlagEquality"]["rule"]
        assert rule["kind"] == "equality_rule"
        assert rule["ref"] == "Agent.flagged"
        assert rule["value"] is False

    def test_membership_rule_extracted(self):
        _, _, ir = _validate(_standard_tree())
        rule = ir["constraints"]["ModeCheck"]["rule"]
        assert rule == {"kind": "membership_rule", "ref": "Agent.current_mode"}

    def test_bound_rule_extracted(self):
        _, _, ir = _validate(_standard_tree())
        rule = ir["constraints"]["ScoreBound"]["rule"]
        assert rule == {
            "kind": "bound_rule", "ref": "Agent.score", "op": "<", "value": 0.8,
        }

    def test_maps_extracted(self):
        _, _, ir = _validate(_standard_tree())
        entries = ir["maps"]["Agent.current_mode"]
        assert len(entries) == 1
        assert entries[0]["maps_to"] == "safe_mode"
        assert entries[0]["triggers"] == ["safe", "restricted", "regex:^r.*d$"]

    def test_enforce_extracted(self):
        _, _, ir = _validate(_standard_tree())
        assert ir["enforce"] == {"Agent": _ALL_CONSTRAINTS}

    def test_arbiter_extracted(self):
        _, _, ir = _validate(_standard_tree())
        arb = ir["arbiter"]
        assert arb["name"] == "Gov"
        assert arb["acceptable_evolution"] == ["tuning"]
        assert arb["never_acceptable"] == ["safety_bypass"]
        assert arb["requires_human_review"] == ["scope_change"]
        assert arb["acceptance_monitor"] == {
            "threshold": 0.75, "window": {"value": 7.0, "unit": "days"},
        }

    def test_escalation_steps_and_decay_extracted(self):
        _, _, ir = _validate(_standard_tree())
        c = ir["constraints"]["ScoreFloor"]
        assert c["escalation"] == [
            {"at": 1.0, "action": "warn"},
            {"at": 3.0, "action": "freeze"},
        ]
        assert c["decay_check"] == {"value": 24.0, "unit": "hours"}


# ── Group 2: semantic errors (7) ──────────────────────────────────────────────

def _minimal_section(*decls: Tree, domain_items: list[Tree] | None = None) -> Tree:
    """Single-domain tree: Agent entity + arbiter always present so each test
    isolates exactly the semantic error it constructs."""
    items = domain_items if domain_items is not None else [
        _audit_item(), _tiebreaker_item(),
    ]
    agent = _entity_decl("Agent", [
        ("score",        _st_range("0.0", "1.0")),
        ("current_mode", _st_kw("text")),
    ])
    arbiter = _arbiter_decl("Gov")
    return _start(_domain_section(
        _domain_decl("unit_domain", items), agent, *decls, arbiter,
    ))


class TestSemanticErrors:
    def test_missing_domain(self):
        ok, errors, _ = _validate(_start())
        assert not ok
        assert errors == ["Missing required 'domain' declaration."]

    def test_missing_audit_interval(self):
        tree = _minimal_section(domain_items=[_tiebreaker_item()])
        ok, errors, _ = _validate(tree)
        assert not ok
        assert any("audit_interval is required" in e for e in errors)

    def test_duplicate_audit_interval(self):
        tree = _minimal_section(
            domain_items=[_audit_item(), _audit_item(), _tiebreaker_item()],
        )
        ok, errors, _ = _validate(tree)
        assert not ok
        assert any("exactly once (found 2)" in e for e in errors)

    def test_undeclared_entity_ref(self):
        constraint = _constraint_decl(
            "GhostFloor",
            _priority("high"),
            _rule(_range_rule(_state_ref("Ghost", "score"), "0.0", "1.0")),
            _on_violation("flag"),
        )
        ok, errors, _ = _validate(_minimal_section(constraint))
        assert not ok
        assert any("undeclared entity 'Ghost'" in e for e in errors)

    def test_undeclared_state_ref(self):
        constraint = _constraint_decl(
            "NoSuchField",
            _priority("high"),
            _rule(_equality_rule(_state_ref("Agent", "nonexistent"), _pv_true())),
            _on_violation("flag"),
        )
        ok, errors, _ = _validate(_minimal_section(constraint))
        assert not ok
        assert any("has no state 'nonexistent'" in e for e in errors)

    def test_membership_rule_without_map(self):
        constraint = _constraint_decl(
            "ModeCheck",
            _priority("medium"),
            _rule(_membership_rule(_state_ref("Agent", "current_mode"))),
            _on_violation("warn"),
        )
        ok, errors, _ = _validate(_minimal_section(constraint))
        assert not ok
        assert any(
            "ModeCheck" in e and "no map block declares" in e for e in errors
        )

    def test_enforce_references_undeclared_constraint(self):
        enforce = _enforce_decl("Agent", ["Nonexistent"])
        ok, errors, _ = _validate(_minimal_section(enforce))
        assert not ok
        assert any("undeclared constraint 'Nonexistent'" in e for e in errors)


# ── Group 3: malformed AST — None guards (5) ──────────────────────────────────

def _tree_with_rule(inner: Tree) -> Tree:
    """Valid domain wrapping one constraint whose rule body is `inner`."""
    constraint = _constraint_decl(
        "Broken", _priority("high"), _rule(inner), _on_violation("flag"),
    )
    return _minimal_section(constraint)


def _assert_unknown_rule(inner: Tree):
    """Validator must not crash on a rule missing its state_ref child; the
    guard maps it to {'kind': 'unknown'} and downstream checks skip it."""
    ok, errors, ir = _validate(_tree_with_rule(inner))
    assert ok, "Validation errors:\n" + "\n".join(errors)
    assert ir["constraints"]["Broken"]["rule"] == {"kind": "unknown"}


class TestMalformedAst:
    def test_range_rule_missing_state_ref(self):
        _assert_unknown_rule(Tree("range_rule", [
            Token("PI_NUMBER", "0.0"), Token("PI_NUMBER", "1.0"),
        ]))

    def test_threshold_rule_missing_state_ref(self):
        _assert_unknown_rule(Tree("threshold_rule", [
            Token("PI_NUMBER", "0.3"), _duration("2", "hours"),
        ]))

    def test_equality_rule_missing_state_ref(self):
        _assert_unknown_rule(Tree("equality_rule", [_pv_true()]))

    def test_membership_rule_missing_state_ref(self):
        _assert_unknown_rule(Tree("membership_rule", []))

    def test_bound_rule_missing_state_ref(self):
        _assert_unknown_rule(Tree("bound_rule", [
            Token("COMP_OP", "<"), Token("PI_NUMBER", "0.8"),
        ]))


# ── Group 4: conditional (if_rule) variants (3) ───────────────────────────────

class TestConditionalRules:
    def test_cond_compare(self):
        constraint = _constraint_decl(
            "CondCompare",
            _priority("high"),
            _rule(_if_rule(_state_ref("Agent", "score"),
                           _cond_compare(">", _pv_number("0.5")))),
            _on_violation("flag"),
        )
        ok, errors, ir = _validate(_minimal_section(constraint))
        assert ok, errors
        assert ir["constraints"]["CondCompare"]["rule"] == {
            "kind":    "conditional_rule",
            "ref":     "Agent.score",
            "op":      ">",
            "value":   0.5,
            "require": "review",
            "before":  "publish",
        }

    def test_cond_bool_true_and_false(self):
        cond_true = _constraint_decl(
            "CondTrue",
            _priority("high"),
            _rule(_if_rule(_state_ref("Agent", "current_mode"),
                           Tree("cond_bool_true", []))),
            _on_violation("flag"),
        )
        cond_false = _constraint_decl(
            "CondFalse",
            _priority("high"),
            _rule(_if_rule(_state_ref("Agent", "current_mode"),
                           Tree("cond_bool_false", []))),
            _on_violation("flag"),
        )
        ok, errors, ir = _validate(_minimal_section(cond_true, cond_false))
        assert ok, errors
        rule_t = ir["constraints"]["CondTrue"]["rule"]
        assert rule_t["kind"] == "conditional_rule"
        assert rule_t["op"] == "=="
        assert rule_t["value"] is True
        rule_f = ir["constraints"]["CondFalse"]["rule"]
        assert rule_f["op"] == "=="
        assert rule_f["value"] is False

    def test_cond_contradiction(self):
        constraint = _constraint_decl(
            "CondContra",
            _priority("high"),
            _rule(_if_rule(_state_ref("Agent", "current_mode"),
                           Tree("cond_contradiction", []))),
            _on_violation("flag"),
        )
        ok, errors, ir = _validate(_minimal_section(constraint))
        assert ok, errors
        assert ir["constraints"]["CondContra"]["rule"] == {
            "kind":    "contradiction_rule",
            "ref":     "Agent.current_mode",
            "require": "review",
            "before":  "publish",
        }
