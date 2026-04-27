"""
Pi Script v0.1 — Semantic Validator (M2)
Walks the Lark AST produced by parser.py and runs five semantic checks.
Returns: (is_valid: bool, errors: list[str], ir: dict)
"""

from __future__ import annotations

from typing import Any

from lark import Tree, Token


# ── Helpers ───────────────────────────────────────────────────────────────────

def _leaf_value(node) -> str:
    """Extract string value from a terminal-like node.
    Handles Token, Tree with children, and empty Tree (value in .data).
    """
    if isinstance(node, Token):
        return str(node)
    if isinstance(node, Tree):
        if node.children:
            return _leaf_value(node.children[0])
        return str(node.data)
    return str(node)


def _tok(node: Tree, index: int) -> str:
    """Return children[index] as a plain string."""
    return str(node.children[index])


def _subtrees(tree: Tree, data: str) -> list[Tree]:
    return [n for n in tree.iter_subtrees() if n.data == data]


def _first_child_tree(node: Tree, data: str) -> Tree | None:
    for c in node.children:
        if isinstance(c, Tree) and c.data == data:
            return c
    return None


def _state_ref_str(node: Tree) -> str:
    """state_ref node → 'Entity.state_name'"""
    return f"{node.children[0]}.{node.children[1]}"


def _extract_duration(node: Tree) -> dict[str, Any]:
    """duration node → {value: float, unit: str}"""
    unit_node = node.children[1]
    if isinstance(unit_node, Token):
        unit = str(unit_node)
    elif isinstance(unit_node, Tree):
        if unit_node.children:
            unit = str(unit_node.children[0])
        else:
            # Empty tree — unit is encoded in the rule name, e.g. "time_unit__minutes"
            unit = str(unit_node.data)
    else:
        unit = str(unit_node)
    return {
        "value": float(_tok(node, 0)),
        "unit": unit,
    }


def _extract_state_type(node) -> str:
    """state_type node → human-readable type string."""
    if isinstance(node, Token):
        return str(node)
    if not node.children:
        return node.data
    ch = node.children[0]
    if isinstance(ch, Token):
        # Two PI_NUMBER children → range(lo..hi); one STATE_TYPE_KW → keyword type
        if len(node.children) == 2:
            return f"range({ch}..{node.children[1]})"
        return str(ch)
    if isinstance(ch, Tree):
        return f"sequence({_extract_state_type(ch)})"
    return "unknown"


def _extract_pi_value(node: Tree) -> Any:
    """pi_value alias node → Python scalar."""
    alias = node.data
    if alias == "pv_number":
        raw = str(node.children[0])
        return float(raw) if "." in raw else int(raw)
    if alias == "pv_true":
        return True
    if alias == "pv_false":
        return False
    if alias == "pv_string":
        return str(node.children[0]).strip('"')
    if alias == "pv_state_ref":
        return _state_ref_str(node.children[0])
    return None


def _extract_rule(rule_expr_node: Tree) -> dict[str, Any]:
    """rule_expr node → flat dict the evaluator can act on."""
    inner = rule_expr_node.children[0]
    kind = inner.data

    if kind == "range_rule":
        ref = _first_child_tree(inner, "state_ref")
        if ref is None:
            return {"kind": "unknown"}
        return {
            "kind":   "range_rule",
            "ref":    _state_ref_str(ref),
            "lo":     float(_tok(inner, 1)),
            "hi":     float(_tok(inner, 2)),
        }

    if kind == "threshold_rule":
        ref = _first_child_tree(inner, "state_ref")
        dur = _first_child_tree(inner, "duration")
        if ref is None or dur is None:
            return {"kind": "unknown"}
        return {
            "kind":      "threshold_rule",
            "ref":       _state_ref_str(ref),
            "below":     float(str(inner.children[1])),
            "within":    _extract_duration(dur),
        }

    if kind == "equality_rule":
        ref = _first_child_tree(inner, "state_ref")
        if ref is None:
            return {"kind": "unknown"}
        val_node = inner.children[1]
        return {
            "kind":  "equality_rule",
            "ref":   _state_ref_str(ref),
            "value": _extract_pi_value(val_node),
        }

    if kind == "membership_rule":
        ref = _first_child_tree(inner, "state_ref")
        if ref is None:
            return {"kind": "unknown"}
        return {
            "kind": "membership_rule",
            "ref":  _state_ref_str(ref),
        }

    if kind == "if_rule":
        ref = _first_child_tree(inner, "state_ref")
        if ref is None:
            return {"kind": "unknown"}
        cond = inner.children[1]          # if_condition alias node
        require = str(inner.children[2])  # SNAKE_ID action
        before  = str(inner.children[3])  # SNAKE_ID outcome

        if cond.data == "cond_compare":
            return {
                "kind":      "conditional_rule",
                "ref":       _state_ref_str(ref),
                "op":        str(cond.children[0]),
                "value":     _extract_pi_value(cond.children[1]),
                "require":   require,
                "before":    before,
            }
        if cond.data in ("cond_bool_true", "cond_bool_false"):
            return {
                "kind":    "conditional_rule",
                "ref":     _state_ref_str(ref),
                "op":      "==",
                "value":   cond.data == "cond_bool_true",
                "require": require,
                "before":  before,
            }
        if cond.data == "cond_contradiction":
            return {
                "kind":    "contradiction_rule",
                "ref":     _state_ref_str(ref),
                "require": require,
                "before":  before,
            }

    return {"kind": "unknown"}


def _extract_violation_action(va_node: Tree) -> list[str]:
    """violation_action node → list of action strings, e.g. ['freeze','rollback']"""
    actions = []
    for c in va_node.children:
        if isinstance(c, Tree) and c.data == "simple_action":
            actions.append(_leaf_value(c))
    return actions


# ── Validator ─────────────────────────────────────────────────────────────────

class PiValidator:

    def __init__(self, tree: Tree):
        self.tree = tree
        self.errors: list[str] = []
        self.ir: dict[str, Any] = {
            "domain":         None,
            "audit_interval": None,
            "tiebreaker":     "timestamp_asc",
            "entities":       {},   # entity_name -> {state_name: type_str}
            "constraints":    {},   # constraint_name -> constraint_ir
            "maps":           {},   # "Entity.state" -> [mapped_value, ...]
            "enforce":        {},   # entity_name -> [constraint_name, ...]
            "arbiter":        None, # arbiter_ir or None
        }

    def validate(self) -> tuple[bool, list[str], dict[str, Any]]:
        self._extract_domain()
        self._extract_entities()
        self._extract_constraints()
        self._extract_maps()
        self._extract_enforce()
        self._extract_arbiter()

        self._check_audit_interval_exactly_once()
        self._check_entity_state_refs_exist()
        self._check_membership_rules_have_maps()
        self._check_enforce_refs_declared()

        return (len(self.errors) == 0), self.errors, self.ir

    # ── Extraction ────────────────────────────────────────────────────────────

    def _extract_domain(self):
        nodes = _subtrees(self.tree, "domain_decl")
        if not nodes:
            self.errors.append("Missing required 'domain' declaration.")
            return
        node = nodes[0]
        self.ir["domain"] = _tok(node, 0)

        for item in node.children:
            if not isinstance(item, Tree) or item.data != "domain_item":
                continue
            ch = item.children[0]
            if isinstance(ch, Tree) and ch.data == "duration":
                self.ir["audit_interval"] = _extract_duration(ch)
            elif isinstance(ch, Tree) and ch.data == "tiebreaker_mode":
                self.ir["tiebreaker"] = _leaf_value(ch)

    def _extract_entities(self):
        for node in _subtrees(self.tree, "entity_decl"):
            name = _tok(node, 0)
            states: dict[str, str] = {}
            for ch in node.children:
                if isinstance(ch, Tree) and ch.data == "state_field":
                    sname = _tok(ch, 0)
                    stype_node = ch.children[1]
                    stype_str = _extract_state_type(stype_node)
                    states[sname] = stype_str
            self.ir["entities"][name] = states

    def _extract_constraints(self):
        for node in _subtrees(self.tree, "constraint_decl"):
            name = _tok(node, 0)
            rec: dict[str, Any] = {
                "priority":     None,
                "rule":         None,
                "on_violation": [],
                "escalation":   [],
                "decay_check":  None,
            }
            for ch in node.children:
                if not isinstance(ch, Tree):
                    continue
                if ch.data == "c_priority":
                    rec["priority"] = _leaf_value(ch.children[0])
                elif ch.data == "c_rule":
                    rec["rule"] = _extract_rule(ch.children[0])
                elif ch.data == "c_on_violation":
                    rec["on_violation"] = _extract_violation_action(ch.children[0])
                elif ch.data == "c_decay_check":
                    rec["decay_check"] = _extract_duration(ch.children[0])
                elif ch.data == "c_escalation":
                    esc_block = ch.children[0]
                    steps = []
                    for step in esc_block.children:
                        if isinstance(step, Tree) and step.data == "escalation_step":
                            at_n   = float(_tok(step, 0))
                            action = _leaf_value(step.children[1])
                            steps.append({"at": at_n, "action": action})
                    rec["escalation"] = steps
            self.ir["constraints"][name] = rec

    def _extract_maps(self):
        for node in _subtrees(self.tree, "map_decl"):
            target_ref = None
            maps_to_val = None
            triggers: list[str] = []

            for ch in node.children:
                if not isinstance(ch, Tree):
                    continue
                if ch.data == "mi_target":
                    target_ref = _state_ref_str(ch.children[0])
                elif ch.data == "mi_maps_to":
                    maps_to_val = _extract_pi_value(ch.children[0])
                elif ch.data == "mi_triggers":
                    tlist = ch.children[0]
                    for entry in tlist.children:
                        if isinstance(entry, Tree) and entry.data == "trigger_entry":
                            triggers.append(str(entry.children[0]).strip('"'))
                        elif isinstance(entry, Tree) and entry.data == "regex_trigger":
                            triggers.append(f"regex:{str(entry.children[0]).strip(chr(34))}")

            if target_ref is not None:
                self.ir["maps"].setdefault(target_ref, [])
                self.ir["maps"][target_ref].append({
                    "maps_to":  maps_to_val,
                    "triggers": triggers,
                })

    def _extract_enforce(self):
        for node in _subtrees(self.tree, "enforce_decl"):
            entity_name = None
            constraint_names: list[str] = []
            for ch in node.children:
                if not isinstance(ch, Tree):
                    continue
                if ch.data == "ei_entity":
                    entity_name = str(ch.children[0])
                elif ch.data == "ei_constraints":
                    ref_list = ch.children[0]
                    for tok in ref_list.children:
                        if isinstance(tok, Token):
                            constraint_names.append(str(tok))
            if entity_name:
                self.ir["enforce"][entity_name] = constraint_names

    def _extract_arbiter(self):
        for node in _subtrees(self.tree, "arbiter_decl"):
            name = _tok(node, 0)
            rec: dict[str, Any] = {
                "name":                  name,
                "acceptable_evolution":  [],
                "never_acceptable":      [],
                "requires_human_review": [],
                "acceptance_monitor":    None,
            }
            for ch in node.children:
                if not isinstance(ch, Tree):
                    continue
                if ch.data == "ai_acceptable":
                    rec["acceptable_evolution"] = _str_list(ch.children[0])
                elif ch.data == "ai_never":
                    rec["never_acceptable"] = _str_list(ch.children[0])
                elif ch.data == "ai_human_review":
                    rec["requires_human_review"] = _str_list(ch.children[0])
                elif ch.data == "ai_monitor":
                    mon: dict[str, Any] = {}
                    for item in ch.children:
                        if isinstance(item, Tree) and item.data == "mi_threshold":
                            mon["threshold"] = float(_tok(item, 0))
                        elif isinstance(item, Tree) and item.data == "mi_window":
                            mon["window"] = _extract_duration(item.children[0])
                    rec["acceptance_monitor"] = mon
            self.ir["arbiter"] = rec
            break

    # ── Semantic checks ───────────────────────────────────────────────────────

    def _check_audit_interval_exactly_once(self):
        count = sum(
            1 for item in _subtrees(self.tree, "domain_item")
            if item.children and isinstance(item.children[0], Tree)
            and item.children[0].data == "duration"
        )
        if count == 0:
            self.errors.append(
                "audit_interval is required and must appear exactly once in the domain block."
            )
        elif count > 1:
            self.errors.append(
                f"audit_interval must appear exactly once (found {count})."
            )

    def _check_entity_state_refs_exist(self):
        for node in _subtrees(self.tree, "state_ref"):
            entity = str(node.children[0])
            state  = str(node.children[1])
            ref    = f"{entity}.{state}"
            if entity not in self.ir["entities"]:
                self.errors.append(
                    f"Reference to undeclared entity '{entity}' in '{ref}'."
                )
            elif state not in self.ir["entities"][entity]:
                self.errors.append(
                    f"Entity '{entity}' has no state '{state}' (referenced in '{ref}')."
                )

    def _check_membership_rules_have_maps(self):
        for cname, cdata in self.ir["constraints"].items():
            rule = cdata.get("rule")
            if not rule or rule["kind"] != "membership_rule":
                continue
            ref = rule["ref"]
            if ref not in self.ir["maps"] or not self.ir["maps"][ref]:
                self.errors.append(
                    f"Constraint '{cname}': membership rule targets '{ref}' "
                    f"but no map block declares that as its target. "
                    f"Add at least one 'map' block with 'target: {ref}'."
                )

    def _check_enforce_refs_declared(self):
        declared = set(self.ir["constraints"])
        for entity, names in self.ir["enforce"].items():
            for name in names:
                if name not in declared:
                    self.errors.append(
                        f"enforce block for '{entity}' references "
                        f"undeclared constraint '{name}'."
                    )


# ── Private helper ────────────────────────────────────────────────────────────

def _str_list(node: Tree) -> list[str]:
    return [str(c).strip('"') for c in node.children if isinstance(c, Token)]


# ── CLI ───────────────────────────────────────────────────────────────────────

def validate_file(path: str) -> tuple[bool, list[str], dict[str, Any]]:
    from pi_script.parser import parse_file
    tree, err = parse_file(path)
    if err:
        return False, [err], {}
    return PiValidator(tree).validate()


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) < 2:
        print("Usage: python validator.py <file.pi>", file=sys.stderr)
        sys.exit(1)
    ok, errors, ir = validate_file(sys.argv[1])
    if errors:
        for e in errors:
            print(f"ERROR  {e}", file=sys.stderr)
    if ok:
        print(json.dumps(ir, indent=2))
        print(f"OK  {sys.argv[1]}", file=sys.stderr)
    sys.exit(0 if ok else 1)
